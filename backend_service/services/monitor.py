"""
HackT Sovereign Core - Screen Monitor Service Module
=====================================================
Provides background screen monitoring for Passive Mode:
- Periodic screen capture via mss
- Florence-2 OCR analysis (ephemeral loading via SovereignEngine)
- Fast keyword filtering to avoid waking the LLM unnecessarily
- Thread-safe alert broadcasting to FastAPI event loop

Runs as daemon thread to avoid blocking the web server.
"""

import threading
import time
import asyncio
from typing import Optional
from mss import mss
from PIL import Image

from utils.logger import get_logger

logger = get_logger("hackt.services.screen_monitor")


class PassiveScreenMonitor:
    """
    Background screen monitoring daemon for Passive Mode.
    
    Features:
    - Periodic screen capture (configurable interval)
    - Florence-2 OCR with ephemeral loading (VRAM-safe)
    - Fast threat keyword filtering
    - Alert broadcasting via telemetry_manager
    - Graceful start/stop with thread safety
    """
    
    def __init__(self, scan_interval: float = 5.0):
        """
        Initialize screen monitor.
        
        Args:
            scan_interval: Seconds between screen scans (default: 5.0)
        """
        self.scan_interval = scan_interval
        self.is_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Threat detection configuration
        self.threat_keywords = [
            "password", "token=", "secret_key", "api_key",
            "eval(", "exec(", "innerHTML", "document.cookie",
            "phishing", "login", "vulnerability", "xss", "sql injection"
        ]
        
    def start(self):
        """Start the background monitoring thread"""
        if self.is_running:
            return
        
        # CRITICAL: Capture the FastAPI main event loop from the thread that calls start()
        try:
            self._main_loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("ScreenMonitor started outside an event loop. Alerts may fail.")
        
        self.is_running = True
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._scan_loop,
            daemon=True,
            name="ScreenMonitor"
        )
        self._monitor_thread.start()
        logger.info("Passive Vision Daemon: ONLINE & WATCHING.")
    
    def stop(self):
        """Stop the background monitoring thread"""
        if not self.is_running:
            return
        
        self._stop_event.set()
        self.is_running = False
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        
        logger.info("Passive Vision Daemon: OFFLINE.")
    
    def _scan_loop(self):
        """Main monitoring loop: capture → analyze → filter → alert (Runs in Background Thread)"""
        with mss() as sct:
            # monitors[1] is primary display. (monitors[0] captures all displays merged)
            monitor_zone = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            
            while not self._stop_event.is_set():
                try:
                    # LOCAL IMPORT: Get active engine safely
                    from main import engine
                    if not engine:
                        time.sleep(2.0)
                        continue

                    # 1. Capture screen frame
                    sct_img = sct.grab(monitor_zone)
                    
                    # 2. Convert to PIL Image for Florence-2
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # 3. Run OCR analysis (Engine handles the ephemeral load/unload)
                    ocr_text = engine.analyze_screen(img, task="<OCR>")
                    
                    # 4. Filter for threats
                    if ocr_text and len(ocr_text) > 15:
                        self._evaluate_threat(ocr_text)
                    
                    # 5. Wait for next scan
                    time.sleep(self.scan_interval)
                    
                except Exception as e:
                    logger.error(f"Vision Daemon encountered an error: {e}")
                    # Backoff on error to avoid CPU/GPU redlining
                    time.sleep(self.scan_interval * 2)
    
    async def _scan_loop_once(self):
        """Run a single scan (for manual trigger via HTTP / PassiveBubble)"""
        try:
            from main import engine
            if not engine:
                return

            with mss() as sct:
                monitor_zone = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor_zone)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                # CRITICAL: Since this is called from FastAPI async route, we MUST 
                # offload the blocking PyTorch computation to a background thread to prevent server freeze.
                ocr_text = await asyncio.to_thread(engine.analyze_screen, img, "<OCR>")
                
                if ocr_text:
                    self._evaluate_threat(ocr_text)
                    
        except Exception as e:
            logger.error(f"Manual screen scan failed: {e}")
    
    def _evaluate_threat(self, text: str):
        """Stage 1 fast-filter for OCR text"""
        if not text or len(text) < 15 or "[SYSTEM_ERROR" in text:
            return
        
        # Fast keyword check (case-insensitive)
        text_lower = text.lower()
        found_keywords = [kw for kw in self.threat_keywords if kw in text_lower]
        
        if found_keywords:
            logger.warning(f"Vision Daemon: Suspicious syntax detected: {found_keywords}")
            
            # LOCAL IMPORT
            from services.websocket import telemetry_manager
            
            # CRITICAL: We are in a standard Thread. We must use the captured main Event Loop 
            # to trigger the async WebSocket broadcast.
            if self._main_loop and self._main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    telemetry_manager.send_threat_alert(
                        threat_level="MEDIUM",
                        source=f"screen_ocr:{found_keywords[0]}"
                    ),
                    self._main_loop
                )
            else:
                logger.error("Cannot send threat alert: Main event loop is missing or dead.")


# Singleton instance
screen_monitor = PassiveScreenMonitor(scan_interval=5.0)