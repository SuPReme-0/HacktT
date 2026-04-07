"""
HackT Sovereign Core - Shared State Manager
============================================
Thread-safe global state container for runtime flags.
Prevents circular imports with main.py while allowing services to share state.
"""
import threading
from typing import Dict, Any

class AppState:
    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            "mode": "active",
            "threat_level": "safe",
            "backend_health": {
                "cpu_usage": 0.0,
                "memory_usage": 0.0,
                "active_scans": 0
            },
            "is_shutting_down": False
        }

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any):
        with self._lock:
            self._state[key] = value

    def update_health(self, cpu: float, ram: float, scans: int):
        with self._lock:
            self._state["backend_health"] = {
                "cpu_usage": cpu,
                "memory_usage": ram,
                "active_scans": scans
            }

    def shutdown(self):
        with self._lock:
            self._state["is_shutting_down"] = True

    @property
    def is_shutting_down(self) -> bool:
        with self._lock:
            return self._state.get("is_shutting_down", False)

# Singleton
app_state = AppState()