"""
HackT Sovereign Core - Autonomous Idle Engagement Manager
========================================================
Provides ambient "JARVIS-like" voice status updates:
- Hardware-Aware: Monitors CPU, RAM, and VRAM.
- OCR Integration: Reads screen for long-running tasks (epochs, compiling).
- VRAM Safe: Bypasses visual cortex if VRAM is saturated by user tasks.
- Dynamic Cooldowns: Reports frequently during tasks, rarely during true idle.
"""

import asyncio
import time
import random
import logging
import io
from typing import Optional

from utils.logger import get_logger

logger = get_logger("hackt.services.idle_manager")

SPEECH_IDLE_PROMPT = """
<|system|>
You are HackT, a sovereign cybersecurity AI assistant. The operator is away from the keyboard.
Provide a brief (1-2 sentences max), professional status update. Do not ask questions.
Context:
System Load: CPU {cpu_usage}%, RAM {ram_usage}%, VRAM {vram_used}GB / {vram_total}GB
Active IDE File: {ide_file}
Screen OCR Data (if any): {screen_text}
Threat Status: {threat_status}

Instructions:
1. If Screen OCR Data shows training (epochs, loss), compiling, or rendering, report the progress briefly.
2. If Screen Data is empty but VRAM/CPU is very high, state that heavy compute is active but visual analysis was bypassed to save memory.
3. If system is completely idle, provide a standard secure perimeter update.
<|user|>
Generate a concise, ambient status report.
<|assistant|>
"""

class IdleEngagementManager:
    """Manages ambient voice engagements based on hardware and screen context."""
    
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
        # Reset to base cooldown on user return
        self.current_cooldown = self.base_cooldown 
        logger.debug("Idle timer reset by user activity.")

    def start(self):
        """Start the background idle check loop"""
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._idle_loop())
            logger.info("Idle Engagement Manager: ONLINE")

    def stop(self):
        """Stop the background loop"""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Idle Engagement Manager: OFFLINE")

    async def _idle_loop(self):
        """Tick every 60 seconds to evaluate system state"""
        while self.is_running:
            try:
                await asyncio.sleep(60)
                
                time_idle = time.time() - self.last_activity
                if time_idle >= self.current_cooldown:
                    logger.info(f"User idle for {int(time_idle)}s. Initiating autonomous check.")
                    await self._trigger_engagement()
                    self.last_activity = time.time() 
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Idle loop error: {e}")

    def _play_audio_sync(self, wav_bytes: bytes):
        """Blocking function to play audio through OS speakers"""
        try:
            import sounddevice as sd
            import soundfile as sf
            
            data, fs = sf.read(io.BytesIO(wav_bytes))
            sd.play(data, fs)
            sd.wait() # Blocks until audio finishes playing
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")

    async def _trigger_engagement(self):
        """Analyze hardware, capture screen if safe, generate speech, and play"""
        # LOCAL IMPORTS
        from main import engine, app_state, vram_guard
        from services.code_watcher import code_watcher
        from services.audio import tts_service
        from services.websocket import telemetry_manager
        from services.screen import screen_analyzer

        if not engine or not vram_guard:
            return

        # 1. Gather Hardware Metrics
        stats = vram_guard.get_usage_stats()
        cpu_usage = app_state.get("backend_health", {}).get("cpu_usage", 0)
        ram_usage = app_state.get("backend_health", {}).get("memory_usage", 0)
        vram_used = round(stats.get("used_gb", 0), 1)
        vram_total = round(stats.get("total_gb", 6.0), 1)

        is_system_under_load = cpu_usage > 60 or (vram_used / vram_total) > 0.7

        # 2. Conditional Visual Cortex (OCR)
        screen_text = "None"
        if is_system_under_load:
            # We suspect a task is running. Do we have VRAM to look at it?
            if vram_guard.can_load_model(1.2, include_buffer=True):
                logger.info("System under load. VRAM available. Triggering silent OCR check...")
                try:
                    # Offload blocking capture & inference to thread
                    img = await asyncio.to_thread(screen_analyzer.capture_screen)
                    if img:
                        ocr_result = await asyncio.to_thread(engine.analyze_screen, img, "<OCR>")
                        # Truncate to save LLM context window
                        screen_text = ocr_result[:800] if ocr_result else "None"
                except Exception as e:
                    logger.warning(f"Silent OCR check failed: {e}")
            else:
                logger.info("System under load, but VRAM is saturated. Bypassing visual cortex.")
                screen_text = "[VISUAL CORTEX BYPASSED DUE TO VRAM SATURATION]"

        # 3. Contextual Data
        active_context = code_watcher.get_active_context()
        ide_file = active_context.get("file", "None")
        threat_status = app_state.get("threat_level", "Safe")

        # 4. Generate Speech via LLM
        response_text = ""
        try:
            prompt = SPEECH_IDLE_PROMPT.format(
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                vram_used=vram_used,
                vram_total=vram_total,
                ide_file=ide_file,
                screen_text=screen_text,
                threat_status=threat_status
            )
            # Max 50 tokens ~ 30 words
            raw_response = await asyncio.to_thread(engine.generate, prompt, max_tokens=50, temperature=0.5)
            response_text = raw_response.replace('"', '').replace('\n', ' ').strip()
        except Exception as e:
            logger.warning(f"Contextual bark failed: {e}")
            response_text = random.choice(self.static_phrases)

        if not response_text:
            return

        logger.info(f"HackT Autonomous Report: {response_text}")

        # 5. SYNTHESIS & BROADCAST
        try:
            # Tell React the Bubble is transmitting! (Scales UI dynamically)
            await telemetry_manager.send_audio_reactivity(is_speaking=True, volume=1.2)
            
            # Generate the WAV bytes 
            wav_bytes = await asyncio.to_thread(tts_service.synthesize, response_text)
            
            # Play the audio through the OS speakers
            await asyncio.to_thread(self._play_audio_sync, wav_bytes)
            
        except Exception as e:
            logger.error(f"Idle Engagement synthesis/playback failed: {e}")
        finally:
            # Tell React the Bubble is done speaking
            await telemetry_manager.send_audio_reactivity(is_speaking=False)

        # 6. DYNAMIC COOLDOWN ADJUSTMENT
        if is_system_under_load:
            # If tracking an active process, report back sooner (e.g., 4 to 8 minutes)
            self.current_cooldown = random.randint(240, 480)
            logger.info(f"Tracking active workload. Next report in {self.current_cooldown // 60} minutes.")
        else:
            # If truly idle, extend silence to save power (e.g., 15 to 25 minutes)
            self.current_cooldown = random.randint(900, 1500)
            logger.info(f"System deep idle. Next report in {self.current_cooldown // 60} minutes.")

# Singleton instance (Defaults to 10 minutes initial check)
idle_manager = IdleEngagementManager(base_cooldown_seconds=600)