"""
HackT Sovereign Core - Services Directory
==========================================
This directory contains all autonomous daemons and network services that power
the Sovereign Core. Each service is designed to run asynchronously without
blocking the main FastAPI event loop.

SERVICES OVERVIEW:
==================

1. http_api.py (HTTP API Service)
   ─────────────────────────────
   Purpose: Unified REST interface for React/Tauri frontend
   Endpoints:
   - POST /api/chat: SSE streaming chat with Vault-Aware RAG
   - POST /api/threat/scan: Manual threat scanning
   - GET /api/health: System health check
   - POST /api/system/mode: Switch Active/Passive modes
   - POST /api/system/shutdown: Graceful shutdown
   - GET /api/system/sessions: Fetch chat history for sidebar
   Key Features:
   - Server-Sent Events (SSE) for real-time token streaming
   - Background task delegation for SQLite writes
   - Vault intent classification before RAG retrieval
   - Context window protection (history pruning)

2. websocket.py (WebSocket Telemetry Manager)
   ─────────────────────────────────────────
   Purpose: Central nervous system for real-time backend→frontend communication
   Endpoints:
   - WS /ws/telemetry: Dashboard stats, threat alerts, context updates
   - WS /ws/bubble: Binary audio streaming, ducking signals, voice commands
   Key Features:
   - Dual-track connections (Dashboard vs. Voice Bubble)
   - Binary WAV audio streaming (bypasses Python sounddevice)
   - Full-duplex audio ducking signals
   - Thread-safe connection management with asyncio.Lock()
   - Background telemetry loop (2-second intervals)
   - Command listener for UI→Backend communication

3. threat_scanner.py (Background Threat Detection)
   ─────────────────────────────────────────────
   Purpose: Continuous non-blocking monitoring of IDE/Browser contexts
   Features:
   - Runs every 10 seconds (configurable)
   - Fast keyword filter (CPU only, 0 VRAM)
   - Deep RAG analysis with Vault-Aware routing
   - UI Diff Bridge (sends original_code + suggested_fix)
   - Async thread offloading for all hardware calls
   - Content hash caching (skips unchanged files)
   Integration:
   - Reads from port_listeners.py contexts
   - Alerts via websocket.py telemetry_manager
   - Uses orchestrator.py for ChatML formatting

4. audio.py (Neural Audio Service)
   ──────────────────────────────
   Purpose: CPU-optimized Full-Duplex voice processing
   Components:
   - STTService: Faster-Whisper streaming with VAD
   - TTSService: Piper TTS with prosodic intelligence
   Key Features:
   - Audio ducking (lowers AI volume when user speaks)
   - Extended VAD (2.5s silence limit for natural pauses)
   - Anti-hallucination conditioning
   - Pure in-memory synthesis (zero disk I/O)
   - PyInstaller-safe pathing
   Integration:
   - Streams audio via websocket.py broadcast_audio()
   - Sends ducking signals via send_audio_ducking()

5. code_watcher.py (IDE Integration)
   ────────────────────────────────
   Purpose: Real-time file system monitoring for active project files
   Features:
   - Watchdog-based file system observer
   - Debounced processing (1-second delay after saves)
   - VRAM-safe context truncation (max 3000 chars)
   - Top/Bottom file slicing for large files
   - Active context tracking with timestamps
   Integration:
   - Provides context to threat_scanner.py
   - Broadcasts updates via websocket.py
   - Receives fix payloads from http_api.py

6. screen_monitor.py (Passive Vision Daemon)
   ───────────────────────────────────────
   Purpose: Background screen monitoring for Passive Mode
   Features:
   - Ultra-fast pixel differencing (100x100 grayscale)
   - Skips OCR if screen hasn't changed
   - VRAM collision avoidance (yields if LLM is busy)
   - Fast keyword filtering for threat detection
   - Thread-safe alert broadcasting
   Integration:
   - Uses core/engine.py for Florence-2 OCR
   - Alerts via websocket.py telemetry_manager
   - Respects vram_guard constraints

7. screen.py (On-Demand Screen Analyzer)
   ───────────────────────────────────
   Purpose: Manual screen capture and Florence-2 analysis
   Features:
   - Cross-platform screen capture (mss)
   - Task routing (OCR, Object Detection, Captioning)
   - Async PyTorch offloading (asyncio.to_thread)
   - Structured output parsing for React UI
   Integration:
   - Called by http_api.py endpoints
   - Uses core/engine.py for ephemeral vision

8. idle_manager.py (Autonomous Engagement)
   ─────────────────────────────────────
   Purpose: "JARVIS-like" ambient voice status updates
   Features:
   - Hardware-aware (monitors CPU, RAM, VRAM)
   - OCR integration for long-running tasks
   - VRAM-safe visual cortex bypass
   - Dynamic cooldowns (4-25 minutes based on load)
   - Audio delegation to React via WebSocket
   Integration:
   - Uses orchestrator.py for prompt routing
   - Streams audio via websocket.py broadcast_audio()
   - Records activity from http_api.py chat endpoint

9. port_listeners.py (External Integration)
   ──────────────────────────────────────
   Purpose: WebSocket servers for IDE and Browser extensions
   Ports:
   - 8081: IDE integration (VS Code / JetBrains)
   - 8082: Browser proxy (Chrome extension)
   Features:
   - Bidirectional communication with extensions
   - Real-time code context streaming
   - Terminal log tracking for hack attempt detection
   - Content truncation security (10k chars code, 5k DOM)
   - Async hardware offloading (asyncio.to_thread)
   Integration:
   - Provides contexts to threat_scanner.py
   - Uses orchestrator.py for threat assessment
   - Alerts via websocket.py telemetry_manager

10. query.py (Legacy - DEPRECATED)
    ─────────────────────────────
    Status: Merged into http_api.py
    Reason: Consolidated all HTTP endpoints into single service
    Action: Do not use. Use http_api.py instead.

ARCHITECTURAL PATTERNS:
=======================

1. Async Thread Offloading:
   All hardware calls (PyTorch, LanceDB, llama.cpp) are wrapped in
   asyncio.to_thread() to prevent blocking the FastAPI event loop.

2. Dependency Injection:
   Services import directly from core/ modules, never from main.py,
   to prevent circular import crashes during PyInstaller compilation.

3. WebSocket Telemetry:
   All background daemons push updates through telemetry_manager
   instead of direct HTTP polling, enabling real-time UI updates.

4. Vault-Aware Routing:
   All RAG queries pass through orchestrator.classify_vault_intent()
   to ensure proper vault separation and prevent hallucination.

5. Background Task Delegation:
   SQLite writes and non-critical operations use FastAPI's
   BackgroundTasks to free the response stream immediately.

STARTUP SEQUENCE:
=================
1. main.py imports all services
2. telemetry_manager.start() begins telemetry loop
3. integration_manager.start_ide_socket(8081)
4. integration_manager.start_browser_socket(8082)
5. threat_scanner.start() (if Passive Mode)
6. screen_monitor.start(loop) (if Passive Mode)
7. idle_manager.start() (if Passive Mode)
8. stt_service.start_listening(loop)
9. uvicorn.run() starts FastAPI server

SHUTDOWN SEQUENCE:
==================
1. telemetry_manager.stop()
2. threat_scanner.stop()
3. screen_monitor.stop()
4. idle_manager.stop()
5. stt_service.stop_listening()
6. integration_manager.stop_ide_socket()
7. integration_manager.stop_browser_socket()
8. engine.unload_llm()
9. sys.exit(0)
"""

# Export all service singletons for easy import
from services.websocket import telemetry_manager, telemetry_router
from services.http_api import api_router
from services.threat_scanner import threat_scanner
from services.audio import stt_service, tts_service
from services.code_watcher import code_watcher
from services.screen_monitor import screen_monitor
from services.screen import screen_analyzer
from services.idle_manager import idle_manager
from services.port_listeners import integration_manager

__all__ = [
    "telemetry_manager",
    "telemetry_router",
    "api_router",
    "threat_scanner",
    "stt_service",
    "tts_service",
    "code_watcher",
    "screen_monitor",
    "screen_analyzer",
    "idle_manager",
    "integration_manager",
]