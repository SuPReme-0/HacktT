"""
HackT Sovereign Core - Screen Analysis Service Module (v3.0)
=============================================================
Centralized screen capture and Florence-2 analysis orchestrator.
Features:
- Cross-platform screen capture (mss with context managers)
- VRAM-safe asynchronous PyTorch offloading (asyncio.to_thread)
- Florence-2 task routing (OCR, Object Detection, Captioning)
- Output structuring for React UI consumption
- Memory-safe resource management
"""

import logging
import asyncio
from typing import Dict, Optional, Any, List
from PIL import Image
from mss import mss

from utils.logger import get_logger
from core.engine import engine
from core.memory import vram_guard
from utils.config import config

logger = get_logger("hackt.services.screen")


class ScreenAnalyzer:
    """
    Centralized screen capture and analysis orchestrator.
    Engineered to never block the FastAPI Event Loop during PyTorch inference.
    """
    
    def __init__(self):
        self.default_monitor_index = 1  # Primary monitor
        self.capture_timeout_sec = 5.0
        
    def capture_screen(self, monitor_index: Optional[int] = None, 
                       region: Optional[Dict[str, int]] = None) -> Optional[Image.Image]:
        """
        Capture screen safely using a context manager to prevent memory leaks.
        
        Args:
            monitor_index: Monitor number (0=all, 1=primary, 2=secondary, etc.)
            region: Optional ROI {left, top, width, height} for partial capture
            
        Returns:
            PIL Image in RGB format, or None if capture fails
        """
        try:
            with mss() as sct:
                # Determine which monitor to capture
                if region:
                    monitor = region
                elif monitor_index is not None and monitor_index < len(sct.monitors):
                    monitor = sct.monitors[monitor_index]
                else:
                    # Fallback: primary monitor if available, else all monitors merged
                    monitor = sct.monitors[self.default_monitor_index] if len(sct.monitors) > 1 else sct.monitors[0]
                
                # Capture and convert to PIL Image (MSS returns BGRA, convert to RGB)
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                return img
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None
    
    async def analyze(self, task: str = "<OCR>", monitor_index: Optional[int] = None,
                      region: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Capture and analyze screen with Florence-2 asynchronously.
        
        Args:
            task: Florence-2 task ("<OCR>", "<OD>", "<CAPTION>", "<DETAILED_CAPTION>")
            monitor_index: Which monitor to capture
            region: Optional ROI for partial capture
            
        Returns:
            Structured analysis result dictionary
        """
        # 1. Capture screen
        img = self.capture_screen(monitor_index, region)
        if not img:
            return {"type": "error", "text": "[SYSTEM_ERROR: Screen capture failed]"}
        
        if not engine:
            return {"type": "error", "text": "[SYSTEM_ERROR: AI Engine offline]"}

        # 2. VRAM Check before loading Florence-2
        if not vram_guard.can_load_model(config.vram.vision_estimate_gb, include_buffer=True):
            return {"type": "error", "text": "[SYSTEM_ERROR: VRAM saturated]"}

        try:
            # 🚀 ASYNC OFFLOAD: Prevent PyTorch from freezing the FastAPI WebSockets
            result = await asyncio.to_thread(engine.analyze_screen, img, task=task)
            
            # Catch VRAM or Engine errors before parsing
            if isinstance(result, str) and "[SYSTEM_ERROR" in result:
                logger.warning(f"Vision analysis returned system error: {result}")
                return {"type": "error", "text": result}
            
            # 3. Parse result based on task type
            if task == "<OCR>":
                return self._parse_ocr(result)
            elif task == "<OD>":
                return self._parse_object_detection(result)
            elif task == "<CAPTION>" or task == "<DETAILED_CAPTION>":
                return self._parse_caption(result)
            else:
                return {"type": "raw", "text": str(result), "task": task}
                
        except Exception as e:
            logger.error(f"On-Demand Vision Analysis failed: {e}")
            return {"type": "error", "text": f"[SYSTEM_ERROR: {str(e)}]"}
    
    def _parse_ocr(self, engine_output: Any) -> Dict[str, Any]:
        """Format Florence-2 OCR output for React UI."""
        text = str(engine_output).strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        return {
            "type": "ocr",
            "text": text,
            "lines": lines,
            "word_count": len(text.split()),
            "has_sensitive_data": self._check_sensitive_keywords(text)
        }
    
    def _parse_object_detection(self, engine_output: Any) -> Dict[str, Any]:
        """Format Florence-2 object detection output with bounding boxes."""
        objects = []
        
        if isinstance(engine_output, dict):
            labels = engine_output.get("labels", [])
            bboxes = engine_output.get("bboxes", [])
            
            for i in range(min(len(labels), len(bboxes))):
                objects.append({
                    "label": labels[i],
                    "bbox": bboxes[i]  # [x1, y1, x2, y2]
                })
        else:
            logger.warning("Object Detection returned non-dictionary output.")
        
        return {
            "type": "object_detection",
            "objects": objects,
            "count": len(objects)
        }
    
    def _parse_caption(self, engine_output: Any) -> Dict[str, Any]:
        """Format Florence-2 caption output."""
        caption = str(engine_output).strip()
        return {
            "type": "caption",
            "caption": caption,
            "length": len(caption.split())
        }
    
    def _check_sensitive_keywords(self, text: str) -> bool:
        """Quick check for sensitive data in OCR text."""
        sensitive_patterns = [
            "password", "token=", "secret_key", "api_key",
            "eval(", "exec(", "innerhtml", "document.cookie",
            "aws_access_key", "sk_live", "private_key"
        ]
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in sensitive_patterns)
    
    async def scan_for_threats(self, monitor_index: Optional[int] = None) -> Dict[str, Any]:
        """
        Specialized method for threat scanning (used by screen_monitor.py).
        Returns OCR text + threat assessment.
        """
        ocr_result = await self.analyze(task="<OCR>", monitor_index=monitor_index)
        
        if ocr_result.get("type") == "error":
            return ocr_result
        
        return {
            "ocr_text": ocr_result.get("text", ""),
            "has_sensitive_data": ocr_result.get("has_sensitive_data", False),
            "word_count": ocr_result.get("word_count", 0)
        }


# Singleton instance
screen_analyzer = ScreenAnalyzer()