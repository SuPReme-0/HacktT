import threading
import time
from mss import mss
from PIL import Image
from core.vision import vision_engine
from utils.logger import get_logger

logger = get_logger("hackt.services.screen_monitor")

class PassiveScreenMonitor:
    def __init__(self):
        self.is_running = False
        self.monitor_thread = None
        # How often to scan the screen (in seconds). 
        # 5 seconds is optimal to avoid cooking the GPU while maintaining vigilance.
        self.scan_interval = 5.0 

    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Passive Vision Daemon: ONLINE & WATCHING.")

    def stop(self):
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info("Passive Vision Daemon: OFFLINE.")

    def _scan_loop(self):
        """The core background loop that feeds Florence-2."""
        with mss() as sct:
            # monitors[1] is the primary display. monitors[0] is all displays combined.
            monitor_zone = sct.monitors[1]
            
            while self.is_running:
                try:
                    # 1. Grab Frame natively from OS
                    sct_img = sct.grab(monitor_zone)
                    
                    # 2. Convert to PIL Image for Florence-2
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # 3. Trigger Ephemeral OCR (Loads -> Analyzes -> Unloads)
                    ocr_text = vision_engine.analyze_screen(img, task_prompt="<OCR>")
                    
                    # 4. Filter and Evaluate
                    self._evaluate_threat(ocr_text)

                except Exception as e:
                    logger.error(f"Vision Daemon encountered an error: {e}")
                
                # Sleep to prevent GPU/CPU redlining
                time.sleep(self.scan_interval)

    def _evaluate_threat(self, text: str):
        """Stage 1 Fast-Filter for OCR text."""
        if not text or len(text) < 15 or "[SYSTEM_ERROR" in text:
            return

        # Fast Keyword Check (Similar to our Browser Ingestion logic)
        red_flags = ["password", "token=", "eval(", "secret_key", "login", "vulnerability"]
        text_lower = text.lower()
        
        if any(flag in text_lower for flag in red_flags):
            logger.info(f"Vision Daemon: Suspicious syntax detected on screen. Alerting Brain.")
            # Here is where we will trigger a WebSocket/HTTP POST to Tauri 
            # so the Neural Bubble turns Yellow/Red and triggers the Qwen LLM.

screen_monitor = PassiveScreenMonitor()