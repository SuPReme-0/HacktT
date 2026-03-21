from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
import uvicorn

from core.llm import LLMManager, llm_manager
from core.retriever import HackTRetriever, retriever
from core.embedder import embedder
from core.vision import vision_manager
from utils.memory import vram_guard
from utils.logger import get_logger

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = get_logger("hackt.main")

app = FastAPI(title="HackT Runtime API", version="1.0.0")

# Fixed Bug #7: CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production to tauri://localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fixed Bug #10: Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "details": "Contact support"}
    )

# Fixed Bug #11: Health Check
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "gpu_available": torch.cuda.is_available(),
        "vram_free_gb": vram_guard.get_free_vram_gb(),
        "llm_loaded": llm_manager.llm is not None
    }

# Pydantic Models (Fixed Bug #6)
class ChatRequest(BaseModel):
    prompt: str
    mode: str = "active"  # active | passive

class EmbedRequest(BaseModel):
    text: str

class VisionRequest(BaseModel):
    image_base64: str

# Initialize Models on Startup
@app.on_event("startup")
async def startup_event():
    global llm_manager, retriever
    llm_manager = LLMManager("models/qwen-3.5-4b-q4.gguf")
    retriever = HackTRetriever("models/indices")

# Fixed Bug #5: Embedding Endpoint
@app.post("/api/embed")
async def embed_text(request: EmbedRequest):
    try:
        vector = embedder.encode(request.text)
        return {"vector": vector.tolist()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chat Endpoint (Streaming)
@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        # 1. Embed Query
        vector = embedder.encode(request.prompt)
        # 2. Retrieve Context
        context = retriever.get_hybrid_context(request.prompt, vector)
        # 3. Stream LLM Response
        return StreamingResponse(
            llm_manager.stream_chat(request.prompt, context),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Chat processing failed")

# Vision Endpoint (On-Demand)
@app.post("/api/vision/scan")
async def scan_screen(request: VisionRequest):
    # Decode image logic here
    result = vision_manager.analyze(request.image_base64)
    vision_manager.unload()  # Free VRAM immediately
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)