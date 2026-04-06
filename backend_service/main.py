"""
HackT Sovereign Core - Master Entry Point
==========================================
Bootstraps the FastAPI application, mounts modular routers, 
and manages the lifecycle of all Sovereign AI microservices.
"""

import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Utilities
from utils.config import config
from utils.logger import get_logger, log_system_info

# 2. Core Engines (Importing the singletons)
from core.memory import vram_guard
from core.embedder import embedder
from core.rag import retriever
from core.engine import engine

logger = get_logger("hackt.main")

# ======================================================================
# Global State (Exported for services/ local imports)
# ======================================================================
app_state = {
    "mode": config.mode,
    "threat_level": "safe",
    "backend_health": {
        "cpu_usage": 0,
        "memory_usage": 0,
        "active_scans": 0
    }
}

# ======================================================================
# Lifespan Manager (Startup & Teardown Sequences)
# ======================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Orchestrates the boot sequence of the Sovereign Agent"""
    
    # --- BOOT SEQUENCE ---
    log_system_info()
    logger.info("🚀 Booting HackT Sovereign Core...")
    
    # 1. Warm up the VRAM Gatekeeper
    vram_guard._detect_hardware()
    
    # 2. Pre-load the Master LLM (if VRAM allows)
    engine.load_llm()
    
    # 3. Wake up the Background Daemons
    from services.websocket import telemetry_manager
    from services.idle_manager import idle_manager
    from services.port_listeners import integration_manager
    from services.monitor import screen_monitor
    
    # Start WebSockets & Telemetry
    telemetry_manager.start()
    
    # Start Autonomous Engagement (JARVIS voice)
    idle_manager.start()
    
    # Open native ports for VS Code & Chrome Extensions
    await integration_manager.start_ide_socket(port=8081)
    await integration_manager.start_browser_socket(port=8082)
    
    # Start vision monitoring if booting into Passive Mode
    if config.mode == "passive":
        screen_monitor.start()
        
    logger.info(f"✅ Sovereign Core ONLINE on port {config.port}. Awaiting Tauri Frontend...")
    
    yield  # --- APP RUNS HERE ---
    
    # --- SHUTDOWN SEQUENCE ---
    logger.info("🛑 Commencing shutdown sequence...")
    
    # 1. Stop all daemons and listeners
    telemetry_manager.stop()
    idle_manager.stop()
    screen_monitor.stop()
    await integration_manager.stop_ide_socket()
    await integration_manager.stop_browser_socket()
    
    # 2. Flush AI Models from VRAM safely
    engine.unload_vision()
    engine.unload_llm()
    embedder.unload()
    vram_guard.emergency_cleanup()
    
    logger.info("✅ Shutdown complete. System secure.")

# ======================================================================
# FastAPI Application & Routing
# ======================================================================
app = FastAPI(
    title="HackT Sovereign Core", 
    version="1.0.0", 
    lifespan=lifespan
)

# Cross-Origin Resource Sharing (Allows Tauri to talk to Python)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the modular routers we built!
from services.http_api import api_router
from services.websocket import telemetry_router

app.include_router(api_router, prefix="/api")
app.include_router(telemetry_router)

# ======================================================================
# Server Execution
# ======================================================================
if __name__ == "__main__":
    import uvicorn
    # uvicorn runs the web server. We pull host/port dynamically from config.
    uvicorn.run(
        "main:app", 
        host=config.host, 
        port=config.port, 
        reload=config.reload,
        log_level="warning" # Keeps uvicorn quiet so our custom logger shines
    )