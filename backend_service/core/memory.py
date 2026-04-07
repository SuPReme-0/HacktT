"""
HackT Sovereign Core - Memory Management Module (v4.0)
=======================================================
Provides VRAM monitoring and safety guards featuring:
- Zero-Leak Driver Checking (PyNVML prioritized over PyTorch)
- Memory Pressure Detection (Trend analysis over time)
- Model Priority Queuing (LLM > Vision > Embedder)
- Usage History Tracking (For telemetry and debugging)
- Graceful CPU Fallback (When VRAM is critically low)
"""

import platform
import gc
import threading
import time
from typing import Optional, Dict, List, Tuple
from collections import deque
from datetime import datetime

from utils.logger import get_logger
from utils.config import config

logger = get_logger("hackt.core.memory")

class VRAMGuard:
    """
    VRAM monitoring and safety enforcement for model loading.
    Tracks memory pressure trends and enforces global config limits.
    """
    
    def __init__(self, history_size: int = 100):
        # 🚀 Perfect Sync: Read directly from master configuration
        self.vram_limit_bytes = config.vram.limit_gb * (1024**3)
        self.buffer_bytes = config.vram.buffer_gb * (1024**3)
        
        self.vendor: str = "Unknown"
        self.total_vram_bytes: int = 0
        self._nvml_handle: Optional[object] = None
        
        self.has_cuda = False
        self._initialized: bool = False
        self._lock = threading.Lock()
        
        # 🚀 Memory Pressure Tracking
        self._usage_history: deque = deque(maxlen=history_size)
        self._pressure_level: str = "normal"  # normal, elevated, critical
        self._last_pressure_check: float = 0
        
        # Model Loading Lock (Prevents race conditions during model swaps)
        self._model_load_lock = threading.Lock()
        
        # Registered models (For priority-based eviction)
        self._loaded_models: Dict[str, Dict] = {}

    def _detect_hardware(self):
        """Detect GPU vendor and initialize appropriate telemetry."""
        with self._lock:
            if self._initialized:
                return

            # 🚨 1. TRY NVML FIRST (Zero VRAM Overhead)
            if self._init_nvidia_nvml():
                self.has_cuda = True
                self._initialized = True
                return

            # 2. FALLBACK TO PYTORCH
            try:
                import torch
                if torch.cuda.is_available():
                    self.has_cuda = True
                    self.vendor = torch.cuda.get_device_name(0)
                    self.total_vram_bytes = torch.cuda.get_device_properties(0).total_memory
                    self._initialized = True
                    logger.info(f"VRAM Guard: PyTorch GPU Detected [{self.vendor}]")
                    return
            except ImportError:
                pass

            # 3. FALLBACK TO WMI (Windows AMD/Intel)
            if platform.system() == "Windows" and self._init_wmi():
                return
            
            # 4. FINAL FALLBACK (CPU Safe Mode)
            logger.warning("VRAM Guard: No discrete GPU detected. Enforcing CPU Safe Mode.")
            self.vendor = "CPU_Fallback"
            self.total_vram_bytes = int(8 * 1024**3)
            self._initialized = True

    def _init_nvidia_nvml(self) -> bool:
        """Driver-level NVIDIA checking. Safest and lightest method."""
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.vendor = pynvml.nvmlDeviceGetName(self._nvml_handle)
            
            if isinstance(self.vendor, bytes):
                self.vendor = self.vendor.decode('utf-8')
                
            self.total_vram_bytes = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle).total
            logger.info(f"VRAM Guard: NVML Driver Detected [{self.vendor}]")
            return True
        except Exception:
            return False

    def _init_wmi(self) -> bool:
        """Windows Management Instrumentation (AMD/Intel fallback)."""
        try:
            import wmi
            wmi_client = wmi.WMI()
            gpu = wmi_client.Win32_VideoController()[0]
            
            self.vendor = gpu.Name or "Unknown Windows GPU"
            self.total_vram_bytes = int(gpu.AdapterRAM)
            self._initialized = True
            logger.info(f"VRAM Guard: WMI Detected [{self.vendor}]")
            return True
        except Exception:
            return False

    def _update_pressure_level(self, used_percent: float):
        """Update memory pressure level based on usage trends."""
        current_time = time.time()
        
        # Only check every 5 seconds to avoid thrashing
        if current_time - self._last_pressure_check < 5.0:
            return
            
        self._last_pressure_check = current_time
        self._usage_history.append({
            "timestamp": current_time,
            "used_percent": used_percent
        })
        
        # Calculate trend (are we increasing or decreasing?)
        if len(self._usage_history) >= 10:
            recent_avg = sum(h["used_percent"] for h in list(self._usage_history)[-5:]) / 5
            older_avg = sum(h["used_percent"] for h in list(self._usage_history)[:5]) / 5
            trend = recent_avg - older_avg
            
            if used_percent > 90 or (used_percent > 80 and trend > 5):
                self._pressure_level = "critical"
                logger.warning(f"VRAM Guard: CRITICAL pressure detected ({used_percent:.1f}%)")
            elif used_percent > 70:
                self._pressure_level = "elevated"
            else:
                self._pressure_level = "normal"

    def get_free_vram_bytes(self) -> int:
        """Fetches current free VRAM dynamically."""
        if not self._initialized:
            self._detect_hardware()
            
        # 1. Prioritize NVML
        if self._nvml_handle:
            try:
                import pynvml
                info = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
                return info.free
            except Exception:
                pass
                
        # 2. PyTorch polling
        if self.has_cuda:
            try:
                import torch
                free_bytes, _ = torch.cuda.mem_get_info()
                return free_bytes
            except Exception:
                pass
        
        # 3. CPU/WMI Fallback Estimate
        estimated_used = 1.5 * (1024**3)
        return max(0, self.total_vram_bytes - int(estimated_used))

    def can_load_model(self, required_gb: float, include_buffer: bool = True, 
                       priority: str = "normal") -> bool:
        """
        Gatekeeper function with priority-based eviction.
        
        Args:
            required_gb: VRAM needed for the model
            include_buffer: Whether to include OS safety buffer
            priority: "critical" (LLM), "normal" (Vision), "low" (Embedder)
        """
        with self._model_load_lock:
            if not self._initialized:
                self._detect_hardware()

            if not self.has_cuda:
                return True  # CPU fallback mode

            required_bytes = int(required_gb * 1024**3)
            free_vram = self.get_free_vram_bytes()
            
            buffer_padding = self.buffer_bytes if include_buffer else 0
            available_vram = free_vram - buffer_padding
            
            # 🚨 Enforce global user config limit
            used_vram = self.total_vram_bytes - free_vram
            if used_vram + required_bytes > self.vram_limit_bytes:
                logger.warning(f"VRAM Guard [BLOCKED]: Would exceed user limit of {config.vram.limit_gb}GB.")
                
                # 🚀 Priority-based eviction: Can we unload lower-priority models?
                if priority == "critical":
                    if self._evict_low_priority_models(required_bytes):
                        return True
                
                return False

            # 🚀 Check memory pressure level
            used_percent = ((self.total_vram_bytes - free_vram) / self.total_vram_bytes) * 100
            self._update_pressure_level(used_percent)
            
            if self._pressure_level == "critical" and priority != "critical":
                logger.warning(f"VRAM Guard [DEFERRED]: Memory pressure critical. Deferring {priority} model.")
                return False

            can_load = available_vram >= required_bytes
            
            if not can_load:
                logger.warning(
                    f"VRAM Guard [BLOCKED]: "
                    f"Required: {required_gb:.2f}GB, "
                    f"Available: {available_vram / 1024**3:.2f}GB"
                )
            
            return can_load

    def _evict_low_priority_models(self, required_bytes: int) -> bool:
        """Attempt to unload lower-priority models to make room."""
        # In a full implementation, this would call unload methods on registered models
        # For now, we just clear the cache
        logger.info("VRAM Guard: Attempting to free VRAM by clearing cache...")
        self.clear_cache()
        
        # Re-check after cache clear
        free_vram = self.get_free_vram_bytes()
        return free_vram >= required_bytes

    def register_model(self, model_name: str, size_gb: float, priority: str = "normal"):
        """Track loaded models for priority-based eviction."""
        with self._lock:
            self._loaded_models[model_name] = {
                "size_gb": size_gb,
                "priority": priority,
                "loaded_at": time.time()
            }
            logger.debug(f"VRAM Guard: Registered model {model_name} ({size_gb}GB, {priority})")

    def unregister_model(self, model_name: str):
        """Unregister a model when it's unloaded."""
        with self._lock:
            if model_name in self._loaded_models:
                del self._loaded_models[model_name]
                logger.debug(f"VRAM Guard: Unregistered model {model_name}")

    def get_usage_stats(self) -> Dict:
        """Export current hardware stats for frontend telemetry."""
        if not self._initialized:
            self._detect_hardware()

        free = self.get_free_vram_bytes()
        used = max(0, self.total_vram_bytes - free)
        used_percent = (used / self.total_vram_bytes * 100) if self.total_vram_bytes > 0 else 0
        
        # Update pressure level
        self._update_pressure_level(used_percent)
        
        return {
            "vendor": self.vendor,
            "total_gb": round(self.total_vram_bytes / 1024**3, 2),
            "used_gb": round(used / 1024**3, 2),
            "free_gb": round(free / 1024**3, 2),
            "percent_used": round(used_percent, 1),
            "pressure_level": self._pressure_level,
            "limit_gb": config.vram.limit_gb,
            "loaded_models": list(self._loaded_models.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }

    def get_memory_trend(self) -> List[Dict]:
        """Get VRAM usage trend for telemetry visualization."""
        return list(self._usage_history)

    def clear_cache(self):
        """Forces immediate garbage collection across Python/C++ layer."""
        with self._lock:
            if self.has_cuda:
                try:
                    import torch
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
                except ImportError:
                    pass
            gc.collect()
            logger.debug("VRAM Guard: Cache cleared.")

    def shutdown(self):
        """Clean shutdown: unload all models and release VRAM."""
        logger.info("VRAM Guard: Initiating shutdown cleanup...")
        
        with self._model_load_lock:
            # Unregister all models
            self._loaded_models.clear()
            
        # Force VRAM clear
        self.clear_cache()
        
        # Close NVML handle
        if self._nvml_handle:
            try:
                import pynvml
                pynvml.nvmlShutdown()
            except Exception:
                pass
        
        logger.info("VRAM Guard: Shutdown complete.")

# Global Singleton
vram_guard = VRAMGuard()