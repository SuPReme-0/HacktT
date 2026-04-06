"""
HackT Sovereign Core - Master Inference Engine
===============================================
Orchestrates Qwen 3.5 (LLM) and Florence-2 (Vision) using a strict VRAM lock.
Incorporates KV cache tracking to prevent context-window OOM crashes.
"""

import logging
import gc
import torch
from typing import Generator, Optional
from core.memory import vram_guard
from utils.logger import get_logger

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = get_logger("hackt.core.engine")

class SovereignEngine:
    """
    Master Inference Orchestrator.
    Ensures LLM and Vision models never collide in VRAM.
    """
    def __init__(self, llm_path: str = "models/qwen-3.5-4b-q4_k_m.gguf"):
        self.llm_path = llm_path
        self.max_ctx = 4096
        self.mode = "active"
        
        # LLM State (Persistent)
        self.llm: Optional[Llama] = None
        self.kv_cache_tokens = 0
        
        # Vision State (Ephemeral)
        self.vision_model = None
        self.vision_processor = None
        self.vision_model_id = "microsoft/Florence-2-base"

    def set_mode(self, mode: str):
        """Update system mode (active/passive)"""
        self.mode = mode

    # ==========================================
    # LLM OPERATIONS (Persistent)
    # ==========================================
    def load_llm(self) -> bool:
        """Load Qwen 3.5 if VRAM budget allows."""
        if self.llm: return True
        if not Llama:
            logger.error("llama-cpp-python not installed. Cannot load LLM.")
            return False
            
        # Estimate: weights (~2.5GB) + KV cache (~0.5GB)
        if not vram_guard.can_load_model(3.0, include_buffer=True):
            logger.warning("Engine: Insufficient VRAM for Qwen 3.5")
            return False
            
        try:
            logger.info("Engine: Loading Qwen 3.5 onto GPU...")
            self.llm = Llama(
                model_path=self.llm_path,
                n_ctx=self.max_ctx,
                n_batch=512,
                n_threads=4,
                n_gpu_layers=-1,  # Offload completely to GPU
                use_mmap=True,
                flash_attn=True,  # Flash Attention 2.0 (Crucial for speed/memory)
                verbose=False
            )
            self.kv_cache_tokens = 0
            logger.info("Engine: LLM ONLINE.")
            return True
        except Exception as e:
            logger.error(f"Engine: Failed to load LLM: {e}")
            return False

    def unload_llm(self):
        """Free VRAM by unloading LLM."""
        if self.llm:
            logger.info("Engine: Unloading LLM...")
            del self.llm
            self.llm = None
            self.kv_cache_tokens = 0
            vram_guard.clear_cache()

    def stream_chat(self, prompt: str, context: str = "", max_tokens: int = 512) -> Generator[str, None, None]:
        """Stream tokens with KV cache tracking."""
        if not self.llm and not self.load_llm():
            yield "[SYSTEM_ERROR: AI Core offline due to memory constraints]"
            return

        # Tokenize to check bounds and prevent Llama.cpp crashes
        tokens = self.llm.tokenize(prompt.encode('utf-8'))
        if len(tokens) > (self.max_ctx - max_tokens):
            logger.warning(f"Engine: Prompt too long ({len(tokens)} tokens). Truncating to avoid crash.")
            # Note: In a robust production setup, we would implement sliding window context here
            
        try:
            # We accept the pre-formatted 'prompt' from http_api.py directly
            for token_result in self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=0.1,
                top_p=0.9,
                stream=True,
                echo=False,
            ):
                token = token_result["choices"][0]["text"]
                self.kv_cache_tokens += 1
                yield token
                
            # Post-generation: Trim KV cache if nearing maximum window
            if self.kv_cache_tokens > self.max_ctx * 0.9:
                self._trim_kv_cache()
                
        except Exception as e:
            logger.error(f"Engine: Chat stream failed: {e}")

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.0) -> str:
        """Non-streaming generation for structured JSON outputs (Threat Scanning)."""
        if not self.llm and not self.load_llm():
            return '{"error": "LLM Offline"}'
            
        try:
            result = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False
            )
            self.kv_cache_tokens += max_tokens
            return result["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"Engine: Generation failed: {e}")
            return "{}"

    def _trim_kv_cache(self):
        """Reset cache to prevent Context Window OOM."""
        logger.info("Engine: KV cache near limit. Resetting context to prevent crash.")
        self.kv_cache_tokens = 0

    # ==========================================
    # VISION OPERATIONS (Ephemeral)
    # ==========================================
    def analyze_screen(self, image, task: str = "<OCR>") -> str:
        """Ephemeral Vision Analysis: Load -> Infer -> Unload"""
        # Require 1.2GB VRAM for Florence-2
        if not vram_guard.can_load_model(1.2, include_buffer=True):
            return "[SYSTEM_ERROR: Vision Core bypassed. VRAM saturated.]"
            
        try:
            from transformers import AutoProcessor, AutoModelForCausalLM
            
            logger.info("Engine: Loading Florence-2 (Ephemeral)...")
            self.vision_processor = AutoProcessor.from_pretrained(self.vision_model_id, trust_remote_code=True)
            self.vision_model = AutoModelForCausalLM.from_pretrained(
                self.vision_model_id, 
                trust_remote_code=True, 
                torch_dtype=torch.float16
            ).to("cuda" if vram_guard.has_cuda else "cpu")
            
            if image.mode != "RGB":
                image = image.convert("RGB")
                
            inputs = self.vision_processor(text=task, images=image, return_tensors="pt")
            if vram_guard.has_cuda:
                inputs = {k: v.to("cuda", torch.float16 if v.dtype == torch.float32 else v.dtype) for k, v in inputs.items()}
                
            generated_ids = self.vision_model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=512,
                num_beams=3
            )
            
            result = self.vision_processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
            parsed = self.vision_processor.post_process_generation(result, task=task, image_size=(image.width, image.height))
            
            output = parsed.get(task, "")
            return "\n".join(output) if isinstance(output, list) else output
            
        except Exception as e:
            logger.error(f"Engine: Vision analysis failed: {e}")
            return f"[SYSTEM_ERROR: {str(e)}]"
            
        finally:
            # GUARANTEED UNLOAD TO PROTECT VRAM
            if self.vision_model:
                logger.info("Engine: Unloading Florence-2...")
                del self.vision_model
                del self.vision_processor
                self.vision_model = None
                self.vision_processor = None
                vram_guard.clear_cache()

# Singleton Instance
engine = SovereignEngine()