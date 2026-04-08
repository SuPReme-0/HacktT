"""
HackT Sovereign Core - Dedicated Chat Service
==================================================
Handles the heavy intelligence pipeline: 
Classification -> Retrieval -> Prompt Routing -> Streaming -> DB Saving.
"""

import asyncio
import json
import time
from typing import AsyncGenerator, Dict, List
import numpy as np

from utils.logger import get_logger
from core.engine import engine
from core.embedder import embedder
from core.rag import retriever
from core.database import db
from prompts.orchestrator import orchestrator

logger = get_logger("hackt.services.chat")

class ChatService:
    def _format_citations(self, chunks: List[Dict]) -> List[str]:
        """Format RAG chunks into citation strings."""
        citations = []
        for chunk in chunks[:3]:
            source = chunk.get("source", "unknown")
            vault_id = chunk.get("vault_id", 0)
            vault_name = {1: "Library", 2: "Laboratory", 3: "Showroom"}.get(vault_id, "Unknown")
            citations.append(f"[{vault_name}] {source}")
        return citations

    def _inject_history(self, base_prompt: str, history: List[Dict]) -> str:
        """Injects historical turns cleanly into the ChatML structure."""
        if not history:
            return base_prompt
        
        parts = base_prompt.split("<|im_start|>user\n")
        if len(parts) < 2:
            return base_prompt
        
        history_str = ""
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_str += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        
        return f"{parts[0]}{history_str}<|im_start|>user\n{parts[1]}"

    async def generate_stream(self, prompt: str, mode: str, session_id: str, query_type: str, project_context: str = None, vector: List[float] = None) -> AsyncGenerator[str, None]:
        """The core streaming generator that yields SSE tokens."""
        
        # 1. Vault Intent Classification
        target_vault = orchestrator.classify_vault_intent(prompt)
        
        # 2. Async RAG Pipeline
        try:
            if vector is None:
                query_vector = await asyncio.to_thread(embedder.encode, prompt)
            else:
                query_vector = np.array(vector)
            
            retrieved_chunks = await asyncio.to_thread(
                retriever.retrieve,
                query=prompt,
                query_vector=query_vector,
                mode=mode,
                query_type=query_type,
                target_vault=target_vault
            )
            citations = self._format_citations(retrieved_chunks)
        except Exception as e:
            logger.error(f"RAG pipeline failed: {e}")
            retrieved_chunks, citations = [], []
        
        # 3. Dynamic Prompt Routing
        system_state = {"Project Context": project_context} if project_context else None
        route_data = orchestrator.route(
            query=prompt,
            mode=mode,
            query_type=query_type,
            retrieved_chunks=retrieved_chunks,
            system_state=system_state
        )
        
        # 4. History Injection & Context Window Safety
        try:
            history = await asyncio.to_thread(db.get_session_history, session_id, max_turns=8)
        except Exception as e:
            logger.warning(f"History fetch failed: {e}")
            history = []
        
        final_prompt = self._inject_history(route_data["prompt"], history)
        
        if len(final_prompt) > 12000:
            logger.warning("Context approaching limit. Pruning history.")
            final_prompt = self._inject_history(route_data["prompt"], history[-2:])

        # 5. Token Generation and Streaming
        full_response = ""
        try:
            for token in engine.stream_chat(prompt=final_prompt, max_tokens=route_data["max_tokens"]):
                full_response += token
                
                # Format as strict SSE JSON
                token_data = {
                    "token": token,
                    "status": "generating",
                    "citations": citations,
                    "timestamp": time.time()
                }
                yield f"data: {json.dumps(token_data)}\n\n"
                await asyncio.sleep(0.001) 
                
            # Final token
            yield f"data: {json.dumps({'token': '', 'status': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'token': '[ERROR]', 'status': 'error'})}\n\n"
        finally:
            # 6. Save Conversation safely in the background
            if len(full_response) > 5:
                asyncio.create_task(asyncio.to_thread(
                    db.save_turn, session_id, prompt, full_response
                ))

# Instantiate the singleton
chat_service = ChatService()