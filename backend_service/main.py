"""
HackT Sovereign Core - Master Entry Point (v2.5)
=================================================
Bootstraps the FastAPI application, mounts modular routers,
and manages the lifecycle of all Sovereign AI microservices.

Features:
- Real-time boot progress via WebSocket
- Code diff broadcasting for threat fixes
- Zero circular imports, lazy service loading
- Async-aware daemon startup & graceful shutdown
- Proper telemetry manager initialization
"""

import sys
import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.config import config
from utils.logger import get_logger, log_system_info, log_shutdown
from utils.state import app_state

logger = get_logger("hackt.main")

# Core engines (safe to import early)
from core.memory import vram_guard
from core.embedder import embedder
from core.rag import retriever
from core.engine import engine
from core.database import db

# Routers
from services.http_api import api_router
from services.websocket import telemetry_router

# ----------------------------------------------------------------------
# Global reference to telemetry manager (set during lifespan)
_telemetry_manager = None

# ----------------------------------------------------------------------
async def broadcast_code_diff(threat_level: str, source: str,
                              original_code: str, suggested_fix: str) -> None:
    """
    Broadcast a suggested code fix to all connected frontend clients.
    Call this from threat_scanner when a dangerous pattern is detected.
    """
    # ✅ FIXED: Check if _telemetry_manager is initialized before use
    if _telemetry_manager is not None:
        try:
            await _telemetry_manager.broadcast_json({
                "type": "code_diff_available",
                "data": {
                    "threat_level": threat_level,
                    "source": source,
                    "original_code": original_code,
                    "suggested_fix": suggested_fix,
                    "timestamp": time.time()
                }
            })
        except Exception as e:
            logger.error(f"Failed to broadcast code diff: {e}")
    else:
        logger.debug(f"Code diff ready but telemetry bridge offline: {source}")

# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telemetry_manager

    # --- Helper for boot progress ---
    async def send_boot_progress(message: str, progress: int, level: str = "info"):
        # ✅ FIXED: Check if _telemetry_manager is initialized before use
        if _telemetry_manager is not None:
            try:
                await _telemetry_manager.broadcast_json({
                    "type": "boot_progress",
                    "message": message,
                    "progress": progress,
                    "level": level,
                    "timestamp": time.time()
                })
            except Exception as e:
                logger.error(f"Failed to send boot progress: {e}")
        else:
            logger.debug(f"Boot: {progress}% - {message}")

    # --- BOOT SEQUENCE ---
    log_system_info()
    logger.info("🚀 Booting HackT Sovereign Core...")

    try:
        # 1. VRAM detection
        vram_guard._detect_hardware()
        await send_boot_progress("Hardware mapping complete", 5)

        # 2. Start WebSocket manager (early, so frontend can receive progress)
        from services.websocket import telemetry_manager
        _telemetry_manager = telemetry_manager
        telemetry_manager.start()
        await asyncio.sleep(0.2)  # allow port to bind
        await send_boot_progress("Neural bridge established", 10)

        # 3. Database handshake
        await send_boot_progress("Mounting Sovereign Vault...", 20)
        db.initialize()   # Ensure this matches your database.py (e.g., db.initialize() if needed)

        # 4. Embedder
        if not embedder._loaded:
            embedder.load()
        await send_boot_progress("Semantic engine online", 35)

        # 5. Master LLM
        if not engine.llm:
            engine.load_llm()
        await send_boot_progress("Master LLM loaded into VRAM", 60)

        # 6. Lazy load services
        from services.idle_manager import idle_manager
        from services.port_listeners import integration_manager
        from services.screen_monitor import screen_monitor
        from services.threat_scanner import threat_scanner
        from services.code_watcher import code_watcher
        from services.audio import stt_service, tts_service

        # 7. Integration sockets
        await integration_manager.start_ide_socket(port=config.services.ide_listener_port)
        await integration_manager.start_browser_socket(port=config.services.browser_listener_port)
        await send_boot_progress("Integration ports synchronized", 75)

        # 8. Passive mode background tasks
        if config.mode == "passive":
            # Inject telemetry broadcaster into threat_scanner
            threat_scanner.inject_dependencies(
                engine, embedder, retriever,
                broadcast_callback=broadcast_code_diff
            )
            threat_scanner.start()
            screen_monitor.start(loop=asyncio.get_running_loop())
            code_watcher.start_watching(str(config.paths.data_dir.parent))
            await send_boot_progress("Passive surveillance active", 90)

        # 9. Audio services
        stt_service.load()
        tts_service.load()

        vram_usage = vram_guard.get_usage_stats().get("used_gb", 0.0)
        await send_boot_progress(
            f"Sovereign Core ONLINE ({vram_usage:.1f} GB VRAM)",
            100, level="success"
        )
        logger.info(f"✅ Sovereign Core READY on {config.host}:{config.port}")

        yield   # <--- APP RUNS HERE ---

    except Exception as e:
        logger.critical(f"🔥 Boot sequence failed: {e}", exc_info=True)
        await send_boot_progress(f"Critical Error: {str(e)[:50]}", 0, level="error")
        raise
    finally:
        # --- SHUTDOWN SEQUENCE ---
        logger.info("🛑 Commencing graceful shutdown...")
        try:
            # Safely stop background daemons using sys.modules to prevent local() scoping errors
            if 'services.idle_manager' in sys.modules:
                sys.modules['services.idle_manager'].idle_manager.stop()
            if 'services.threat_scanner' in sys.modules:
                sys.modules['services.threat_scanner'].threat_scanner.stop()
            if 'services.screen_monitor' in sys.modules:
                sys.modules['services.screen_monitor'].screen_monitor.stop()
            if 'services.code_watcher' in sys.modules:
                sys.modules['services.code_watcher'].code_watcher.stop_watching()

            # Unload models
            engine.unload_llm()
            embedder.unload()

            # Stop WebSocket last (to allow final messages)
            if _telemetry_manager is not None:
                _telemetry_manager.stop()

            # Close database
            db.close_all()
            log_shutdown()
        except Exception as e:
            logger.error(f"⚠️ Shutdown error: {e}")

# ----------------------------------------------------------------------
# FastAPI application
app = FastAPI(
    title="HackT Sovereign Core",
    description="Privacy-first, offline AI cybersecurity agent",
    version="2.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins + ["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(telemetry_router)

@app.get("/health")
async def health_check():
    # ✅ FIXED: Replaced asyncio.get_event_loop().time() with time.time() for safe endpoint querying
    return {
        "status": "healthy",
        "mode": config.mode,
        "llm_loaded": engine.llm is not None,
        "vram_usage_gb": vram_guard.get_usage_stats().get("used_gb", 0.0),
        "timestamp": time.time()
    }

# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    if "--bootstrap" in sys.argv:
        from utils.downloader import run_bootstrap
        run_bootstrap()
        sys.exit(0)

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="warning",
        workers=1,
        timeout_keep_alive=30,
        limit_concurrency=100
    )