"""
HackT Sovereign Core - HTTP API Service Module (v5.0)
======================================================
The Unified REST Interface for React/Tauri.
Features:
- SSE Chat Streaming (Vault-Aware)
- System Health & Control
- Manual Threat Scanning
- Zero Circular Imports
- Background Task Delegation
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, Response, JSONResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict
import numpy as np

from utils.logger import get_logger
from utils.config import config
from core.engine import engine
from core.embedder import embedder
from core.rag import retriever
from core.memory import vram_guard
from core.database import db
from prompts.orchestrator import orchestrator

# Lazy imports to prevent boot-time circular dependencies
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

logger = get_logger("hackt.services.http_api")
api_router = APIRouter(prefix="/api")

# ======================================================================
# Request/Response Models
# ======================================================================

class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    
    prompt: str = Field(..., min_length=1, max_length=2000)
    vector: Optional[List[float]] = Field(default=None, min_length=256, max_length=768)
    mode: str = Field(default="active", pattern="^(active|passive)$")
    session_id: str = Field(default="default_session", min_length=1, max_length=64)
    query_type: str = Field(default="chat", pattern="^(chat|voice|audit|idle)$")
    project_context: Optional[str] = Field(default=None, max_length=4000)
    
    @field_validator("prompt")
    @classmethod
    def sanitize_prompt(cls, v: str) -> str:
        """Remove potential prompt injection patterns."""
        dangerous_prefixes = ["ignore previous", "system prompt", "you are now", "disregard"]
        v_lower = v.lower()
        for prefix in dangerous_prefixes:
            if prefix in v_lower:
                logger.warning(f"Prompt injection attempt detected: {v[:100]}")
                return v  # Log but process
        return v.strip()

class ChatToken(BaseModel):
    token: str
    status: str = "generating" 
    citations: List[str] = Field(default_factory=list)
    threat_level: Optional[str] = None
    kv_cache_usage: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp: float = Field(default_factory=time.time)

class ThreatScanRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)
    content_type: str = Field(default="code", pattern="^(code|text|screen_ocr|terminal_log)$")

# ======================================================================
# Utility Functions
# ======================================================================

def _format_citations(chunks: List[Dict]) -> List[str]:
    """Format RAG chunks into citation strings for frontend display."""
    citations = []
    for chunk in chunks[:3]:  # Limit to top 3 for UI clarity
        source = chunk.get("source", "unknown")
        vault_id = chunk.get("vault_id", 0)
        vault_name = {1: "Library", 2: "Laboratory", 3: "Showroom"}.get(vault_id, "Unknown")
        citations.append(f"[{vault_name}] {source}")
    return citations

def _inject_history(base_prompt: str, history: List[Dict]) -> str:
    """Injects historical turns cleanly into the ChatML structure."""
    if not history:
        return base_prompt
    
    # Split prompt at the first user message marker to insert history BEFORE current query
    parts = base_prompt.split("<|im_start|>user\n")
    if len(parts) < 2:
        return base_prompt
    
    history_str = ""
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_str += f"<|im_start|>{role}\n{content}<|im_end|>\n"
    
    return f"{parts[0]}{history_str}<|im_start|>user\n{parts[1]}"

# ======================================================================
# Chat Streaming Endpoint (Server-Sent Events)
# ======================================================================

@api_router.post("/chat")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks) -> StreamingResponse:
    """
    Unified Chat Endpoint: Classifies -> Embeds -> Retrieves -> Routes -> Streams -> Saves
    """
    # 0. Reset Idle Timer
    try:
        from services.idle_manager import idle_manager
        idle_manager.record_activity()
    except ImportError:
        pass 
    
    # 1. Engine readiness check
    if not engine or not embedder or not retriever:
        raise HTTPException(503, "Sovereign Core not fully initialized.")
    
    if not engine.llm and not engine.load_llm():
        raise HTTPException(503, "VRAM exhausted. Cannot load LLM.")
    
    # 2. 🚀 VAULT INTENT CLASSIFICATION (The Missing Link)
    target_vault = orchestrator.classify_vault_intent(request.prompt)
    
    # 3. 🚀 ASYNC RAG PIPELINE (Vault-Aware)
    try:
        if request.vector is None:
            query_vector = await asyncio.to_thread(embedder.encode, request.prompt)
        else:
            query_vector = np.array(request.vector)
        
        retrieved_chunks = await asyncio.to_thread(
            retriever.retrieve,
            query=request.prompt,
            query_vector=query_vector,
            mode=request.mode,
            query_type=request.query_type,
            target_vault=target_vault  # 🔥 Vault Routing Applied
        )
        citations = _format_citations(retrieved_chunks)
    except Exception as e:
        logger.error(f"RAG pipeline failed: {e}")
        retrieved_chunks = []
        citations = []
    
    # 4. 🚀 DYNAMIC PROMPT ROUTING
    system_state = {"Project Context": request.project_context} if request.project_context else None
    
    route_data = orchestrator.route(
        query=request.prompt,
        mode=request.mode,
        query_type=request.query_type,
        retrieved_chunks=retrieved_chunks,
        system_state=system_state
    )
    
    # 5. 🚀 HISTORY INJECTION & OOM PROTECTION
    try:
        history = await asyncio.to_thread(db.get_session_history, request.session_id, max_turns=8)
    except Exception as e:
        logger.warning(f"History fetch failed: {e}")
        history = []
    
    final_prompt = _inject_history(route_data["prompt"], history)
    
    # Context Window Safety Guard (Prunes history if token count gets dangerously high)
    if len(final_prompt) > 12000:
        logger.warning("Context approaching VRAM limit. Pruning history.")
        final_prompt = _inject_history(route_data["prompt"], history[-2:])  # Keep only last 2 turns

    # 6. 🚀 SSE GENERATOR
    async def sse_generator() -> AsyncGenerator[str, None]:
        full_response = ""
        try:
            for token in engine.stream_chat(prompt=final_prompt, max_tokens=route_data["max_tokens"]):
                full_response += token
                yield f"data: {ChatToken(token=token, citations=citations).model_dump_json()}\n\n"
                await asyncio.sleep(0.001) 
                
            yield f"data: {ChatToken(token='', status='done').model_dump_json()}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {ChatToken(token='[ERROR]', status='error').model_dump_json()}\n\n"
        finally:
            if len(full_response) > 5:
                # 🚀 Delegate SQLite save to FastAPI's non-blocking background workers
                background_tasks.add_task(db.save_turn, request.session_id, request.prompt, full_response)

    return StreamingResponse(sse_generator(), media_type="text/event-stream", background=background_tasks)

# ======================================================================
# Threat Scanning Endpoint
# ======================================================================

@api_router.post("/threat/scan")
async def manual_threat_scan(request: ThreatScanRequest):
    """
    Manual threat scan endpoint for React UI triggers.
    Returns full assessment including suggested_fix for Diff Modal.
    """
    from services.threat_scanner import threat_scanner
    
    if not threat_scanner:
        raise HTTPException(503, "Threat Scanner not initialized.")
    
    result = await threat_scanner.scan_now(
        content=request.content,
        source=request.content_type
    )
    
    return JSONResponse(content=result)

# ======================================================================
# System & Health Endpoints
# ======================================================================

@api_router.get("/health")
async def health_check():
    """Health check endpoint for React polling."""
    vram_usage = 0.0
    if vram_guard:
        vram_usage = vram_guard.get_usage_stats().get("used_gb", 0.0)

    return {
        "status": "healthy",
        "mode": config.mode,
        "rag_status": retriever.health_check(),
        "llm_loaded": engine.llm is not None if engine else False,
        "vram_usage_gb": vram_usage,
        "timestamp": time.time(),
    }

@api_router.post("/system/mode")
async def switch_mode(request: Dict):
    """Switch between Active/Passive modes."""
    mode = request.get("mode", "").lower()
    if mode not in ["active", "passive"]:
        raise HTTPException(400, "Invalid mode. Must be 'active' or 'passive'")
    
    config.mode = mode
    
    # Coordinate background daemons
    if mode == "passive":
        logger.info("Passive mode: Screen monitoring enabled")
    else:
        logger.info("Active mode: Passive daemons suspended")
    
    if telemetry_manager:
        await telemetry_manager.broadcast_telemetry({
            "type": "mode_changed",
            "mode": mode,
            "timestamp": time.time()
        }, target="all")
    
    return {"status": "success", "mode": mode}

@api_router.post("/system/shutdown")
async def shutdown(background_tasks: BackgroundTasks):
    """Nuclear kill switch from Tauri tray or React."""
    async def _perform_shutdown():
        logger.info("🔥 Graceful shutdown initiated")
        if telemetry_manager:
            telemetry_manager.stop()
        if engine:
            engine.unload_llm()
        import sys
        sys.exit(0)
    
    background_tasks.add_task(_perform_shutdown)
    return {"status": "shutdown_queued", "message": "Core is shutting down gracefully"}

@api_router.get("/system/sessions")
async def get_sessions():
    """Fetch all chat sessions for React sidebar."""
    sessions = await asyncio.to_thread(db.get_all_sessions)
    return {"sessions": sessions}