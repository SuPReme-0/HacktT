"""
HackT Sovereign Core - HTTP API Service Module (v6.0)
======================================================
The Unified REST Interface. 
Strictly handles HTTP routing and delegates processing to dedicated services.
"""

import os
import signal
import asyncio
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field, field_validator, ConfigDict

from utils.logger import get_logger
from utils.config import config
from core.engine import engine
from core.memory import vram_guard
from services.audio import stt_service, tts_service
from services.chat_service import chat_service  # 🧠 The Dedicated Brain Connection

logger = get_logger("hackt.services.http_api")

# Prefix "/api" is handled by main.py, so we mount at root here
api_router = APIRouter()

# ======================================================================
# REQUEST MODELS
# ======================================================================

class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    
    prompt: str = Field(..., min_length=1, max_length=2000)
    vector: Optional[List[float]] = Field(default=None)
    mode: str = Field(default="active", pattern="^(active|passive)$")
    session_id: str = Field(default="default_session")
    query_type: str = Field(default="chat")
    project_context: Optional[str] = Field(default=None)
    
    @field_validator("prompt")
    @classmethod
    def sanitize_prompt(cls, v: str) -> str:
        """Strip dangerous prompt injection prefixes."""
        dangerous_prefixes = ["ignore previous", "system prompt", "you are now"]
        if any(p in v.lower() for p in dangerous_prefixes):
            logger.warning("Prompt injection detected & logged.")
        return v.strip()

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    voice: str = Field(default="en_US-lessac-medium")
    speed: float = Field(default=1.0)

# ======================================================================
# CORE ENDPOINTS
# ======================================================================

@api_router.get("/health")
async def health_check():
    """Health check for React/Tauri polling."""
    vram_usage = 0.0
    if vram_guard:
        vram_usage = vram_guard.get_usage_stats().get("used_gb", 0.0)

    return {
        "status": "healthy",
        "mode": config.mode,
        "llm_loaded": engine.llm is not None if engine else False,
        "vram_usage_gb": vram_usage,
        "timestamp": time.time(),
    }

@api_router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> StreamingResponse:
    """
    Connects directly to the Chat Service Brain.
    """
    # 0. Optional: Reset Idle Timer safely
    try:
        from services.idle_manager import idle_manager
        idle_manager.record_activity()
    except ImportError:
        pass 
        
    # 1. Non-Blocking Engine Readiness Check
    if not engine:
        raise HTTPException(503, "Core offline.")
    
    if not engine.llm:
        logger.info("LLM not in memory. Booting into CPU/GPU now...")
        success = await asyncio.to_thread(engine.load_llm)
        if not success:
            raise HTTPException(503, "Hardware exhausted. Cannot load LLM.")

    # 2. Delegate the entire RAG + LLM pipeline to the Chat Service
    stream_generator = chat_service.generate_stream(
        prompt=request.prompt,
        mode=request.mode,
        session_id=request.session_id,
        query_type=request.query_type,
        project_context=request.project_context,
        vector=request.vector
    )

    return StreamingResponse(
        stream_generator, 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ======================================================================
# AUDIO & SYSTEM ENDPOINTS
# ======================================================================

@api_router.post("/audio/transcribe")
async def transcribe_audio(request: Request):
    """Speech-to-Text: Accepts raw binary audio bytes."""
    try:
        audio_bytes = await request.body()
        if not audio_bytes:
            raise HTTPException(400, "No audio data received.")
            
        text = await stt_service.transcribe_audio(audio_bytes)
        return {"text": text}
    except Exception as e:
        logger.error(f"STT failed: {e}")
        raise HTTPException(500, str(e))

@api_router.post("/tts")
async def synthesize_speech(request: TTSRequest):
    """Text-to-Speech: Returns a binary WAV file."""
    try:
        audio_bytes = await tts_service.synthesize_speech(
            text=request.text, voice=request.voice, speed=request.speed
        )
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'attachment; filename="tts_output.wav"', 
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise HTTPException(500, str(e))

@api_router.post("/system/shutdown")
async def shutdown():
    """Nuclear kill switch (Graceful trigger)"""
    logger.info("🔥 Shutdown command received from client.")
    os.kill(os.getpid(), signal.SIGTERM)
    return {"status": "shutting down"}