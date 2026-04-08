"""
HackT Sovereign Core - Neural Audio Service Module (v7.2)
=========================================================
FINALIZED: Merges v7.1 Thread-Safety/WAV Header patches with the 
required HTTP REST API Bridge methods for full frontend compatibility.
"""

import os
import io
import sys
import queue
import asyncio
import time
import subprocess
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from typing import Optional, AsyncGenerator, Callable, Dict, Any
from enum import Enum
from dataclasses import dataclass
import wave

from utils.logger import get_logger
from utils.config import config

# Lazy import for WebSocket telemetry
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

logger = get_logger("hackt.services.audio")

# ==============================================================================
# Thread-Safe State Management
# ==============================================================================
@dataclass
class AudioState:
    """Thread-safe container for audio conversation state."""
    state: 'ConversationState' = None
    is_speaking: bool = False
    is_listening: bool = False
    interruption_pending: bool = False
    lock: threading.Lock = None
    
    def __post_init__(self):
        if self.lock is None:
            self.lock = threading.Lock()
        if self.state is None:
            self.state = ConversationState.IDLE
    
    def get(self) -> 'ConversationState':
        with self.lock:
            return self.state
    
    def set(self, state: 'ConversationState'):
        with self.lock:
            old = self.state
            self.state = state
            return old
    
    def get_speaking(self) -> bool:
        with self.lock:
            return self.is_speaking
    
    def set_speaking(self, value: bool):
        with self.lock:
            self.is_speaking = value

class ConversationState(Enum):
    IDLE = "idle"
    AI_SPEAKING = "ai_speaking"
    USER_SPEAKING = "user_speaking"
    INTERRUPTED = "interrupted"
    PROCESSING = "processing"
    ERROR = "error"

# ==============================================================================
# Speech-to-Text (STT) Service
# ==============================================================================
class STTService:
    def __init__(self):
        self.model_size = getattr(config.model, 'stt_model', 'base')
        self.device = getattr(config.model, 'stt_device', 'cpu')
        self.model = None
        self._loaded = False

        self.sample_rate = 16000
        self.audio_queue: queue.Queue = queue.Queue(maxsize=100) 
        self.is_listening = False
        self._stream: Optional[sd.InputStream] = None

        self._state = AudioState()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread_id: Optional[int] = None

        self.energy_threshold = 0.020
        self._adaptive_threshold = 0.020
        self._noise_floor_samples = []
        self._calibration_complete = False
        
        self.silence_limit_sec = 2.5
        self._is_speaking_now = False
        self._speaking_lock = threading.Lock()

        self._interruption_callback: Optional[Callable] = None
        self._last_interruption_time: float = 0
        self._interruption_cooldown = 0.5

        self._max_buffer_sec = 30.0
        self._buffer_samples = int(self.sample_rate * self._max_buffer_sec)
        self._shutdown_event = threading.Event()

    def load(self) -> bool:
        if self._loaded:
            return True
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                from faster_whisper import WhisperModel
                logger.info(f"AudioService: Booting Faster-Whisper ({self.model_size}) on {self.device} [INT8]...")
                
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type="int8"
                )
                
                self._loaded = True
                logger.info("AudioService: STT Engine ONLINE.")
                return True
                
            except Exception as e:
                logger.warning(f"STT load attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"AudioService: Failed to load STT: {e}")
                    return False
                time.sleep(2 ** attempt)
        
        return False

    # 🚀 HTTP REST API Bridge Method
    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """Endpoint for HTTP /api/audio/transcribe (Streamlit & Tauri Web)"""
        if not self._loaded and not self.load():
            raise RuntimeError("STT Engine offline")

        def _run():
            data, samplerate = sf.read(io.BytesIO(audio_bytes))
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            data = data.astype(np.float32)

            segments, _ = self.model.transcribe(
                data,
                beam_size=1,
                language="en",
                condition_on_previous_text=False
            )
            return " ".join([s.text.strip() for s in segments if s.text.strip()])

        return await asyncio.to_thread(_run)

    def _calibrate_microphone(self, audio_data: np.ndarray):
        if self._calibration_complete:
            return
        
        energy = np.sqrt(np.mean(audio_data**2))
        self._noise_floor_samples.append(energy)
        
        if len(self._noise_floor_samples) >= 20:
            avg_noise = np.mean(self._noise_floor_samples)
            self._adaptive_threshold = max(avg_noise * 3, 0.010)
            self.energy_threshold = self._adaptive_threshold
            self._calibration_complete = True
            logger.info(f"AudioService: Mic calibrated. Threshold: {self.energy_threshold:.4f}")

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"Audio stream status: {status}")

        if tts_service.is_speaking():
            return

        audio_data = indata[:, 0].astype(np.float32)
        self._calibrate_microphone(audio_data)
        energy = np.sqrt(np.mean(audio_data**2))

        if energy > self.energy_threshold:
            with self._speaking_lock:
                if not self._is_speaking_now:
                    self._is_speaking_now = True
                    current_time = time.time()
                    
                    if current_time - self._last_interruption_time > self._interruption_cooldown:
                        self._last_interruption_time = current_time
                        if self._main_loop and not self._main_loop.is_closed():
                            try:
                                asyncio.run_coroutine_threadsafe(
                                    self._on_voice_detected(),
                                    self._main_loop
                                )
                            except RuntimeError:
                                pass
            try:
                self.audio_queue.put_nowait(audio_data.copy())
            except queue.Full:
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.put_nowait(audio_data.copy())
                except queue.Empty:
                    pass
        else:
            try:
                self.audio_queue.put_nowait(None)
            except queue.Full:
                pass

    async def _on_voice_detected(self):
        old_state = self._state.get()
        if old_state == ConversationState.AI_SPEAKING:
            self._state.set(ConversationState.INTERRUPTED)
            logger.debug("AudioService: User interrupted AI. Triggering ducking.")
            self._trigger_ducking(True)
            
            if self._interruption_callback:
                try:
                    await self._interruption_callback()
                except Exception as e:
                    logger.error(f"Interruption callback failed: {e}")
                    
        elif old_state == ConversationState.IDLE:
            self._state.set(ConversationState.USER_SPEAKING)
            self._trigger_ducking(False)

    def _trigger_ducking(self, is_ducked: bool):
        if self._main_loop and not self._main_loop.is_closed() and telemetry_manager:
            volume_level = 0.2 if is_ducked else 1.0
            try:
                asyncio.run_coroutine_threadsafe(
                    telemetry_manager.broadcast_telemetry({
                        "type": "audio_ducking",
                        "volume": volume_level,
                        "timestamp": time.time()
                    }, target="bubble"),
                    self._main_loop
                )
            except RuntimeError:
                pass

    def set_interruption_callback(self, callback: Callable):
        self._interruption_callback = callback

    def start_listening(self, loop: asyncio.AbstractEventLoop):
        if self.is_listening:
            return
        if not self._loaded and not self.load():
            raise RuntimeError("Cannot start listening: STT Model offline.")

        self._main_loop = loop
        self._loop_thread_id = threading.get_ident()
        self.is_listening = True
        self._shutdown_event.clear()

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.25),
            latency='low'
        )
        self._stream.start()
        logger.info("AudioService: Microphone HOT. Full-Duplex listening active.")

    def stop_listening(self):
        self.is_listening = False
        self._shutdown_event.set()
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Stream close error: {e}")
            self._stream = None
        
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
                
        logger.info("AudioService: Microphone COLD.")

    async def process_stream(self) -> AsyncGenerator[str, None]:
        buffer = []
        silence_chunks = 0
        chunks_needed_for_silence = int(self.silence_limit_sec / 0.25)
        total_samples = 0

        while self.is_listening and not self._shutdown_event.is_set():
            try:
                try:
                    data = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if data is not None:
                    buffer.append(data)
                    total_samples += len(data)
                    silence_chunks = 0

                    if total_samples > self._buffer_samples:
                        while buffer and total_samples > self._buffer_samples:
                            oldest = buffer.pop(0)
                            total_samples -= len(oldest)
                else:
                    if len(buffer) > 0:
                        silence_chunks += 1

                    if silence_chunks >= chunks_needed_for_silence and len(buffer) > 0:
                        self._state.set(ConversationState.PROCESSING)

                        with self._speaking_lock:
                            self._is_speaking_now = False
                        
                        self._trigger_ducking(False)

                        audio_np = np.concatenate(buffer)
                        buffer = []
                        silence_chunks = 0
                        total_samples = 0

                        if len(audio_np) > (self.sample_rate * 0.5):
                            def _run_transcription():
                                try:
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
                                        condition_on_previous_text=False,
                                        initial_prompt="Operator command:",
                                        no_speech_threshold=0.6,
                                        log_prob_threshold=-1.0
                                    )
                                    return " ".join([s.text.strip() for s in segments if s.text.strip()])
                                except Exception as e:
                                    logger.error(f"Transcription failed: {e}")
                                    return ""

                            text = await asyncio.to_thread(_run_transcription)
                            self._state.set(ConversationState.IDLE)

                            if text:
                                logger.info(f"AudioService: Transcribed: {text[:100]}...")
                                yield text
                            else:
                                logger.debug("AudioService: No speech detected in buffer")

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
    def __init__(self):
        self.model_name = getattr(config.model, 'tts_model', 'en_US-lessac-medium')
        self._loaded = False
        self._state = AudioState() 
        self.base_dir = None
        self.piper_exe = None
        self.model_path = None
        self.sample_rate = 22050 

    def load(self) -> bool:
        if self._loaded:
            return True

        if getattr(sys, 'frozen', False):
            self.base_dir = Path(sys.executable).parent / "models" / "piper"
        else:
            self.base_dir = getattr(config.paths, 'models_dir', Path('./models')) / "piper"

        self.piper_exe = self.base_dir / "piper.exe" if os.name == 'nt' else self.base_dir / "piper"
        
        if not self.piper_exe.exists():
            nested_exe = self.base_dir / "piper" / ("piper.exe" if os.name == 'nt' else "piper")
            if nested_exe.exists():
                self.piper_exe = nested_exe
            else:
                logger.warning(f"AudioService: Piper engine missing at {self.base_dir}")
                return False

        model_file = self.model_name if self.model_name.endswith('.onnx') else f"{self.model_name}.onnx"
        self.model_path = self.base_dir / model_file
        
        if not self.model_path.exists():
            logger.warning(f"AudioService: Piper voice model missing at {self.model_path}")
            return False

        self._loaded = True
        logger.info("AudioService: TTS Subprocess Engine ONLINE.")
        return True

    def _create_wav_header(self, raw_pcm: bytes, sample_rate: int, channels: int = 1, sample_width: int = 2) -> bytes:
        num_frames = len(raw_pcm) // (channels * sample_width)
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(raw_pcm)
        return buffer.getvalue()

    # 🚀 HTTP REST API Bridge Method
    async def synthesize_speech(self, text: str, voice: Optional[str] = None, speed: float = 1.0) -> bytes:
        """Endpoint for HTTP /api/tts. Returns formatted WAV bytes."""
        if not self._loaded and not self.load():
            raise RuntimeError("TTS Engine offline")

        length_scale = max(0.5, min(2.0, 1.0 / speed))

        def _run():
            creation_flags = 0x08000000 if os.name == 'nt' else 0
            process = subprocess.Popen(
                [
                    str(self.piper_exe),
                    "-m", str(self.model_path),
                    "--length_scale", str(length_scale),
                    "--output_raw",
                    "--sample_rate", str(self.sample_rate),
                    "-f", "-"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags
            )
            wav_data, stderr = process.communicate(input=text.encode('utf-8'), timeout=30)
            
            if process.returncode != 0:
                raise RuntimeError(f"Piper failed: {stderr.decode()}")
                
            return self._create_wav_header(wav_data, self.sample_rate)

        return await asyncio.to_thread(_run)

    async def synthesize_and_play(self, text: str, urgency_score: float = 0.5, threat_level: str = "safe"):
        if not self._loaded and not self.load():
            logger.error("TTS model offline, cannot speak.")
            return

        length_scale = 1.0
        if threat_level.lower() == "critical" or urgency_score > 0.8:
            length_scale = 0.85
        elif threat_level.lower() == "high":
            length_scale = 0.92
        elif threat_level.lower() == "safe" and urgency_score < 0.3:
            length_scale = 1.15

        self._state.set_speaking(True)

        def _run_and_play():
            creation_flags = 0x08000000 if os.name == 'nt' else 0
            
            try:
                process = subprocess.Popen(
                    [
                        str(self.piper_exe),
                        "-m", str(self.model_path),
                        "--length_scale", str(length_scale),
                        "--output_raw", 
                        "--sample_rate", str(self.sample_rate),
                        "-f", "-"
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=creation_flags
                )
                
                wav_data, stderr = process.communicate(input=text.encode('utf-8'), timeout=30)
                
                if process.returncode != 0:
                    logger.error(f"Piper exited with code {process.returncode}: {stderr.decode()}")
                    return

                if not wav_data or len(wav_data) < 100:
                    logger.error("Piper returned empty or invalid audio data")
                    return

                wav_with_header = self._create_wav_header(wav_data, self.sample_rate)

                data, fs = sf.read(io.BytesIO(wav_with_header))
                
                if not self._state.get_speaking():
                    logger.debug("TTS: Playback cancelled due to interruption")
                    return
                
                sd.play(data, fs)
                sd.wait()

            except subprocess.TimeoutExpired:
                logger.error("Piper TTS timed out")
                process.kill()
            except Exception as e:
                logger.error(f"Piper TTS/Playback failed: {e}")
            finally:
                self._state.set_speaking(False)

        try:
            await asyncio.to_thread(_run_and_play)
        except Exception as e:
            logger.error(f"TTS execution failed: {e}")
            self._state.set_speaking(False)

    def is_speaking(self) -> bool:
        return self._state.get_speaking()

    def stop_speaking(self):
        self._state.set_speaking(False)
        sd.stop() 
        logger.debug("TTS: Forced stop triggered")

    def unload(self):
        self.stop_speaking()
        self._loaded = False

# ==============================================================================
# Conversation Manager
# ==============================================================================
class ConversationManager:
    def __init__(self, stt: STTService, tts: TTSService):
        self.stt = stt
        self.tts = tts
        self._current_response_id: Optional[str] = None
        self._interrupted_response_id: Optional[str] = None
        self._lock = threading.Lock()

    async def on_interruption(self):
        logger.info("ConversationManager: User interrupted. Stopping AI response.")
        with self._lock:
            self._interrupted_response_id = self._current_response_id
        self.tts.stop_speaking()

    def register_interruption_handler(self, handler: Callable):
        self.stt.set_interruption_callback(handler)

    def set_current_response(self, response_id: str):
        with self._lock:
            self._current_response_id = response_id

    def was_interrupted(self, response_id: str) -> bool:
        with self._lock:
            return self._interrupted_response_id == response_id

    def clear_interruption(self):
        with self._lock:
            self._interrupted_response_id = None

# ==============================================================================
# Singletons & Health Check
# ==============================================================================
stt_service = STTService()
tts_service = TTSService()
conversation_manager = ConversationManager(stt_service, tts_service)
conversation_manager.register_interruption_handler(conversation_manager.on_interruption)

async def audio_health_check() -> Dict[str, Any]:
    results = {
        "stt_loaded": stt_service._loaded,
        "tts_loaded": tts_service._loaded,
        "stt_model": stt_service.model_size,
        "tts_model": tts_service.model_name,
        "mic_active": stt_service.is_listening,
        "tts_speaking": tts_service.is_speaking(),
        "state": stt_service._state.get().value if stt_service._state.get() else None,
        "threshold": stt_service.energy_threshold,
        "calibrated": stt_service._calibration_complete
    }
    if tts_service._loaded:
        try:
            results["tts_model_exists"] = tts_service.model_path.exists()
        except Exception as e:
            results["tts_model_exists"] = False
            results["tts_error"] = str(e)
    return results