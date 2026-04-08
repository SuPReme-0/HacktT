"""
HackT Sovereign Core - HTTP API Router
======================================
Defines all REST API endpoints for frontend communication.

Features:
- SSE streaming for chat responses
- Audio transcription (STT) and synthesis (TTS)
- Threat scanning and code diff broadcasting
- System configuration and health checks
- Proper error handling and CORS support
"""

import asyncio
import json
import time
from typing import AsyncGenerator, Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, validator

from utils.config import config
from utils.logger import get_logger
from core.engine import engine
from core.embedder import embedder
from core.rag import retriever
from core.memory import vram_guard
from services.websocket import telemetry_manager
from services.audio import stt_service, tts_service
from services.threat_scanner import threat_scanner

logger = get_logger("hackt.api")

# Create router with prefix
api_router = APIRouter()

# ======================================================================
# REQUEST/RESPONSE MODELS
# ======================================================================

class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="User query or command")
    mode: str = Field(default="active", pattern="^(active|passive)$", description="Agent operation mode")
    query_type: str = Field(default="chat", pattern="^(chat|voice|audit|code)$", description="Type of query")
    session_id: str = Field(..., min_length=1, description="Unique session identifier")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context data")
    
    @validator('prompt')
    def validate_prompt(cls, v):
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()

class ChatResponse(BaseModel):
    token: str
    done: bool = False
    metadata: Optional[Dict[str, Any]] = None

class ThreatScanRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Code or text content to scan")
    content_type: str = Field(default="code", pattern="^(code|text|url)$", description="Type of content")
    source: Optional[str] = Field(default=None, description="Source file or URL")

class ThreatScanResponse(BaseModel):
    is_threat: bool
    threat_level: Optional[str] = None
    description: Optional[str] = None
    suggested_fix: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="Text to synthesize")
    voice: Optional[str] = Field(default=None, description="Voice model identifier")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech speed multiplier")

class HealthResponse(BaseModel):
    status: str
    mode: str
    llm_loaded: bool
    vram_usage_gb: float
    timestamp: float
    version: str = "2.4.0"

class SystemModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(active|passive)$", description="Target operation mode")

class IDEConfigRequest(BaseModel):
    enabled: bool
    port: int = Field(ge=1024, le=65535, description="Port for IDE integration")

# ======================================================================
# HELPER FUNCTIONS
# ======================================================================

async def generate_chat_stream(
    prompt: str,
    mode: str,
    session_id: str,
    query_type: str,
    context: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Generate streaming chat response using SSE format.
    Yields JSON-encoded tokens with proper SSE formatting.
    """
    try:
        # Prepare context for RAG retrieval
        query_vector = await embedder.encode(prompt) if embedder._loaded else None
        
        # Retrieve relevant context from vault
        retrieved_chunks = []
        if query_vector and retriever._loaded:
            retrieved_chunks = await retriever.retrieve(
                query=prompt,
                query_vector=query_vector,
                mode=mode,
                query_type=query_type
            )
        
        # Format prompt with retrieved context
        formatted_prompt = prompt
        if retrieved_chunks:
            context_text = "\n\n".join([chunk["text"] for chunk in retrieved_chunks[:3]])
            formatted_prompt = f"Context:\n{context_text}\n\nQuery: {prompt}"
        
        # Generate response using LLM with streaming
        async for chunk in engine.generate_stream(
            prompt=formatted_prompt,
            max_tokens=512,
            temperature=0.3 if mode == "passive" else 0.7,
            session_id=session_id
        ):
            # Format as SSE event
            response = ChatResponse(token=chunk, done=False)
            yield f" {json.dumps(response.dict())}\n\n"
            # Small delay to prevent overwhelming the client
            await asyncio.sleep(0.01)
        
        # Send final done event
        yield f" {json.dumps({'done': True})}\n\n"
        
    except Exception as e:
        logger.error(f"Chat stream generation failed: {e}")
        # Send error event
        yield f" {json.dumps({'error': str(e), 'done': True})}\n\n"

# ======================================================================
# API ENDPOINTS
# ======================================================================

@api_router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for load balancers and frontend polling.
    Returns system status, VRAM usage, and LLM load state.
    """
    return HealthResponse(
        status="healthy",
        mode=config.mode,
        llm_loaded=engine.llm is not None,
        vram_usage_gb=vram_guard.get_usage_stats().get("used_gb", 0.0),
        timestamp=time.time()
    )

@api_router.post("/api/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Chat endpoint with Server-Sent Events (SSE) streaming.
    
    Accepts user prompts and streams AI responses token-by-token.
    Supports active/passive modes and different query types.
    
    SSE Format:
     {"token": "chunk", "done": false}
     {"done": true}
    """
    try:
        return StreamingResponse(
            generate_chat_stream(
                prompt=request.prompt,
                mode=request.mode,
                session_id=request.session_id,
                query_type=request.query_type,
                context=request.context
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable Nginx buffering
            }
        )
    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@api_router.post("/api/audio/transcribe")
async def transcribe_audio(request: Request):
    """
    Speech-to-Text endpoint.
    
    Accepts raw audio bytes in request body and returns transcribed text.
    Supports WAV, MP3, and other common audio formats via Faster-Whisper.
    """
    try:
        # Get raw audio bytes from request body
        audio_bytes = await request.body()
        
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="No audio data received")
        
        # Transcribe using STT service
        text = await stt_service.transcribe_audio(audio_bytes)
        
        return {"text": text}
        
    except Exception as e:
        logger.error(f"STT transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@api_router.post("/api/tts")
async def synthesize_speech(request: TTSRequest):
    """
    Text-to-Speech endpoint.
    
    Accepts text and returns synthesized audio as WAV bytes.
    Supports voice selection and speed control via Piper TTS.
    """
    try:
        # Synthesize speech using TTS service
        audio_bytes = await tts_service.synthesize_speech(
            text=request.text,
            voice=request.voice,
            speed=request.speed
        )
        
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="tts_output.wav"',
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {str(e)}")

@api_router.post("/api/threat/scan", response_model=ThreatScanResponse)
async def scan_threat(request: ThreatScanRequest):
    """
    Threat scanning endpoint.
    
    Analyzes code or text for security vulnerabilities using RAG + LLM.
    Returns threat assessment with suggested fixes for critical issues.
    """
    try:
        # Perform threat analysis
        result = await threat_scanner.analyze_content(
            content=request.content,
            content_type=request.content_type,
            source=request.source
        )
        
        return ThreatScanResponse(**result)
        
    except Exception as e:
        logger.error(f"Threat scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Threat scan failed: {str(e)}")

@api_router.post("/api/system/mode")
async def toggle_system_mode(request: SystemModeRequest):
    """
    Toggle system operation mode between active and passive.
    
    Active mode: Chat-only, minimal resource usage.
    Passive mode: Full surveillance with OCR, code watching, threat scanning.
    """
    try:
        # Update config mode
        old_mode = config.mode
        config.mode = request.mode
        
        # Notify services of mode change
        if request.mode == "passive":
            # Start passive mode services
            threat_scanner.start()
            # ... start other passive services ...
        else:
            # Stop passive mode services
            threat_scanner.stop()
            # ... stop other passive services ...
        
        logger.info(f"System mode changed: {old_mode} → {request.mode}")
        return {"mode": request.mode, "success": True}
        
    except Exception as e:
        logger.error(f"Mode toggle failed: {e}")
        # Revert on failure
        config.mode = old_mode
        raise HTTPException(status_code=500, detail=f"Mode toggle failed: {str(e)}")

@api_router.post("/api/config/ide")
async def configure_ide(request: IDEConfigRequest):
    """
    Configure IDE integration settings.
    
    Enables/disables IDE socket listener and sets port for code streaming.
    """
    try:
        # Update IDE config
        from services.port_listeners import integration_manager
        
        if request.enabled:
            await integration_manager.start_ide_socket(port=request.port)
        else:
            await integration_manager.stop_ide_socket()
        
        logger.info(f"IDE integration {'enabled' if request.enabled else 'disabled'} on port {request.port}")
        return {"enabled": request.enabled, "port": request.port, "success": True}
        
    except Exception as e:
        logger.error(f"IDE config failed: {e}")
        raise HTTPException(status_code=500, detail=f"IDE configuration failed: {str(e)}")

@api_router.get("/api/system/info")
async def get_system_info():
    """
    Get detailed system information for frontend diagnostics.
    
    Returns VRAM stats, loaded models, active services, and configuration.
    """
    try:
        vram_stats = vram_guard.get_usage_stats()
        
        return {
            "vram": vram_stats,
            "models": {
                "llm": engine.llm is not None,
                "embedder": embedder._loaded,
                "retriever": retriever._loaded
            },
            "services": {
                "websocket": telemetry_manager.active_connections > 0,
                "threat_scanner": threat_scanner.is_running,
                "stt": stt_service._loaded,
                "tts": tts_service._loaded
            },
            "config": {
                "mode": config.mode,
                "ports": {
                    "ide": config.services.ide_listener_port,
                    "browser": config.services.browser_listener_port
                }
            },
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"System info failed: {e}")
        raise HTTPException(status_code=500, detail=f"System info failed: {str(e)}")

