"""
HackT Sovereign Core - Neural Audio Service Module
===================================================
Provides CPU-optimized voice processing with Prosodic Intelligence:
- Real-time continuous STT streaming (Faster-Whisper + VAD)
- Context-aware TTS synthesis (Piper) with dynamic speed/urgency
- CPU-only execution to preserve GPU VRAM for the AI Core
"""

import logging
import asyncio
import numpy as np
import sounddevice as sd
import queue
import tempfile
import os
from typing import Optional, List, Generator
from utils.logger import get_logger

logger = get_logger("hackt.services.audio")


class STTService:
    """
    Speech-to-Text streaming service using Faster-Whisper (CPU-only).
    
    Features:
    - Non-blocking InputStream for continuous listening
    - Energy-based Voice Activity Detection (VAD) to save CPU
    - Auto-chunking when speech pauses
    """
    
    def __init__(self, model_size: str = "tiny.en", device: str = "cpu"):
        self.model_size = model_size
        self.device = device
        self.model = None
        self._loaded = False
        
        # Audio Stream Configuration
        self.sample_rate = 16000
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self._stream: Optional[sd.InputStream] = None
        
        # VAD Configuration
        self.energy_threshold = 0.015  # Adjust based on mic sensitivity
        self.silence_limit_sec = 1.5   # Seconds of silence before finalizing chunk
        
    def load(self) -> bool:
        """Load Whisper model into CPU memory"""
        if self._loaded:
            return True
        
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading Faster-Whisper {self.model_size} on {self.device}...")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8"
            )
            self._loaded = True
            logger.info("STT model loaded successfully")
            return True
        except ImportError:
            logger.error("faster-whisper not installed. pip install faster-whisper")
            return False
        except Exception as e:
            logger.error(f"Failed to load STT model: {e}")
            return False
            
    def _audio_callback(self, indata, frames, time, status):
        """Called for each audio block from the microphone"""
        if status:
            logger.warning(f"Audio stream status: {status}")
        
        # Calculate audio energy (volume)
        audio_data = indata[:, 0]
        energy = np.sqrt(np.mean(audio_data**2))
        
        # Only put data in queue if it exceeds background noise threshold
        if energy > self.energy_threshold:
            self.audio_queue.put(audio_data.copy())
        else:
            # Send a marker to indicate silence
            self.audio_queue.put(None)

    def start_listening(self):
        """Open the microphone stream"""
        if self.is_listening:
            return
            
        if not self._loaded and not self.load():
            raise RuntimeError("Cannot start listening: Model failed to load.")
            
        self.is_listening = True
        # Clear old audio
        while not self.audio_queue.empty():
            self.audio_queue.get()
            
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.5) # 0.5 second blocks
        )
        self._stream.start()
        logger.info("Microphone HOT. Listening for voice commands...")

    def stop_listening(self):
        """Close the microphone stream"""
        self.is_listening = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Microphone COLD.")

    def process_stream(self) -> Generator[str, None, None]:
        """
        Process the audio queue and yield transcribed text chunks.
        Designed to run in a background thread.
        """
        buffer = []
        silence_chunks = 0
        chunks_needed_for_silence = int(self.silence_limit_sec / 0.5)
        
        while self.is_listening:
            try:
                # Wait for audio block (timeout allows graceful exit)
                data = self.audio_queue.get(timeout=1.0)
                
                if data is not None:
                    # User is speaking
                    buffer.append(data)
                    silence_chunks = 0
                else:
                    # User is silent
                    if len(buffer) > 0:
                        silence_chunks += 1
                        
                    # If user has been silent for X seconds, transcribe the buffer
                    if silence_chunks >= chunks_needed_for_silence and len(buffer) > 0:
                        audio_np = np.concatenate(buffer)
                        buffer = [] # Reset buffer
                        silence_chunks = 0
                        
                        # Only transcribe if audio is long enough (>0.5s)
                        if len(audio_np) > (self.sample_rate * 0.5):
                            segments, _ = self.model.transcribe(
                                audio_np,
                                beam_size=2, # Lower beam size for faster CPU inference
                                temperature=0.0,
                                language="en"
                            )
                            text = " ".join([s.text.strip() for s in segments if s.text.strip()])
                            if text:
                                yield text
                                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"STT stream processing error: {e}")

    def unload(self):
        """Free memory"""
        self.stop_listening()
        if self.model:
            del self.model
            self.model = None
            self._loaded = False


class TTSService:
    """
    Context-Aware Text-to-Speech service using Piper (CPU-only).
    
    Features:
    - Prosodic Intelligence: Dynamically adjusts speech speed based on threat level.
    """
    
    def __init__(self, model_name: str = "en_US-lessac-medium"):
        self.model_name = model_name
        self.voice = None
        self._loaded = False
        
    def load(self) -> bool:
        """Load Piper voice model"""
        if self._loaded:
            return True
        
        try:
            from piper import PiperVoice
            
            model_path = f"models/{self.model_name}.onnx"
            # Fallback if downloaded models folder doesn't exist yet
            if not os.path.exists(model_path):
                logger.warning(f"Piper model {model_path} not found. Attempting auto-download is not supported in this script. Please download the ONNX model to the models/ dir.")
                
            self.voice = PiperVoice.load(model_path)
            self._loaded = True
            logger.info("TTS model loaded successfully")
            return True
        except ImportError:
             logger.error("piper-tts not installed. pip install piper-tts")
             return False
        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            return False
            
    def synthesize(self, text: str, urgency_score: float = 0.5, threat_level: str = "safe") -> bytes:
        """
        Synthesize speech with dynamic tuning based on context.
        
        Args:
            text: Input text
            urgency_score: 0.0 (calm) to 1.0 (panic)
            threat_level: "safe", "medium", "high", "critical"
            
        Returns:
            WAV audio bytes
        """
        if not self._loaded and not self.load():
            raise RuntimeError("TTS model not loaded")
            
        import soundfile as sf
        
        # 1. DYNAMIC PROSODY TUNING
        # length_scale > 1.0 = slower speech. length_scale < 1.0 = faster speech.
        length_scale = 1.0 
        
        if threat_level.lower() == "critical" or urgency_score > 0.8:
            length_scale = 0.85  # Fast, sharp, urgent
        elif threat_level.lower() == "high":
            length_scale = 0.92  # Brisk
        elif threat_level.lower() == "safe" and urgency_score < 0.3:
            length_scale = 1.15  # Slow, analytical, calm
            
        logger.debug(f"TTS Tuning: Threat={threat_level}, Urgency={urgency_score}, Speed={length_scale}x")

        # 2. SYNTHESIS
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            # Piper allows passing length_scale for speed control
            self.voice.synthesize(text, tmp, length_scale=length_scale)
            tmp_path = tmp.name
            
        # 3. READ & CLEANUP
        try:
            with open(tmp_path, "rb") as f:
                wav_bytes = f.read()
        finally:
            os.unlink(tmp_path)
            
        return wav_bytes

    def unload(self):
        """Free memory"""
        if self.voice:
            del self.voice
            self.voice = None
            self._loaded = False


# Singleton instances (CPU-only to save VRAM)
# Using 'base.en' as it is vastly faster and more accurate for English-only commands
stt_service = STTService(model_size="base.en", device="cpu")
tts_service = TTSService(model_name="en_US-lessac-medium")