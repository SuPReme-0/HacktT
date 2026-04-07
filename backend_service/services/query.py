"""
HackT Sovereign Core - Query Orchestrator (v4.0)
================================================
Industry-grade Streaming Gateway connecting:
- FastAPI WebSockets / SSE
- Vault-Aware Intent Classification 
- Adaptive RAG Retriever (Native Hybrid)
- Dynamic Prompt Orchestrator
- Persistent SQLite Database (History)
"""

import asyncio
import logging
from typing import Dict, List, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.engine import engine
from core.rag import retriever
from core.embedder import embedder
from prompts.orchestrator import orchestrator  
from core.database import db  

logger = logging.getLogger("hackt.services.query")
query_router = APIRouter()

# ==============================================================================
# Pydantic Models
# ==============================================================================
class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field(default="active", pattern="^(active|passive)$")
    query_type: str = Field(default="chat")  
    project_context: Optional[str] = None
    threat_level: str = "NONE"
    session_id: str = Field(default="default_session")
    stream: bool = Field(default=True)

class ChatToken(BaseModel):
    token: str
    status: str = "generating"

# ==============================================================================
# Prompt Formatting
# ==============================================================================
def inject_history_to_chatml(base_prompt: str, history: List[Dict[str, str]]) -> str:
    """Injects historical turns into the Orchestrator's ChatML payload."""
    if not history:
        return base_prompt
        
    parts = base_prompt.split("<|im_start|>user\n")
    if len(parts) != 2:
        return base_prompt 
        
    history_str = ""
    for msg in history:
        history_str += f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>\n"
        
    return f"{parts[0]}{history_str}<|im_start|>user\n{parts[1]}"

# ==============================================================================
# The Core Orchestrator Endpoint
# ==============================================================================
@query_router.post("/chat")
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """Main Gateway: Classifies -> Embeds -> Retrieves -> Routes -> Streams -> Saves"""
    
    if not engine.llm and not engine.load_llm():
        raise HTTPException(status_code=503, detail="VRAM exhausted. Cannot load LLM.")

    # 🚀 1. VAULT INTENT CLASSIFICATION
    # Decide if this belongs to the Library (Docs) or Laboratory (Exploits/Code)
    target_vault = orchestrator.classify_vault_intent(request.prompt)

    try:
        # 🚀 2. ASYNC RAG PIPELINE (Now with Vault Routing)
        query_vector = await asyncio.to_thread(embedder.encode, request.prompt)
        retrieved_chunks = await asyncio.to_thread(
            retriever.retrieve, 
            query=request.prompt, 
            query_vector=query_vector, 
            mode=request.mode, 
            query_type=request.query_type,
            target_vault=target_vault  # 🔥 THE MISSING LINK APPLIED
        )
    except Exception as e:
        logger.error(f"Retrieval pipeline failed: {e}")
        retrieved_chunks = []

    # 🚀 3. DYNAMIC PROMPT ROUTING
    # We pass the targeted chunks into the Orchestrator to format the ChatML
    route_data = orchestrator.route(
        query=request.prompt,
        mode=request.mode,
        query_type=request.query_type,
        retrieved_chunks=retrieved_chunks,
        system_state={"Project Context": request.project_context, "Threat Level": request.threat_level} if request.project_context else None
    )

    # 🚀 4. HISTORY INJECTION (SQLite via Background Threading)
    history = await asyncio.to_thread(db.get_session_history, request.session_id, max_turns=10)
    final_prompt = inject_history_to_chatml(route_data["prompt"], history)

    # 🚀 5. SSE STREAMING GENERATOR
    async def sse_generator() -> AsyncGenerator[str, None]:
        full_response = ""
        try:
            for token in engine.stream_chat(prompt=final_prompt, max_tokens=route_data["max_tokens"]):
                full_response += token
                yield f"data: {ChatToken(token=token).model_dump_json()}\n\n"
                await asyncio.sleep(0.001) 
                
            yield f"data: {ChatToken(token='', status='done').model_dump_json()}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {ChatToken(token='[ERROR]', status='error').model_dump_json()}\n\n"
        finally:
            if full_response:
                # Delegate SQLite save to FastAPI's non-blocking background workers
                background_tasks.add_task(db.save_turn, request.session_id, request.prompt, full_response, token_count=len(full_response) // 4)

    if request.stream:
        return StreamingResponse(sse_generator(), media_type="text/event-stream", background=background_tasks)
    else:
        raise HTTPException(status_code=400, detail="Only streaming mode is supported.")