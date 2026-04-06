"""
HackT Sovereign Core - WebSocket Service Module
================================================
Provides real-time bidirectional communication with React frontend via:
- /ws/telemetry: System metrics, threat alerts, active context
- /ws/bubble: Passive Bubble-specific audio reactivity + state sync
- Direct Python → React data flow (bypasses Tauri for heavy telemetry)
"""

import asyncio
import json
from typing import Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from utils.logger import get_logger

logger = get_logger("hackt.services.websocket")

# Router for FastAPI
telemetry_router = APIRouter()


class TelemetryManager:
    """
    Manages WebSocket connections for real-time telemetry push to React.
    
    Features:
    - Multiple client support (Dashboard + Passive Bubble)
    - Automatic reconnection handling
    - Background telemetry loop (2-second intervals)
    - Threat alert broadcasting
    - Audio reactivity stream for TTS sync
    """
    
    def __init__(self):
        self.dashboard_connections: Set[WebSocket] = set()
        self.bubble_connections: Set[WebSocket] = set()
        self.telemetry_task: Optional[asyncio.Task] = None
        self.is_running: bool = False
        self._lock = asyncio.Lock()
        
        # Telemetry cache to avoid redundant computation
        self._last_telemetry: Dict = {}
        self._last_update_time: float = 0
        
    async def connect_dashboard(self, websocket: WebSocket):
        """Register a new Dashboard WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.dashboard_connections.add(websocket)
        logger.info(f"Dashboard client connected. Total: {len(self.dashboard_connections)}")
        
        # Send initial state
        await self._send_initial_state(websocket)
    
    async def connect_bubble(self, websocket: WebSocket):
        """Register a new Passive Bubble WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.bubble_connections.add(websocket)
        logger.info(f"Bubble client connected. Total: {len(self.bubble_connections)}")
        
        # Send initial bubble state
        await self._send_bubble_state(websocket)
    
    # FIXED: Upgraded to async to support 'async with self._lock'
    async def disconnect_dashboard(self, websocket: WebSocket):
        """Remove a Dashboard WebSocket connection"""
        async with self._lock:
            self.dashboard_connections.discard(websocket)
        logger.info(f"Dashboard client disconnected. Total: {len(self.dashboard_connections)}")
    
    # FIXED: Upgraded to async
    async def disconnect_bubble(self, websocket: WebSocket):
        """Remove a Bubble WebSocket connection"""
        async with self._lock:
            self.bubble_connections.discard(websocket)
        logger.info(f"Bubble client disconnected. Total: {len(self.bubble_connections)}")
    
    async def _send_initial_state(self, websocket: WebSocket):
        """Send initial system state to newly connected Dashboard"""
        # LOCAL IMPORT: Prevents circular import crash at boot
        from main import app_state, vram_guard
        
        vram_gb = 0.0
        if vram_guard:
            vram_gb = vram_guard.get_usage_stats().get("used_gb", 0.0)

        initial_data = {
            "type": "initial_state",
            "mode": app_state.get("mode", "active"),
            "vram_usage_gb": vram_gb,
            "backend_health": app_state.get("backend_health", {}),
            "permissions": {},  # Would load from config in production
            "threat_level": "safe",
        }
        await websocket.send_json(initial_data)
    
    async def _send_bubble_state(self, websocket: WebSocket):
        """Send initial state to newly connected Passive Bubble"""
        from main import app_state
        
        bubble_data = {
            "type": "bubble_init",
            "mode": app_state.get("mode", "active"),
            "is_speaking": False,
            "audio_level": 1.0,
            "threat_level": "safe",
            "connection_status": "connected",
        }
        await websocket.send_json(bubble_data)
    
    # FIXED: Signature missing 'data:' parameter name
    async def broadcast_telemetry(self, data: Dict, target: str = "all"):
        """
        Broadcast telemetry data to connected clients.
        
        Args:
            data: Telemetry dictionary to send
            target: "dashboard", "bubble", or "all"
        """
        message = json.dumps(data)
        disconnected = []
        
        async with self._lock:
            # Send to Dashboard connections
            if target in ["dashboard", "all"]:
                for conn in self.dashboard_connections:
                    try:
                        await conn.send_text(message)
                    except WebSocketDisconnect:
                        disconnected.append((conn, "dashboard"))
                    except Exception as e:
                        logger.error(f"Dashboard broadcast failed: {e}")
                        disconnected.append((conn, "dashboard"))
            
            # Send to Bubble connections
            if target in ["bubble", "all"]:
                for conn in self.bubble_connections:
                    try:
                        await conn.send_text(message)
                    except WebSocketDisconnect:
                        disconnected.append((conn, "bubble"))
                    except Exception as e:
                        logger.error(f"Bubble broadcast failed: {e}")
                        disconnected.append((conn, "bubble"))
        
        # Clean up disconnected clients safely
        for conn, client_type in disconnected:
            if client_type == "dashboard":
                await self.disconnect_dashboard(conn)
            else:
                await self.disconnect_bubble(conn)
    
    async def send_audio_reactivity(self, is_speaking: bool, volume: float = 1.2):
        """Send TTS audio reactivity data to Bubble clients"""
        data = {
            "type": "tts",
            "is_speaking": is_speaking,
            "volume": volume if is_speaking else 1.0,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast_telemetry(data, target="bubble")
    
    async def send_threat_alert(self, threat_level: str, source: Optional[str] = None):
        """Send threat alert to all clients"""
        data = {
            "type": "threat",
            "level": threat_level,
            "source": source,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast_telemetry(data, target="all")
    
    async def send_context_update(self, context: Dict):
        """Send IDE/browser context update to Dashboard"""
        data = {
            "type": "context",
            **context,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast_telemetry(data, target="dashboard")
    
    async def telemetry_loop(self):
        """Background task: Push system telemetry every 2 seconds"""
        self.is_running = True
        
        while self.is_running:
            try:
                # LOCAL IMPORT: Safely fetch global state
                from main import app_state, vram_guard
                
                # Prevent running before system is fully booted
                if not vram_guard:
                    await asyncio.sleep(1.0)
                    continue

                # Gather system metrics (cached to avoid overload)
                current_time = asyncio.get_event_loop().time()
                if current_time - self._last_update_time < 1.5:
                    await asyncio.sleep(0.5)
                    continue
                
                vram_stats = vram_guard.get_usage_stats()
                
                # FIXED: Retrieve active_scans safely from app_state to avoid circular import with monitor.py
                active_scans = app_state.get("backend_health", {}).get("active_scans", 0)

                telemetry_data = {
                    "type": "telemetry",
                    "cpu_usage": app_state.get("backend_health", {}).get("cpu_usage", 0),
                    "memory_usage": app_state.get("backend_health", {}).get("memory_usage", 0),
                    "vram_usage_gb": vram_stats.get("used_gb", 0),
                    "vram_total_gb": vram_stats.get("total_gb", 0),
                    "active_scans": active_scans,
                    "mode": app_state.get("mode", "active"),
                    "threat_level": app_state.get("threat_level", "safe"),
                    "timestamp": current_time
                }
                
                self._last_telemetry = telemetry_data
                self._last_update_time = current_time
                
                await self.broadcast_telemetry(telemetry_data, target="dashboard")
                await asyncio.sleep(2.0)
                
            except Exception as e:
                logger.error(f"Telemetry loop error: {e}")
                await asyncio.sleep(5.0)  # Backoff on error
    
    def start(self):
        """Start the background telemetry task"""
        if self.telemetry_task is None or self.telemetry_task.done():
            self.telemetry_task = asyncio.create_task(self.telemetry_loop())
            logger.info("Telemetry manager started")
    
    def stop(self):
        """Stop the background telemetry task"""
        self.is_running = False
        if self.telemetry_task and not self.telemetry_task.done():
            self.telemetry_task.cancel()
        logger.info("Telemetry manager stopped")


# Singleton instance
telemetry_manager = TelemetryManager()


# ======================================================================
# WebSocket Endpoints
# ======================================================================

@telemetry_router.websocket("/ws/telemetry")
async def telemetry_endpoint(websocket: WebSocket):
    """WebSocket endpoint for Dashboard telemetry"""
    await telemetry_manager.connect_dashboard(websocket)
    try:
        # Keep connection alive and handle client messages
        while True:
            data = await websocket.receive_text()
            # Optional: Handle React → Python commands here
    except WebSocketDisconnect:
        # FIXED: Awaited async function
        await telemetry_manager.disconnect_dashboard(websocket)
    except Exception as e:
        logger.error(f"Telemetry WebSocket error: {e}")
        await telemetry_manager.disconnect_dashboard(websocket)


@telemetry_router.websocket("/ws/bubble")
async def bubble_endpoint(websocket: WebSocket):
    """WebSocket endpoint for Passive Bubble audio reactivity + state"""
    await telemetry_manager.connect_bubble(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Optional: Handle Bubble → Python commands
    except WebSocketDisconnect:
        await telemetry_manager.disconnect_bubble(websocket)
    except Exception as e:
        logger.error(f"Bubble WebSocket error: {e}")
        await telemetry_manager.disconnect_bubble(websocket)