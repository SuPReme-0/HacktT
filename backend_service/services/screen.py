"""
HackT Sovereign Core - Screen Analysis Service Module
======================================================
Orchestrates screen capture and Florence-2 analysis:
- Cross-platform screen capture (mss for Windows/Linux, AVFoundation for macOS)
- Florence-2 task routing (OCR, object detection, captioning)
- Result parsing and structuring for React consumption
- VRAM-safe ephemeral model loading via SovereignEngine
"""

import logging
from typing import Dict, Optional
from PIL import Image
from mss import mss

from utils.logger import get_logger

logger = get_logger("hackt.services.screen")


class ScreenAnalyzer:
    """
    Screen capture and analysis orchestrator.
    
    Features:
    - Multi-monitor support with primary display default
    - Context-managed capture for memory safety
    - Florence-2 task routing (<OCR>, <OD>, <CAPTION>, etc.)
    - Structured output parsing with System Error detection
    """
    
    def capture_screen(self, region: Optional[Dict[str, int]] = None) -> Optional[Image.Image]:
        """
        Capture screen safely using a context manager to prevent memory leaks.
        
        Args:
            region: Optional {left, top, width, height} for ROI capture
            
        Returns:
            PIL Image in RGB format, or None if capture fails
        """
        try:
            with mss() as sct:
                # Use specified region or fallback to primary monitor (index 1)
                monitor = region if region else sct.monitors[1]
                
                # Capture and convert to PIL Image
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                return img
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None
    
    async def analyze(self, task: str = "<OCR>", region: Optional[Dict] = None) -> Dict:
        """
        Capture and analyze screen with Florence-2.
        
        Args:
            task: Florence-2 task prompt ("<OCR>", "<OD>", "<CAPTION>", etc.)
            region: Optional ROI for capture
            
        Returns:
            Structured analysis result dictionary
        """
        img = self.capture_screen(region)
        if not img:
            return {"type": "error", "text": "[SYSTEM_ERROR: Screen capture failed]"}
        
        # LOCAL IMPORT: Pull active SovereignEngine from main to avoid circular imports
        from main import engine
        if not engine:
            return {"type": "error", "text": "[SYSTEM_ERROR: AI Engine offline]"}

        # Run Florence-2 analysis (handles its own ephemeral load/unload for VRAM safety)
        result_text = engine.analyze_screen(img, task=task)
        
        # Catch VRAM or Engine errors before parsing
        if "[SYSTEM_ERROR" in result_text:
            logger.warning(f"Vision analysis returned system error: {result_text}")
            return {"type": "error", "text": result_text}
        
        # Parse result based on task type
        if task == "<OCR>":
            return self._parse_ocr(result_text)
        elif task == "<OD>":
            return self._parse_object_detection(result_text)
        elif task == "<CAPTION>":
            return self._parse_caption(result_text)
        else:
            return {"type": "raw", "text": result_text, "task": task}
    
    def _parse_ocr(self, raw_text: str) -> Dict:
        """Parse Florence-2 OCR output into structured format"""
        # Florence-2 OCR returns: "text line 1 <sep> text line 2"
        lines = raw_text.replace("<OCR>", "").strip().split("<sep>")
        clean_lines = [line.strip() for line in lines if line.strip()]
        
        return {
            "type": "ocr",
            "text": "\n".join(clean_lines),
            "lines": clean_lines,
            "word_count": len(" ".join(clean_lines).split())
        }
    
    def _parse_object_detection(self, raw_text: str) -> Dict:
        """Parse Florence-2 object detection output"""
        # Format: "object1 [x1,y1,x2,y2] <sep> object2 [x1,y1,x2,y2]"
        objects = []
        parts = raw_text.replace("<OD>", "").strip().split("<sep>")
        
        for part in parts:
            if "[" in part and "]" in part:
                try:
                    # Extract object name and bbox
                    name, bbox_str = part.split("[")
                    bbox = [int(x) for x in bbox_str.replace("]", "").split(",")]
                    objects.append({
                        "label": name.strip(),
                        "bbox": bbox  # [x1, y1, x2, y2]
                    })
                except ValueError:
                    continue # Skip malformed bounding boxes
        
        return {
            "type": "object_detection",
            "objects": objects,
            "count": len(objects)
        }
    
    def _parse_caption(self, raw_text: str) -> Dict:
        """Parse Florence-2 caption output"""
        clean_text = raw_text.replace("<CAPTION>", "").strip()
        return {
            "type": "caption",
            "caption": clean_text,
            "length": len(clean_text.split())
        }


# Singleton instance
screen_analyzer = ScreenAnalyzer()