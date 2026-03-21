import torch
import platform
import logging

logger = logging.getLogger("hackt.utils.memory")

class VRAMGuard:
    def __init__(self):
        self.vendor = "Unknown"
        self.total_vram_gb = 8.0  # Safe fallback
        self.nvml_handle = None

        # 1. PRIMARY: Try NVIDIA (PyNVML)
        # Deepest telemetry, gives exact real-time free VRAM
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.vendor = "NVIDIA"
            logger.info("VRAM Guard: NVIDIA Hardware Detected & Hooked.")
            return
        except Exception:
            pass

        # 2. SECONDARY: Windows Universal WMI (AMD / Intel)
        # Universal OS-level fallback for Radeon and Arc GPUs
        if platform.system() == "Windows":
            try:
                import wmi
                w = wmi.WMI()
                # Query the Win32_VideoController
                gpu = w.Win32_VideoController()[0]
                
                # AdapterRAM returns bytes. Convert to GB.
                self.total_vram_gb = int(gpu.AdapterRAM) / (1024**3)
                self.vendor = gpu.Name
                
                logger.info(f"VRAM Guard: Universal Driver Engaged. GPU: {self.vendor} | Total VRAM: {self.total_vram_gb:.1f} GB")
                return
            except Exception as e:
                logger.warning(f"VRAM Guard: Universal WMI Fallback failed: {e}")

        logger.warning("VRAM Guard: Hardware telemetry failed. Defaulting to 8GB Safe Mode.")

    def get_free_vram_gb(self) -> float:
        """
        Returns dynamic free VRAM for NVIDIA/ROCm.
        Uses a conservative heuristic for Windows AMD/Intel (DirectML).
        """
        # Precise real-time calculation for NVIDIA
        if self.vendor == "NVIDIA":
            import pynvml
            info = pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
            return info.free / (1024 ** 3)
        
        # Precise real-time calculation for AMD on Linux (ROCm)
        if torch.cuda.is_available() and "NVIDIA" not in self.vendor:
            free_bytes, _ = torch.cuda.mem_get_info()
            return free_bytes / (1024 ** 3)

        # Heuristic for Windows AMD/Intel 
        # (Getting dynamic free VRAM without DXGI C++ hooks is impossible in pure Python)
        # We assume the OS and background apps use ~1.5GB of the total capacity.
        logger.debug(f"Calculating heuristic VRAM for {self.vendor}")
        return max(0.0, self.total_vram_gb - 1.5)

    def can_load_model(self, required_gb: float, buffer_gb: float = 1.0) -> bool:
        """
        Checks if a model can safely fit into the GPU.
        Buffer ensures Windows OS doesn't crash from VRAM starvation.
        """
        free = self.get_free_vram_gb()
        available = free - buffer_gb
        
        if available >= required_gb:
            return True
        else:
            logger.warning(f"VRAM Blocked: Need {required_gb}GB, but only {available:.1f}GB available.")
            return False

    def clear_cuda_cache(self):
        """Forcefully clears PyTorch/DirectML cache to recover fragmented VRAM."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("GPU Cache Purged. Memory reclaimed.")

vram_guard = VRAMGuard()