"""
HackT Sovereign Core - Master Entry Point (v2.1)
=================================================
Bootstraps the FastAPI application, mounts modular routers,
and manages the lifecycle of all Sovereign AI microservices.

Features:
- Zero Circular Imports (State decoupled, lazy service imports inside lifespan)
- Async-Aware Daemon Startup (Proper event loop handling)
- Native Uvicorn Signal Handling (Clean SIGTERM/SIGINT teardown)
- PyInstaller-Safe Path Resolution
- Bootstrap Flag Intercept for Model Downloader
"""

import sys
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ======================================================================
# 1. Utilities (Safe to import early)
# ======================================================================
from utils.config import config
from utils.logger import get_logger, log_system_info, log_shutdown
from utils.state import app_state  # Runtime mutable state (Global state lives here now)

logger = get_logger("hackt.main")

# ======================================================================
# 2. Core Engines (Singletons - Safe to import)
# ======================================================================
from core.memory import vram_guard
from core.embedder import embedder
from core.rag import retriever
from core.engine import engine
from core.database import db

# ======================================================================
# 3. Mount Routers (Safe now because main.py holds no state)
# ======================================================================
from services.http_api import api_router
from services.websocket import telemetry_router


# ======================================================================
# 4. Lifespan Manager (Startup & Teardown Sequences)
# ======================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Orchestrates the boot sequence of the Sovereign Agent.
    All heavy service imports are lazy-loaded inside this function to prevent 
    circular dependency crashes during PyInstaller compilation.
    """
    
    # --- BOOT SEQUENCE ---
    log_system_info()
    logger.info("🚀 Booting HackT Sovereign Core...")
    
    try:
        # 1. Warm up the VRAM Gatekeeper
        vram_guard._detect_hardware()
        
        # 2. Pre-load the Embedder for zero-latency voice mode
        if not embedder._loaded:
            embedder.load()
        
        # 3. Pre-load the Master LLM (if VRAM allows)
        if not engine.llm:
            engine.load_llm()
        
        # 4. Initialize Database Schema
        db._initialize_database()
        
        # ==================================================================
        # LAZY IMPORTS: Import services ONLY after core engines are ready
        # ==================================================================
        from services.websocket import telemetry_manager
        from services.idle_manager import idle_manager
        from services.port_listeners import integration_manager
        from services.screen_monitor import screen_monitor
        from services.threat_scanner import threat_scanner
        from services.code_watcher import code_watcher
        from services.audio import stt_service, tts_service
        
        # 5. Start WebSocket Telemetry Manager
        telemetry_manager.start()
        
        # 6. Start Autonomous Engagement (JARVIS voice logic)
        idle_manager.start()
        
        # 7. Open native ports for VS Code & Chrome Extensions
        await integration_manager.start_ide_socket(port=config.services.ide_listener_port)
        await integration_manager.start_browser_socket(port=config.services.browser_listener_port)
        
        # 8. Start Background Threat Scanner (if in Passive Mode)
        if config.mode == "passive":
            # Inject dependencies explicitly to avoid circular imports
            threat_scanner.inject_dependencies(engine, embedder, retriever)
            threat_scanner.start()
            
            screen_monitor.start(loop=asyncio.get_running_loop())
            
            # Start code watching for the user's project directory
            project_dir = config.paths.data_dir.parent 
            code_watcher.start_watching(str(project_dir))
        
        # 9. Initialize Audio Services (CPU-only, so safe to start anytime)
        stt_service.load()  
        tts_service.load()  
        
        logger.info(f"✅ Sovereign Core ONLINE on {config.host}:{config.port}. Awaiting Tauri Frontend...")
        
        # Uvicorn natively handles SIGINT/SIGTERM and will pause here.
        yield  # --- APP RUNS HERE ---
        
    except Exception as e:
        logger.critical(f"🔥 Boot sequence failed: {e}", exc_info=True)
        await _emergency_shutdown()
        raise
    
    # --- SHUTDOWN SEQUENCE ---
    # Uvicorn automatically triggers this block when you press Ctrl+C
    logger.info("🛑 Commencing graceful shutdown sequence...")
    
    try:
        # 1. Stop all background daemons
        telemetry_manager.stop()
        idle_manager.stop()
        threat_scanner.stop()
        screen_monitor.stop()
        code_watcher.stop_watching()
        
        # 2. Close external integration ports
        await integration_manager.stop_ide_socket()
        await integration_manager.stop_browser_socket()
        
        # 3. Unload audio models (free CPU RAM)
        stt_service.unload()
        tts_service.unload()
        
        # 4. Flush AI Models from VRAM safely
        engine.unload_llm()
        if hasattr(engine, 'unload_vision'):
            engine.unload_vision()
        embedder.unload()
        
        # 5. Close database connections
        db.close_all()
        
        # 6. Final VRAM cleanup
        vram_guard.clear_cache()
        
        # 7. Log shutdown completion
        log_shutdown()
        
    except Exception as e:
        logger.error(f"⚠️ Shutdown sequence encountered error: {e}", exc_info=True)


async def _emergency_shutdown():
    """Emergency cleanup if boot sequence fails mid-flight."""
    logger.warning("🚨 Emergency shutdown triggered")
    try:
        vram_guard.clear_cache()
        db.close_all()
    except Exception as e:
        logger.error(f"Emergency cleanup failed: {e}")


# ======================================================================
# 5. FastAPI Application & Routing
# ======================================================================
app = FastAPI(
    title="HackT Sovereign Core",
    description="Privacy-first, offline AI cybersecurity agent",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",  
    redoc_url="/redoc",  
    openapi_url="/openapi.json"
)

# Cross-Origin Resource Sharing (Allows Tauri/React to talk to Python)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the routers
app.include_router(api_router, prefix="/api")
app.include_router(telemetry_router)

# Health check endpoint for load balancers / Tauri
@app.get("/health")
async def health_check():
    """Quick health check for frontend polling."""
    return {
        "status": "healthy",
        "mode": config.mode,
        "llm_loaded": engine.llm is not None,
        "vram_usage_gb": vram_guard.get_usage_stats().get("used_gb", 0.0),
        "timestamp": asyncio.get_event_loop().time()
    }


# ======================================================================
# 6. Server Execution & Bootstrap Intercept
# ======================================================================
if __name__ == "__main__":
    import uvicorn
    
    # 🚨 THE SETUP WIZARD INTERCEPTOR 🚨
    # If Tauri calls this with --bootstrap, run the downloader and exit.
    # MUST BE BEFORE uvicorn.run() WHICH BLOCKS FOREVER
    if "--bootstrap" in sys.argv:
        from utils.downloader import run_bootstrap
        run_bootstrap()
        sys.exit(0)  # Close the process successfully when done!
    
    # Normal execution: Run the web server
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,  # No hot reload in production
        log_level="warning",  # Keep uvicorn quiet so our custom logger shines
        workers=1,  # Single worker strictly enforced to prevent VRAM contention
        timeout_keep_alive=30,
        limit_concurrency=100
    )