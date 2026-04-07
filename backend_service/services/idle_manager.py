"""
HackT Sovereign Core - Autonomous Idle Engagement Manager (v3.0)
================================================================
Provides ambient "JARVIS-like" voice status updates:
- Hardware-Aware: Monitors CPU, RAM, and VRAM via psutil.
- OCR Integration: Reads screen for long-running tasks (epochs, compiling).
- VRAM Safe: Bypasses visual cortex if VRAM is saturated.
- Audio Delegation: Streams audio to React via WebSockets (Zero Python Audio Locking).
- Dynamic Cooldowns: Reports frequently during tasks, rarely during true idle.
"""

import asyncio
import time
import random
import logging
from typing import Optional

from utils.logger import get_logger
from utils.config import config
from core.engine import engine
from core.memory import vram_guard
from prompts.orchestrator import orchestrator

# Lazy imports to prevent boot-time circular dependencies
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

try:
    from services.screen import screen_analyzer
except ImportError:
    screen_analyzer = None

try:
    from services.code_watcher import code_watcher
except ImportError:
    code_watcher = None

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = get_logger("hackt.services.idle_manager")

class IdleEngagementManager:
    """
    Manages ambient voice engagements based on hardware and screen context.
    Engineered to feel like a human partner monitoring the perimeter.
    """
    
    def __init__(self, base_cooldown_seconds: int = 600):
        self.base_cooldown = base_cooldown_seconds
        self.current_cooldown = base_cooldown_seconds
        self.last_activity = time.time()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

        # High-Entropy Zero-VRAM Pool (Used if LLM fails or is busy)
        self.static_phrases = [
            "VRAM stable. All passive monitors secure.",
            "Perimeter clear. I remain on standby.",
            "Background telemetry is optimal.",
            "I am maintaining overwatch.",
            "Neural link stable. Awaiting your command, operator.",
            "Scanning idle memory... No threats found."
        ]

    def record_activity(self):
        """Call this whenever the user interacts with the app (chat/voice)"""
        self.last_activity = time.time()
        self.current_cooldown = self.base_cooldown 
        logger.debug("IdleManager: Timer reset by user activity.")

    def start(self):
        """Start the background idle check loop"""
        if self.is_running:
            return
            
        if config.mode == "passive":
            self.is_running = True
            self._task = asyncio.create_task(self._idle_loop())
            logger.info("IdleManager: ONLINE (Passive Mode)")
        else:
            logger.warning("IdleManager: Aborted boot. Core is not in Passive Mode.")

    def stop(self):
        """Stop the background loop"""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("IdleManager: OFFLINE")

    async def _idle_loop(self):
        """Tick every 60 seconds to evaluate system state"""
        while self.is_running:
            try:
                await asyncio.sleep(60)
                
                time_idle = time.time() - self.last_activity
                if time_idle >= self.current_cooldown:
                    logger.info(f"IdleManager: User idle for {int(time_idle)}s. Initiating autonomous check.")
                    await self._trigger_engagement()
                    self.last_activity = time.time() 
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"IdleManager: Loop error: {e}")
                await asyncio.sleep(5)  # Backoff on error

    async def _trigger_engagement(self):
        """Analyze hardware, capture screen if safe, generate speech, and broadcast."""
        if not engine or not vram_guard or not telemetry_manager:
            return

        # 1. Gather Hardware Metrics (Real Data via psutil)
        stats = vram_guard.get_usage_stats()
        
        cpu_usage = psutil.cpu_percent(interval=None) if PSUTIL_AVAILABLE else 0.0
        ram_usage = psutil.virtual_memory().percent if PSUTIL_AVAILABLE else 0.0
        vram_used = float(stats.get("used_gb", 0.0))
        vram_total = float(stats.get("total_gb", 6.0))

        # Determine if system is under heavy load
        is_system_under_load = cpu_usage > 60 or (vram_used / max(vram_total, 1)) > 0.7

        # 2. Conditional Visual Cortex (OCR)
        screen_text = "None"
        if is_system_under_load and screen_analyzer:
            # We suspect a task is running. Do we have VRAM to look at it?
            if vram_guard.can_load_model(config.vram.vision_estimate_gb, include_buffer=True):
                logger.info("IdleManager: System under load. Triggering silent OCR check...")
                try:
                    # Offload blocking capture & inference to thread
                    img = await asyncio.to_thread(screen_analyzer.capture_screen)
                    if img:
                        ocr_result = await asyncio.to_thread(engine.analyze_screen, img, "<OCR>")
                        screen_text = ocr_result[:800] if ocr_result else "None"
                except Exception as e:
                    logger.warning(f"IdleManager: Silent OCR check failed: {e}")
            else:
                logger.info("IdleManager: System under load, VRAM saturated. Bypassing visual cortex.")
                screen_text = "[VISUAL CORTEX BYPASSED DUE TO VRAM SATURATION]"

        # 3. Contextual Data
        ide_file = "None"
        if code_watcher:
            active_context = code_watcher.get_active_context()
            ide_file = active_context.get("file_name", "None")

        system_state = {
            "CPU": f"{cpu_usage}%",
            "RAM": f"{ram_usage}%",
            "VRAM": f"{vram_used}GB / {vram_total}GB",
            "Screen Context": screen_text,
            "Active IDE File": ide_file
        }

        # 4. Generate Speech via the Master Orchestrator
        response_text = ""
        try:
            # We route this through our prompts/orchestrator.py to ensure ChatML formatting
            route_data = orchestrator.route(
                query="Generate a concise, ambient status report.",
                mode="passive",
                query_type="idle",
                system_state=system_state
            )
            
            raw_response = await asyncio.to_thread(
                engine.generate, 
                route_data["prompt"], 
                max_tokens=route_data["max_tokens"], 
                temperature=0.5
            )
            response_text = raw_response.replace('"', '').replace('\n', ' ').strip()
        except Exception as e:
            logger.warning(f"IdleManager: Contextual bark failed: {e}")
            response_text = random.choice(self.static_phrases)

        if not response_text:
            return

        logger.info(f"HackT Autonomous Report: {response_text}")

        # 5. SYNTHESIS & WEBSOCKET BROADCAST (Bypassing Python Audio Drivers)
        try:
            # Generate the WAV bytes strictly in RAM using Piper
            wav_bytes = await telemetry_manager.broadcast_audio(
                text=response_text, 
                urgency_score=0.8 if is_system_under_load else 0.2
            )
            
            # Note: broadcast_audio handles the TTS synthesis internally in our final websocket.py design
            # OR if tts_service is local:
            # wav_bytes = await tts_service.synthesize(...)
            # await telemetry_manager.broadcast_audio(wav_bytes)
            
            # For this implementation, we assume tts_service is available locally as per previous design
            from services.audio import tts_service
            wav_bytes = await tts_service.synthesize(
                text=response_text, 
                urgency_score=0.8 if is_system_under_load else 0.2
            )
            await telemetry_manager.broadcast_audio(wav_bytes)
            
            # Send the text transcript so the UI can display it in the bubble
            await telemetry_manager.broadcast_json({
                "type": "idle_bark",
                "text": response_text,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"IdleManager: Synthesis/Broadcast failed: {e}")

        # 6. DYNAMIC COOLDOWN ADJUSTMENT
        if is_system_under_load:
            self.current_cooldown = random.randint(240, 480) # 4 to 8 minutes
            logger.info(f"IdleManager: Tracking active workload. Next report in {self.current_cooldown // 60}m.")
        else:
            self.current_cooldown = random.randint(900, 1500) # 15 to 25 minutes
            logger.info(f"IdleManager: System deep idle. Next report in {self.current_cooldown // 60}m.")

# Singleton instance (Defaults to 10 minutes initial check)
idle_manager = IdleEngagementManager(base_cooldown_seconds=600)