"""
HackT Sovereign Core - Screen Monitor Service Module (v3.0)
============================================================
Background screen monitoring daemon for Passive Mode.
Features:
- Ultra-Fast Pixel Differencing (Prevents OCR spam on static screens)
- Delegates OCR to screen_analyzer (No code duplication)
- VRAM Collision Avoidance (Yields if LLM is active)
- Fast keyword filtering for real-time threat detection
- WebSocket alert broadcasting to React UI
"""

import threading
import time
import asyncio
import numpy as np
from typing import Optional
from PIL import Image

from utils.logger import get_logger
from utils.config import config
from core.memory import vram_guard

# Import the centralized analyzer (no duplicate capture logic)
from services.screen import screen_analyzer

# Lazy import for WebSocket to prevent boot-time circular dependencies
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

logger = get_logger("hackt.services.screen_monitor")


class PassiveScreenMonitor:
    """
    Background screen monitoring daemon for Passive Mode.
    Engineered to minimize GPU/CPU footprint using smart frame diffing.
    """
    
    def __init__(self):
        self.scan_interval = config.modes.screen_scan_interval
        self.is_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Threat detection configuration
        self.threat_keywords = [
            "password", "token=", "secret_key", "api_key",
            "eval(", "exec(", "innerhtml", "document.cookie",
            "phishing", "vulnerability", "xss", "sql injection",
            "aws_access_key", "sk_live", "private_key"
        ]

        # Smart Frame Diffing State
        self._last_frame_hash: Optional[np.ndarray] = None
        self._diff_threshold = 2.5  # Minimum % of pixel change required to trigger OCR
        
        # Monitor configuration
        self.monitor_index = 1  # Primary monitor by default

    def start(self, loop: asyncio.AbstractEventLoop):
        """
        Start the background monitoring thread.
        Requires passing the FastAPI event loop for Thread-Safe WebSocket broadcasting.
        """
        if self.is_running:
            return
            
        self._main_loop = loop
        self.is_running = True
        self._stop_event.clear()
        
        self._monitor_thread = threading.Thread(
            target=self._scan_loop,
            daemon=True,
            name="ScreenMonitor_Daemon"
        )
        self._monitor_thread.start()
        logger.info("Passive Vision Daemon: ONLINE & WATCHING.")
    
    def stop(self):
        """Gracefully stop the background monitoring thread."""
        if not self.is_running:
            return
        
        self._stop_event.set()
        self.is_running = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        
        logger.info("Passive Vision Daemon: OFFLINE.")

    def _calculate_image_diff(self, pil_img: Image.Image) -> bool:
        """
        Takes a tiny, low-res grayscale snapshot of the screen.
        If the screen hasn't changed since the last scan, returns False.
        This saves ~1.2GB of VRAM thrashing every 5 seconds.
        """
        try:
            # Resize to a tiny 100x100 matrix and convert to Grayscale for lightning-fast math
            tiny_img = pil_img.resize((100, 100)).convert("L")
            current_frame = np.array(tiny_img).astype(int)
            
            if self._last_frame_hash is None:
                self._last_frame_hash = current_frame
                return True  # Always scan the first frame
                
            # Calculate Mean Absolute Error (MAE) between the two frames
            diff = np.mean(np.abs(current_frame - self._last_frame_hash))
            self._last_frame_hash = current_frame
            
            # If the average pixel changed by less than the threshold, the screen is basically static
            if diff < self._diff_threshold:
                return False
            return True
        except Exception as e:
            logger.error(f"Image diff calculation failed: {e}")
            return True  # Scan on error to be safe

    def _scan_loop(self):
        """Main daemon loop: Capture → Diff Check → VRAM Check → OCR → Filter → Alert"""
        while not self._stop_event.is_set():
            try:
                # 1. Capture screen frame (using mss directly for speed in daemon thread)
                from mss import mss
                with mss() as sct:
                    monitor_zone = sct.monitors[self.monitor_index] if len(sct.monitors) > self.monitor_index else sct.monitors[0]
                    sct_img = sct.grab(monitor_zone)
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # 2. SMART DIFFING: Did the screen actually change?
                    if not self._calculate_image_diff(img):
                        # Screen is static. Sleep and skip the heavy OCR.
                        time.sleep(self.scan_interval)
                        continue

                    # 3. VRAM COLLISION CHECK: Is the LLM busy?
                    if not vram_guard.can_load_model(config.vram.vision_estimate_gb, include_buffer=True):
                        logger.debug("Vision Daemon: VRAM saturated by LLM. Yielding scan cycle.")
                        time.sleep(self.scan_interval)
                        continue

                    # 4. Run OCR analysis (Delegate to screen_analyzer for consistency)
                    # Note: We're in a thread, so we need to run the async method
                    if self._main_loop and self._main_loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(
                            screen_analyzer.analyze(task="<OCR>", monitor_index=self.monitor_index),
                            self._main_loop
                        )
                        ocr_result = future.result(timeout=30.0)
                    else:
                        # Fallback if event loop isn't available
                        ocr_result = {"type": "error", "text": "[SYSTEM_ERROR: Event loop unavailable]"}
                    
                    # 5. Filter for threats
                    if ocr_result.get("type") != "error" and ocr_result.get("text"):
                        self._evaluate_threat(ocr_result.get("text", ""))
                    
                    time.sleep(self.scan_interval)
                    
            except Exception as e:
                logger.error(f"Vision Daemon encountered an error: {e}")
                time.sleep(self.scan_interval * 2)  # Backoff on error
    
    async def scan_once_async(self):
        """Manual trigger for FastAPI endpoints (e.g., user clicks 'Scan Now')."""
        return await screen_analyzer.analyze(task="<OCR>", monitor_index=self.monitor_index)
    
    def _evaluate_threat(self, text: str):
        """Stage 1 fast-filter for OCR text."""
        if not text or len(text) < 15 or "[SYSTEM_ERROR" in text:
            return
        
        # Fast keyword check (case-insensitive)
        text_lower = text.lower()
        found_keywords = [kw for kw in self.threat_keywords if kw in text_lower]
        
        if found_keywords:
            logger.warning(f"Vision Daemon: Suspicious syntax detected on screen: {found_keywords}")
            
            # Thread-Safe execution: Push the async broadcast into the FastAPI Event Loop
            if self._main_loop and self._main_loop.is_running() and telemetry_manager:
                asyncio.run_coroutine_threadsafe(
                    telemetry_manager.send_threat_alert(
                        threat_level="MEDIUM",
                        source=f"Screen OCR: {found_keywords[0].upper()}",
                        description=f"Passive vision detected sensitive pattern: {found_keywords[0]}"
                    ),
                    self._main_loop
                )
            else:
                logger.error("Vision Daemon: Cannot send threat alert. Main event loop or telemetry unavailable.")


# Singleton instance
screen_monitor = PassiveScreenMonitor()