"""
HackT Sovereign Core - HTTP API Service Module
===============================================
Provides REST endpoints for React frontend integration via fetch():
- /api/chat: Streaming chat with RAG context
- /api/embed: Generate embeddings for client-side vector search
- /api/vision/*: Screen analysis and OCR controls
- /api/audio/*: STT transcription and TTS synthesis
- /api/system/*: Mode switching, health checks, permissions
- /api/action/*: Code injection and fix generation
"""

import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field, validator
import numpy as np

from utils.logger import get_logger

logger = get_logger("hackt.services.http_api")

# Router for FastAPI
api_router = APIRouter()


# ======================================================================
# Request/Response Models
# ======================================================================

class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    vector: Optional[List[float]] = None  # Pre-computed embedding (768-dim)
    mode: str = Field(default="active", regex="^(active|passive)$")
    session_id: str = Field(..., min_length=1)
    
    @validator('prompt')
    def validate_prompt(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()


class ChatResponse(BaseModel):
    token: str
    citations: List[str] = []
    threat_level: Optional[str] = None
    kv_cache_usage: float = 0.0


class EmbedRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=512)


class EmbedResponse(BaseModel):
    vector: List[float]


class VisionRequest(BaseModel):
    task: str = Field(default="<OCR>", regex="^<OCR>|<OD>|<CAPTION>|<DETAILED_CAPTION>$")
    region: Optional[Dict[str, int]] = None  # {x, y, width, height}


class VisionResponse(BaseModel):
    text: str
    bboxes: Optional[List[Dict]] = None
    labels: Optional[List[str]] = None
    timestamp: str


class AudioTranscribeResponse(BaseModel):
    text: str
    confidence: float
    language: str


class AudioSynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class ThreatScanRequest(BaseModel):
    content: str
    content_type: str = Field(regex="^(code|text|screen_ocr)$")


class ThreatScanResponse(BaseModel):
    threat_level: str  # NONE, LOW, MEDIUM, HIGH, CRITICAL
    vulnerabilities: List[Dict]
    confidence: float
    citations: List[str]


class CodeInjectionRequest(BaseModel):
    session_id: str
    instruction: str
    file_path: Optional[str] = None


# ======================================================================
# Utility Functions
# ======================================================================
def _clean_json_response(text: str) -> str:
    """Strips markdown formatting from LLM JSON responses"""
    text = text.strip()
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    return text.strip()

# ======================================================================
# Health & System Endpoints
# ======================================================================

@api_router.get("/health")
async def health_check():
    """Health check endpoint for React polling"""
    from main import engine, app_state, vram_guard
    import sys
    import torch
    
    vram_usage = 0.0
    if vram_guard:
        vram_usage = vram_guard.get_usage_stats().get("used_gb", 0.0)

    return {
        "status": "healthy",
        "mode": app_state.get("mode", "active"),
        "llm_loaded": engine.llm is not None if engine else False,
        "vram_usage_gb": vram_usage,
        "gpu_available": torch.cuda.is_available(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }


@api_router.post("/system/mode")
async def switch_mode(request: Dict):
    """Switch between Active/Passive modes"""
    from main import app_state
    from services.monitor import screen_monitor
    from services.websocket import telemetry_manager
    
    mode = request.get("mode")
    if mode not in ["active", "passive"]:
        raise HTTPException(400, "Invalid mode. Must be 'active' or 'passive'")
    
    try:
        # Update global state
        app_state["mode"] = mode
        
        # Start/stop passive services
        if mode == "passive":
            screen_monitor.start()
            telemetry_manager.start()
        else:
            screen_monitor.stop()
        
        logger.info(f"Mode switched to {mode}")
        return {"status": "success", "mode": mode}
        
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@api_router.post("/system/shutdown")
async def shutdown():
    """Nuclear kill switch from Tauri tray or React"""
    logger.info("🔥 Shutdown command received")
    import sys
    from main import engine
    from services.websocket import telemetry_manager
    
    telemetry_manager.stop()
    if engine:
        engine.unload_llm()
        engine.unload_vision()
    sys.exit(0)


# ======================================================================
# Chat Streaming Endpoint (Server-Sent Events)
# ======================================================================

@api_router.post("/chat")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """Stream chat responses token-by-token with RAG context."""
    from main import engine, embedder, retriever, app_state
    from services.idle_manager import idle_manager
    
    # 0. Reset Idle Timer (User is actively engaged!)
    idle_manager.record_activity()

    if not engine or not embedder or not retriever:
        raise HTTPException(500, "Sovereign Core is not fully initialized.")

    # 1. Generate query vector if not provided
    if request.vector is None:
        if not embedder._loaded:
            embedder.load()
        query_vector = embedder.encode(request.prompt)
    else:
        query_vector = np.array(request.vector)
    
    # 2. Retrieve hybrid context from RAG engine
    try:
        context = retriever.retrieve(
            query=request.prompt,
            query_vector=query_vector,
            mode=request.mode
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        context = "No relevant context found in Knowledge Vault."
    
    # 3. Build prompt with system instructions + context + query
    try:
        from prompts.rag_prompt import build_rag_prompt
        full_prompt = build_rag_prompt(
            query=request.prompt,
            project_context="",  # Could load from active_context
            retrieved_chunks=context
        )
    except ImportError:
        # Fallback prompt if module is missing
        full_prompt = f"Context: {context}\n\nUser: {request.prompt}\nAgent:"
    
    # 4. Stream response from LLM
    async def generate() -> AsyncGenerator[str, None]:
        try:
            token_count = 0
            # Run the generator in a thread to prevent blocking FastAPI
            for token in engine.stream_chat(
                prompt=full_prompt,
                context=context,
                max_tokens=512
            ):
                response = ChatResponse(
                    token=token,
                    citations=[],
                    threat_level=app_state.get("threat_level", "safe"),
                    kv_cache_usage=token_count / 4096
                )
                yield f"data: {response.json()}\n\n"
                token_count += 1
                await asyncio.sleep(0)  # Yield control to event loop
                
        except Exception as e:
            logger.error(f"Chat streaming failed: {e}")
            error_response = ChatResponse(token="", citations=[], threat_level="error", kv_cache_usage=0.0)
            yield f"data: {error_response.json()}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


# ======================================================================
# Vision & OCR Endpoints
# ======================================================================

@api_router.post("/vision/analyze", response_model=VisionResponse)
async def analyze_screen(request: VisionRequest):
    """Analyze screen capture with Florence-2"""
    from services.screen import screen_analyzer
    from main import app_state
    
    if app_state.get("mode") != "passive":
        raise HTTPException(400, "Vision analysis only available in Passive Mode")
    
    try:
        # Calls the unified screen_analyzer which handles capture + engine unloading safely
        result = await screen_analyzer.analyze(task=request.task, region=request.region)
        
        if result.get("type") == "error":
            raise HTTPException(500, result.get("text", "Unknown Vision Error"))
            
        import datetime
        return VisionResponse(
            text=result.get("text", ""),
            bboxes=result.get("objects", []),
            labels=[obj["label"] for obj in result.get("objects", [])] if result.get("objects") else [],
            timestamp=datetime.datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        raise HTTPException(500, "Failed to analyze screen")


@api_router.post("/vision/scan-now")
async def manual_screen_scan():
    """Trigger immediate screen analysis (for PassiveBubble manual scan)"""
    from services.monitor import screen_monitor
    
    # Trigger an asynchronous one-off scan
    asyncio.create_task(screen_monitor._scan_loop_once())
    return {"status": "scan_triggered"}


# ======================================================================
# Audio Endpoints (STT/TTS)
# ======================================================================

@api_router.post("/audio/synthesize")
async def synthesize_speech(request: AudioSynthesizeRequest):
    """Synthesize speech via Piper TTS with dynamic prosody"""
    from services.audio import tts_service
    from main import app_state
    
    try:
        # Apply prosodic intelligence based on current global threat level
        threat_level = app_state.get("threat_level", "safe")
        
        # Generate WAV audio bytes (Offload to thread to prevent UI freeze)
        wav_bytes = await asyncio.to_thread(
            tts_service.synthesize, 
            request.text, 
            urgency_score=0.5, 
            threat_level=threat_level
        )
        
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise HTTPException(500, "Speech synthesis failed")


@api_router.post("/audio/mic-start")
async def start_mic():
    """Enable continuous microphone listening for voice commands"""
    from services.audio import stt_service
    from services.idle_manager import idle_manager
    idle_manager.record_activity()
    
    try:
        stt_service.start_listening()
        return {"status": "mic_enabled"}
    except Exception as e:
        raise HTTPException(500, str(e))


@api_router.post("/audio/mic-stop")
async def stop_mic():
    """Disable continuous microphone listening"""
    from services.audio import stt_service
    stt_service.stop_listening()
    return {"status": "mic_disabled"}


# ======================================================================
# Threat Scanning Endpoint
# ======================================================================

@api_router.post("/threat/scan", response_model=ThreatScanResponse)
async def threat_scan(request: ThreatScanRequest):
    """Analyze code/text for security vulnerabilities"""
    from main import engine, retriever
    
    if not engine or not retriever:
        raise HTTPException(500, "Core not ready")

    try:
        from prompts.threat_prompt import THREAT_ASSESSMENT_PROMPT
        prompt = THREAT_ASSESSMENT_PROMPT.format(
            input_text=request.content[:2000],
            context="Manual API Scan"
        )
    except ImportError:
        prompt = f"Analyze for vulnerabilities: {request.content[:2000]}"
    
    try:
        # Run inference (temperature 0 for stable JSON output)
        result = engine.generate(prompt=prompt, max_tokens=256, temperature=0.0)
        
        # Parse JSON response using the robust cleaner
        try:
            clean_json = _clean_json_response(result)
            parsed = json.loads(clean_json)
            return ThreatScanResponse(**parsed)
        except json.JSONDecodeError:
            # Fallback: simple keyword-based detection if LLM hallucinated markdown
            is_threat = retriever.fast_scan(request.content)
            return ThreatScanResponse(
                threat_level="HIGH" if is_threat else "NONE",
                vulnerabilities=[] if not is_threat else [{"type": "keyword_match"}],
                confidence=0.7 if is_threat else 0.95,
                citations=[]
            )
            
    except Exception as e:
        logger.error(f"Threat scan failed: {e}")
        raise HTTPException(500, "Failed to analyze for threats")


# ======================================================================
# Code Injection Endpoint
# ======================================================================

@api_router.post("/action/fix-universal")
async def trigger_code_injection(request: CodeInjectionRequest):
    """Generate and inject AI fix into active IDE using OS-Level Time-Stop"""
    from main import engine, embedder, retriever
    from services.code_watcher import code_watcher
    
    if not request.instruction:
        raise HTTPException(400, "Instruction is required")
    
    if not engine or not embedder or not retriever:
        raise HTTPException(500, "Core systems offline.")
    
    try:
        # 1. Generate fix using LLM + RAG context
        if not embedder._loaded:
            embedder.load()
        query_vector = embedder.encode(request.instruction)
        context = retriever.retrieve(
            query=request.instruction,
            query_vector=query_vector,
            mode="passive"
        )
        
        try:
            from prompts.code_prompt import CODE_FIX_INJECTION_PROMPT
            fix_prompt = CODE_FIX_INJECTION_PROMPT.format(
                file_path=request.file_path or "unknown",
                vulnerability_type="security issue",
                line_start=0,
                line_end=0,
                retrieved_context=context
            )
        except ImportError:
            fix_prompt = f"Fix the vulnerability according to: {request.instruction}. Context: {context}"
        
        # Generate full fix text (Blocking call wrapped in thread)
        raw_fix = await asyncio.to_thread(engine.generate, fix_prompt, max_tokens=512, temperature=0.1)
        
        # Clean markdown code blocks from LLM output before pasting
        fix_text = re.sub(r'```[a-z]*\n', '', raw_fix).replace('```', '').strip()
        
        # 2. Inject fix into IDE via OS-Level Hardware Lock
        # This is more reliable than WebSockets if the IDE extension is buggy
        file_target = request.file_path or code_watcher.get_active_context().get("file", "unknown")
        
        success = await code_watcher.inject_fix(file_target, fix_text)
        
        if success:
            return {"status": "fix_injected", "code": fix_text[:100] + "..."}
        else:
            return {"status": "fix_generated", "code": fix_text[:100] + "...", "warning": "Injection failed. Code returned for manual pasting."}
        
    except Exception as e:
        logger.error(f"Code injection failed: {e}")
        raise HTTPException(500, "Failed to generate or inject fix")


# ======================================================================
# Feedback Endpoint (RLHF Data Collection)
# ======================================================================

@api_router.post("/chat/feedback")
async def submit_feedback(request: Dict):
    """Record user feedback for model improvement (RLHF)"""
    message_id = request.get("messageId")
    feedback = request.get("feedback")  # "up" or "down"
    
    if not message_id or feedback not in ["up", "down"]:
        raise HTTPException(400, "Invalid feedback request")
    
    try:
        logger.info(f"RLHF Feedback recorded: {message_id} -> {feedback}")
        return {"status": "feedback_recorded"}
    except Exception as e:
        logger.error(f"Feedback storage failed: {e}")
        return {"status": "feedback_logged", "error": str(e)}