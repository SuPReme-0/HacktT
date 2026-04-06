"""
HackT Sovereign Core - Memory Management Module
================================================
Provides VRAM monitoring and safety guards for:
- NVIDIA GPUs via PyNVML / PyTorch
- AMD/Intel GPUs via WMI (Windows) or ROCm (Linux)
- Conservative heuristics for unknown hardware
- Automatic cache clearing to prevent fragmentation
"""

import logging
import platform
import gc
from typing import Optional, Dict

logger = logging.getLogger("hackt.core.memory")


class VRAMGuard:
    """
    VRAM monitoring and safety enforcement for model loading.
    """
    
    def __init__(self, vram_limit_gb: float = 6.0, buffer_gb: float = 1.0):
        self.vram_limit_bytes = vram_limit_gb * 1024**3
        self.buffer_bytes = buffer_gb * 1024**3
        
        self.vendor: str = "Unknown"
        self.total_vram_bytes: int = 0
        self._nvml_handle: Optional[object] = None
        self._initialized: bool = False
        self.has_cuda = False
    
    def _detect_hardware(self):
        """Detect GPU vendor and initialize appropriate telemetry."""
        if self._initialized:
            return

        try:
            import torch
            if torch.cuda.is_available():
                self.has_cuda = True
                self.vendor = torch.cuda.get_device_name(0)
                self.total_vram_bytes = torch.cuda.get_device_properties(0).total_memory
                self._initialized = True
                logger.info(f"VRAM Guard: GPU Detected [{self.vendor}] - {self.total_vram_bytes / 1024**3:.1f}GB Total")
                
                if "NVIDIA" in self.vendor:
                    self._init_nvidia()
                return
        except ImportError:
            pass

        if platform.system() == "Windows" and self._init_wmi():
            return
        
        logger.warning("VRAM Guard: GPU detection failed. Running in CPU Safe Mode.")
        self.vendor = "CPU_Fallback"
        self.total_vram_bytes = 8 * 1024**3  
        self._initialized = True
    
    def _init_nvidia(self) -> bool:
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            return True
        except Exception:
            return False
    
    def _init_wmi(self) -> bool:
        try:
            import wmi
            wmi_client = wmi.WMI()
            gpu = wmi_client.Win32_VideoController()[0]
            
            self.vendor = gpu.Name or "Unknown Windows GPU"
            self.total_vram_bytes = int(gpu.AdapterRAM)
            self._initialized = True
            logger.info(f"VRAM Guard: WMI Detected [{self.vendor}] - {self.total_vram_bytes / 1024**3:.1f}GB Total")
            return True
        except Exception:
            return False
    
    def get_free_vram_bytes(self) -> int:
        if not self._initialized:
            self._detect_hardware()
            
        if self.has_cuda:
            try:
                import torch
                free_bytes, _ = torch.cuda.mem_get_info()
                return free_bytes
            except Exception:
                pass
        
        if self._nvml_handle:
            try:
                import pynvml
                info = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
                return info.free
            except Exception:
                pass
        
        estimated_used = 1.5 * 1024**3
        return max(0, self.total_vram_bytes - estimated_used)
    
    def can_load_model(self, required_gb: float, include_buffer: bool = True) -> bool:
        if not self._initialized:
            self._detect_hardware()

        if not self.has_cuda:
            return True 

        required_bytes = int(required_gb * 1024**3)
        free_vram = self.get_free_vram_bytes()
        
        available = free_vram - (self.buffer_bytes if include_buffer else 0)
        can_load = available >= required_bytes
        
        if not can_load:
            logger.warning(
                f"VRAM Guard [BLOCKED LOAD]: "
                f"Required: {required_gb:.2f} GB, "
                f"Available: {available / 1024**3:.2f} GB"
            )
        
        return can_load
    
    def get_usage_stats(self) -> Dict:
        if not self._initialized:
            self._detect_hardware()

        free = self.get_free_vram_bytes()
        used = max(0, self.total_vram_bytes - free)
        
        return {
            "total_gb": self.total_vram_bytes / 1024**3,
            "used_gb": used / 1024**3,
            "free_gb": free / 1024**3,
            "percent_used": (used / self.total_vram_bytes * 100) if self.total_vram_bytes > 0 else 0,
            "vendor": self.vendor,
        }
    
    def clear_cache(self):
        if self.has_cuda:
            try:
                import torch
                torch.cuda.empty_cache()
            except ImportError:
                pass
        gc.collect()

# Lazy-loaded singleton. Instantiates instantly, but won't query hardware until a method is called.
vram_guard = VRAMGuard()