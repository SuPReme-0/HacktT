"""
HackT Sovereign Core - WebSocket Service Module (v4.0)
======================================================
The Central Nervous System for React Communication.
Features:
- Dual-Track Connections (Dashboard Stats vs. Voice Bubble)
- Binary Audio Streaming (WAV bytes via WebSocket)
- Full-Duplex Audio Ducking Signals
- Command Listener (For Voice Confirmation of Diffs)
- Thread-Safe Connection Management
"""

import asyncio
import json
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, APIRouter

from utils.logger import get_logger
from core.memory import vram_guard
from utils.config import config

logger = get_logger("hackt.services.websocket")

telemetry_router = APIRouter()

class TelemetryManager:
    """
    Manages WebSocket connections for real-time telemetry and binary audio push.
    Thread-safe via asyncio.Lock().
    """
    
    def __init__(self):
        self.dashboard_connections: Set[WebSocket] = set()
        self.bubble_connections: Set[WebSocket] = set()
        self.telemetry_task: Optional[asyncio.Task] = None
        self.is_running: bool = False
        self._lock = asyncio.Lock()
        
    # ======================================================================
    # Connection Management
    # ======================================================================
    async def connect_dashboard(self, websocket: WebSocket):
        """Register a new Dashboard WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.dashboard_connections.add(websocket)
        logger.info(f"Dashboard client connected. Total: {len(self.dashboard_connections)}")
        await self._send_initial_state(websocket)
    
    async def connect_bubble(self, websocket: WebSocket):
        """Register a new Passive Bubble WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.bubble_connections.add(websocket)
        logger.info(f"Bubble client connected. Total: {len(self.bubble_connections)}")
        
    async def disconnect_dashboard(self, websocket: WebSocket):
        """Remove a Dashboard WebSocket connection."""
        async with self._lock:
            self.dashboard_connections.discard(websocket)
        logger.info("Dashboard client disconnected.")
    
    async def disconnect_bubble(self, websocket: WebSocket):
        """Remove a Bubble WebSocket connection."""
        async with self._lock:
            self.bubble_connections.discard(websocket)
        logger.info("Bubble client disconnected.")

    # ======================================================================
    # Broadcasters (JSON & Binary)
    # ======================================================================
    async def broadcast_telemetry(self, data: Dict, target: str = "all"):
        """Broadcast JSON data safely to specified targets."""
        message = json.dumps(data)
        disconnected = []
        
        async with self._lock:
            if target in ["dashboard", "all"]:
                for conn in self.dashboard_connections:
                    try:
                        await conn.send_text(message)
                    except Exception:
                        disconnected.append((conn, "dashboard"))
            
            if target in ["bubble", "all"]:
                for conn in self.bubble_connections:
                    try:
                        await conn.send_text(message)
                    except Exception:
                        disconnected.append((conn, "bubble"))
        
        # Cleanup dead connections
        for conn, client_type in disconnected:
            if client_type == "dashboard":
                await self.disconnect_dashboard(conn)
            else:
                await self.disconnect_bubble(conn)

    async def broadcast_audio(self, wav_bytes: bytes):
        """
        🚨 CRITICAL: Streams raw binary WAV data strictly to the Bubble UI.
        Bypasses Python's blocking sounddevice library.
        """
        # 1. Send Header so React knows binary is coming
        await self.broadcast_telemetry({"type": "incoming_audio", "format": "wav"}, target="bubble")
        
        disconnected = []
        async with self._lock:
            for conn in self.bubble_connections:
                try:
                    await conn.send_bytes(wav_bytes)
                except Exception:
                    disconnected.append((conn, "bubble"))
                    
        for conn, _ in disconnected:
            await self.disconnect_bubble(conn)

    async def broadcast_json(self, data: Dict):
        """
        Broadcast arbitrary JSON payload to all connections.
        Used for Code Diff Bridge and custom events.
        """
        await self.broadcast_telemetry(data, target="all")

    # ======================================================================
    # Domain-Specific Event Triggers
    # ======================================================================
    async def _send_initial_state(self, websocket: WebSocket):
        """Send initial system state to newly connected Dashboard."""
        vram_gb = vram_guard.get_usage_stats().get("used_gb", 0.0)
        await websocket.send_json({
            "type": "initial_state",
            "mode": config.mode,
            "vram_usage_gb": vram_gb,
            "threat_level": "safe",
        })

    async def send_audio_reactivity(self, is_speaking: bool, volume: float = 1.0):
        """Used by Idle Manager to pulse the UI bubble."""
        await self.broadcast_telemetry({
            "type": "tts",
            "is_speaking": is_speaking,
            "volume": volume,
            "timestamp": asyncio.get_event_loop().time()
        }, target="bubble")

    async def send_audio_ducking(self, volume: float = 0.2):
        """
        🚀 FULL-DUPLEX SUPPORT: Tells React to lower AI volume when user speaks.
        """
        await self.broadcast_telemetry({
            "type": "audio_ducking",
            "volume": volume,
            "timestamp": asyncio.get_event_loop().time()
        }, target="bubble")
    
    async def send_threat_alert(self, threat_level: str, source: Optional[str] = None, 
                                 description: str = "", diff_data: Optional[Dict] = None):
        """
        Sends threat alert. If diff_data is present, triggers the Code Diff Modal.
        """
        payload = {
            "type": "threat",
            "level": threat_level,
            "source": source,
            "description": description,
            "timestamp": asyncio.get_event_loop().time()
        }
        if diff_data:
            payload["diff"] = diff_data  # Contains original_code, suggested_fix
            
        await self.broadcast_telemetry(payload, target="all")
    
    async def send_context_update(self, context: Dict):
        """Send IDE/browser context update to Dashboard."""
        await self.broadcast_telemetry({
            "type": "context",
            **context,
            "timestamp": asyncio.get_event_loop().time()
        }, target="dashboard")

    # ======================================================================
    # Background Telemetry Loop
    # ======================================================================
    async def telemetry_loop(self):
        """Pushes CPU/RAM/VRAM stats using native libraries."""
        self.is_running = True
        try:
            import psutil
            psutil_available = True
        except ImportError:
            psutil_available = False
        
        while self.is_running:
            try:
                cpu_usage = psutil.cpu_percent(interval=None) if psutil_available else 0.0
                ram_usage = psutil.virtual_memory().percent if psutil_available else 0.0
                vram_stats = vram_guard.get_usage_stats()
                
                telemetry_data = {
                    "type": "telemetry",
                    "cpu_usage": cpu_usage,
                    "memory_usage": ram_usage,
                    "vram_usage_gb": vram_stats.get("used_gb", 0),
                    "vram_total_gb": vram_stats.get("total_gb", 0),
                    "mode": config.mode,
                    "vram_usage_percent": vram_stats.get("used_percent", 0),
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                await self.broadcast_telemetry(telemetry_data, target="dashboard")
                await asyncio.sleep(2.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telemetry loop error: {e}")
                await asyncio.sleep(5.0) 

    def start(self):
        """Start the background telemetry task."""
        if self.telemetry_task is None or self.telemetry_task.done():
            self.telemetry_task = asyncio.create_task(self.telemetry_loop())
            logger.info("Telemetry manager started")
    
    def stop(self):
        """Stop the background telemetry task."""
        self.is_running = False
        if self.telemetry_task and not self.telemetry_task.done():
            self.telemetry_task.cancel()

# Singleton instance
telemetry_manager = TelemetryManager()

# ======================================================================
# WebSocket Endpoints
# ======================================================================
@telemetry_router.websocket("/ws/telemetry")
async def telemetry_endpoint(websocket: WebSocket):
    """Dashboard Connection: Receives Stats, Sends Commands."""
    await telemetry_manager.connect_dashboard(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 🚀 COMMAND LISTENER: Handle UI -> Backend commands
            try:
                msg = json.loads(data)
                if msg.get("type") == "command":
                    logger.info(f"Received UI Command: {msg.get('action')}")
                    # Example: if msg.get('action') == 'apply_fix': trigger code injection
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await telemetry_manager.disconnect_dashboard(websocket)

@telemetry_router.websocket("/ws/bubble")
async def bubble_endpoint(websocket: WebSocket):
    """Voice Bubble Connection: Receives Audio/Ducking, Sends Voice Commands."""
    await telemetry_manager.connect_bubble(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 🚀 VOICE COMMAND LISTENER
            try:
                msg = json.loads(data)
                if msg.get("type") == "voice_command":
                    logger.info(f"Received Voice Command: {msg.get('text')}")
                    # Route to query engine for processing
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await telemetry_manager.disconnect_bubble(websocket)