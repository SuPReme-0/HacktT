from llama_cpp import Llama
from utils.memory import vram_guard
import logging

logger = logging.getLogger("hackt.llm")

class LLMManager:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.llm = None
        # KV Cache Limit: 4096 tokens fits comfortably in 6GB VRAM with 4B model
        self.n_ctx = 4096 
        self.load_model()

    def load_model(self):
        if self.llm is not None:
            return
        
        logger.info("Loading Qwen 3.5 4B (4-bit) onto GPU...")
        try:
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_batch=512,          # Optimize batch size for latency
                n_gpu_layers=-1,      # Offload all layers to GPU
                flash_attn=True,      # Enable Flash Attention if supported by build
                verbose=False
            )
            logger.info("LLM Loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load LLM: {e}")
            raise e

    def stream_chat(self, prompt: str, context: str):
        if self.llm is None:
            raise RuntimeError("LLM not loaded")

        full_prompt = f"""
        <|system|>
        You are HackT, a cybersecurity AI agent. Use the provided context to answer.
        Context: {context}
        <|end|>
        <|user|>
        {prompt}
        <|end|>
        <|assistant|>
        """

        # Generator for StreamingResponse
        for token in self.llm(
            full_prompt, 
            max_tokens=512, 
            temperature=0.1,      # Low temp for factual accuracy
            top_p=0.9, 
            stream=True
        ):
            yield token['choices'][0]['text']

llm_manager = None  # Singleton initialized in main.py