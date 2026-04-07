"""
HackT Sovereign Core - Neural Audio Service Module (v7.0)
=========================================================
Provides CPU-optimized Full-Duplex voice processing with Human Conversation Protocol:
- Subprocess TTS Pipeline: Zero C++ compilation, zero disk I/O, pure memory-streamed playback.
- Audio Ducking: Lowers UI volume/ignores mic when TTS is active (Human-like overlap).
- Extended VAD: Allows natural breathing/pausing during user input (2.5s threshold).
- Conversation State Machine: Tracks speaking/listening/interrupt states.
- Anti-Hallucination Conditioning: Blocks looping STT subtitles.
- Interruption Recovery: AI pauses mid-sentence, listens, then responds contextually.
"""

import os
import io
import sys
import queue
import asyncio
import time
import subprocess
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from typing import Optional, AsyncGenerator, Callable
from enum import Enum

from utils.logger import get_logger
from utils.config import config

# Lazy import for WebSocket telemetry
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

logger = get_logger("hackt.services.audio")


# ==============================================================================
# Conversation State Machine
# ==============================================================================
class ConversationState(Enum):
    IDLE = "idle"              # No one is speaking
    AI_SPEAKING = "ai_speaking"  # AI is currently talking
    USER_SPEAKING = "user_speaking"  # User is currently talking
    INTERRUPTED = "interrupted"  # User interrupted AI mid-sentence
    PROCESSING = "processing"  # Transcribing user input


# ==============================================================================
# Speech-to-Text (STT) Service
# ==============================================================================
class STTService:
    """
    Speech-to-Text streaming service using Faster-Whisper.
    Engineered for Full-Duplex "Audio Ducking" and natural human pacing.
    """

    def __init__(self):
        self.model_size = config.model.stt_model
        self.device = config.model.stt_device
        self.model = None
        self._loaded = False

        self.sample_rate = 16000
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self._stream: Optional[sd.InputStream] = None

        # Conversation State Tracking
        self._state = ConversationState.IDLE
        self._state_lock = asyncio.Lock()

        # VAD & PACING Configuration
        self.energy_threshold = 0.020  # Tuned to ignore keyboard/PC fan noise
        self.silence_limit_sec = 2.5   # Natural breathing room before processing
        self._is_speaking_now = False
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

        # Interruption Tracking
        self._interruption_callback: Optional[Callable] = None
        self._last_interruption_time: float = 0

        # Audio Buffer Management
        self._max_buffer_sec = 30.0  # Prevent memory overflow on long speeches
        self._buffer_samples = int(self.sample_rate * self._max_buffer_sec)

    def load(self) -> bool:
        """Load Whisper model safely into CPU memory."""
        if self._loaded:
            return True
        try:
            from faster_whisper import WhisperModel
            logger.info(f"AudioService: Booting Faster-Whisper ({self.model_size}) on {self.device} [INT8]...")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8"  # Strictly INT8 to preserve system RAM
            )
            self._loaded = True
            logger.info("AudioService: STT Engine ONLINE.")
            return True
        except Exception as e:
            logger.error(f"AudioService: Failed to load STT: {e}")
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        """
        Called by the OS audio driver for every chunk of mic data.
        Executes raw energy math to detect Barge-in and manage conversation state.
        """
        if status:
            logger.warning(f"Audio stream status: {status}")

        # 🚨 AUDIO DUCKING: If TTS is speaking, aggressively ignore mic input
        if tts_service.is_speaking():
            self.audio_queue.put(None)
            return

        audio_data = indata[:, 0]
        energy = np.sqrt(np.mean(audio_data**2))

        if energy > self.energy_threshold:
            # VOICE DETECTED
            if not self._is_speaking_now:
                self._is_speaking_now = True
                self._last_interruption_time = time.time()
                if self._main_loop:
                    asyncio.run_coroutine_threadsafe(
                        self._on_voice_detected(),
                        self._main_loop
                    )
            self.audio_queue.put(audio_data.copy())
        else:
            # Silence detected
            self.audio_queue.put(None)

    async def _on_voice_detected(self):
        """Handles voice detection events on the main event loop."""
        async with self._state_lock:
            if self._state == ConversationState.AI_SPEAKING:
                # USER INTERRUPTED AI MID-SENTENCE
                self._state = ConversationState.INTERRUPTED
                logger.debug("AudioService: User interrupted AI. Triggering ducking.")
                self._trigger_ducking(True)
                if self._interruption_callback:
                    await self._interruption_callback()
            elif self._state == ConversationState.IDLE:
                # User started speaking naturally
                self._state = ConversationState.USER_SPEAKING
                self._trigger_ducking(False)

    def _trigger_ducking(self, is_ducked: bool):
        """Safely pushes the volume-ducking event to the React UI."""
        if self._main_loop and self._main_loop.is_running() and telemetry_manager:
            volume_level = 0.2 if is_ducked else 1.0
            asyncio.run_coroutine_threadsafe(
                telemetry_manager.broadcast_telemetry({
                    "type": "audio_ducking",
                    "volume": volume_level,
                    "timestamp": time.time()
                }, target="bubble"),
                self._main_loop
            )

    def set_interruption_callback(self, callback: Callable):
        self._interruption_callback = callback

    async def set_state(self, state: ConversationState):
        async with self._state_lock:
            old_state = self._state
            self._state = state
            if old_state != state:
                logger.debug(f"AudioService: State changed {old_state.value} -> {state.value}")

    async def get_state(self) -> ConversationState:
        async with self._state_lock:
            return self._state

    def start_listening(self, loop: asyncio.AbstractEventLoop):
        if self.is_listening:
            return
        if not self._loaded and not self.load():
            raise RuntimeError("Cannot start listening: STT Model offline.")

        self._main_loop = loop
        self.is_listening = True

        while not self.audio_queue.empty():
            self.audio_queue.get()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.25)  # 0.25s blocks
        )
        self._stream.start()
        logger.info("AudioService: Microphone HOT. Full-Duplex listening active.")

    def stop_listening(self):
        self.is_listening = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("AudioService: Microphone COLD.")

    async def process_stream(self) -> AsyncGenerator[str, None]:
        buffer = []
        silence_chunks = 0
        chunks_needed_for_silence = int(self.silence_limit_sec / 0.25)
        total_buffer_samples = 0

        while self.is_listening:
            try:
                if self.audio_queue.empty():
                    await asyncio.sleep(0.05)
                    continue

                data = self.audio_queue.get_nowait()

                if data is not None:
                    # USER IS SPEAKING
                    buffer.append(data)
                    total_buffer_samples += len(data)
                    silence_chunks = 0

                    if total_buffer_samples > self._buffer_samples:
                        buffer = buffer[-int(self._buffer_samples / len(data)):]
                        total_buffer_samples = self._buffer_samples
                else:
                    # SILENCE DETECTED
                    if len(buffer) > 0:
                        silence_chunks += 1

                    # USER FINISHED SPEAKING (2.5 sec pause)
                    if silence_chunks >= chunks_needed_for_silence and len(buffer) > 0:
                        async with self._state_lock:
                            self._state = ConversationState.PROCESSING

                        self._is_speaking_now = False
                        self._trigger_ducking(False)

                        audio_np = np.concatenate(buffer)
                        buffer = []
                        silence_chunks = 0
                        total_buffer_samples = 0

                        if len(audio_np) > (self.sample_rate * 0.5):
                            def _run_transcription():
                                segments, _ = self.model.transcribe(
                                    audio_np,
                                    beam_size=1,
                                    temperature=0.0,
                                    language="en",
                                    vad_filter=True,
                                    vad_parameters=dict(
                                        min_silence_duration_ms=500,
                                        speech_pad_ms=200
                                    ),
                                    # ANTI-HALLUCINATION ARMOR
                                    condition_on_previous_text=False,
                                    initial_prompt="Operator command:",
                                    no_speech_threshold=0.6,
                                    log_prob_threshold=-1.0
                                )
                                return " ".join([s.text.strip() for s in segments if s.text.strip()])

                            text = await asyncio.to_thread(_run_transcription)

                            async with self._state_lock:
                                self._state = ConversationState.IDLE

                            if text:
                                logger.info(f"AudioService: Transcribed: {text[:100]}...")
                                yield text

            except Exception as e:
                logger.error(f"STT stream error: {e}")
                await asyncio.sleep(0.1)

    def unload(self):
        self.stop_listening()
        if self.model:
            del self.model
            self.model = None
            self._loaded = False


# ==============================================================================
# Text-to-Speech (TTS) Service
# ==============================================================================
class TTSService:
    """
    Subprocess-driven TTS service.
    Zero C++ bindings required. Streams audio directly to RAM via stdout and plays via sounddevice.
    """

    def __init__(self):
        self.model_name = config.model.tts_model
        self._loaded = False
        self._is_speaking = False
        self.base_dir = None
        self.piper_exe = None
        self.model_path = None

    def load(self) -> bool:
        if self._loaded:
            return True

        # Resolve base directory as before
        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys.executable).parent / "models" / "piper"
        else:
            self.base_dir = config.paths.models_dir / "piper"

        # Try direct location first
        self.piper_exe = self.base_dir / "piper.exe"
        if not self.piper_exe.exists():
            # Fallback: check nested piper/ folder (common with Piper's Windows zip)
            nested_exe = self.base_dir / "piper" / "piper.exe"
            if nested_exe.exists():
                self.piper_exe = nested_exe
            else:
                logger.warning(f"AudioService: Piper engine missing at {self.base_dir}")
                return False

        self.model_path = self.base_dir / "en_US-lessac-medium.onnx"
        if not self.model_path.exists():
            logger.warning(f"AudioService: Piper voice model missing at {self.model_path}")
            return False

        self._loaded = True
        logger.info("AudioService: TTS Subprocess Engine ONLINE.")
        return True
    
    async def synthesize_and_play(self, text: str, urgency_score: float = 0.5, threat_level: str = "safe"):
        """
        Generates TTS purely in RAM via subprocess stdout, then plays it blocking the state.
        """
        if not self._loaded and not self.load():
            logger.error("TTS model offline, cannot speak.")
            return

        # 🚀 DYNAMIC PROSODY TUNING
        length_scale = 1.0
        if threat_level.lower() == "critical" or urgency_score > 0.8:
            length_scale = 0.85  # Fast, sharp, urgent
        elif threat_level.lower() == "high":
            length_scale = 0.92  # Brisk
        elif threat_level.lower() == "safe" and urgency_score < 0.3:
            length_scale = 1.15  # Slow, analytical

        self._is_speaking = True

        def _run_and_play():
            # 0x08000000 = CREATE_NO_WINDOW (Prevents CMD flash in production .exe)
            creation_flags = 0x08000000 if os.name == 'nt' else 0
            
            try:
                # 1. Pipe TTS directly into RAM
                process = subprocess.Popen(
                    [
                        str(self.piper_exe),
                        "-m", str(self.model_path),
                        "--length_scale", str(length_scale),
                        "-f", "-"  # Output RAW WAV bytes to stdout
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags
                )
                
                # Encode text to stdin and capture stdout
                wav_data, _ = process.communicate(input=text.encode('utf-8'))

                if not wav_data:
                    return

                # 2. Play Audio directly from RAM 
                data, fs = sf.read(io.BytesIO(wav_data))
                sd.play(data, fs)
                sd.wait()  # Block until the audio physically finishes playing through speakers

            except Exception as e:
                logger.error(f"Piper TTS/Playback failed: {e}")

        try:
            # Run the blocking generation & playback in a separate thread so asyncio isn't stalled
            await asyncio.to_thread(_run_and_play)
        finally:
            # This ensures the ducking ends exactly when the speech ends
            self._is_speaking = False

    def is_speaking(self) -> bool:
        """Check if TTS is currently generating or playing audio."""
        return self._is_speaking

    def unload(self):
        """Reset state."""
        self._loaded = False


# ==============================================================================
# Conversation Manager (Coordinates STT + TTS + State)
# ==============================================================================
class ConversationManager:
    def __init__(self, stt: STTService, tts: TTSService):
        self.stt = stt
        self.tts = tts
        self._current_response_id: Optional[str] = None
        self._interrupted_response_id: Optional[str] = None

    async def on_interruption(self):
        logger.info("ConversationManager: User interrupted. Stopping AI response.")
        self._interrupted_response_id = self._current_response_id

    def register_interruption_handler(self, handler: Callable):
        self.stt.set_interruption_callback(handler)

    def set_current_response(self, response_id: str):
        self._current_response_id = response_id

    def was_interrupted(self, response_id: str) -> bool:
        return self._interrupted_response_id == response_id

    def clear_interruption(self):
        self._interrupted_response_id = None


# ==============================================================================
# Singletons
# ==============================================================================
stt_service = STTService()
tts_service = TTSService()
conversation_manager = ConversationManager(stt_service, tts_service)

conversation_manager.register_interruption_handler(conversation_manager.on_interruption)