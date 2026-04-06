"""
HackT Sovereign Core - Embedding Engine
========================================
Generates Matryoshka-optimized 256-dim vectors for RAG.
- Auto-truncates to 256 dimensions to save 66% RAM/Disk.
- Injects Nomic task prefixes automatically.
- VRAM-aware loading with CPU fallback.
"""

import logging
import numpy as np
from typing import List, Union, Optional

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

from utils.logger import get_logger
from core.memory import vram_guard

logger = get_logger("hackt.core.embedder")


class Embedder:
    """
    Sentence embedding engine for vector search.
    Optimized for Nomic v1.5 with Matryoshka dimensionality reduction.
    """
    
    def __init__(
        self, 
        model_name: str = "nomic-ai/nomic-embed-text-v1.5", 
        dimensionality: int = 256  # Matryoshka truncation size
    ):
        self.model_name = model_name
        self.dimensionality = dimensionality
        self._model: Optional[SentenceTransformer] = None
        self._loaded: bool = False
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.error("sentence-transformers not installed. Vector search will fail.")
            
        self.device = self._auto_detect_device()
        logger.info(f"Embedder initialized: {model_name} on {self.device} at {self.dimensionality}-dim")
        
    def _auto_detect_device(self) -> str:
        """Auto-detect best available device based on current VRAM."""
        if vram_guard.has_cuda:
            # Check if we have enough VRAM (~500MB for Nomic)
            if vram_guard.can_load_model(0.5, include_buffer=False):
                return "cuda"
            else:
                logger.warning("Embedder: Insufficient VRAM. Falling back to CPU.")
                return "cpu"
                
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
        except:
            pass
            
        return "cpu"

    def load(self) -> bool:
        """Load the model safely."""
        if self._loaded:
            return True
            
        try:
            logger.info(f"Loading Embedder: {self.model_name}...")
            model_kwargs = {"device": self.device}
            
            # Enable Flash Attention if on CUDA for speed
            if self.device == "cuda":
                try:
                    model_kwargs["model_kwargs"] = {"attn_implementation": "sdpa"}
                except Exception:
                    pass

            self._model = SentenceTransformer(
                self.model_name,
                trust_remote_code=True,
                **model_kwargs
            )
            self._model.max_seq_length = 512
            self._loaded = True
            
            logger.info("Embedder ONLINE.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Embedder: {e}")
            return False

    def encode(self, texts: Union[str, List[str]], normalize: bool = True) -> np.ndarray:
        """
        Encode text into 256-dim normalized vectors.
        """
        if not self._loaded and not self.load():
            raise RuntimeError("Embedding model failed to load.")
            
        if isinstance(texts, str):
            texts = [texts]
            
        # Nomic v1.5 requires specific prefixes. If none provided, assume query.
        processed_texts = []
        for text in texts:
            if not text.startswith("search_query: ") and not text.startswith("search_document: "):
                processed_texts.append(f"search_query: {text}")
            else:
                processed_texts.append(text)
                
        try:
            # 1. Generate full 768-dim embeddings
            embeddings = self._model.encode(
                processed_texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=False # We normalize AFTER truncation
            )
            
            # 2. Matryoshka Truncation (Slice the array to 256)
            if self.dimensionality < embeddings.shape[1]:
                embeddings = embeddings[:, :self.dimensionality]
                
            # 3. L2 Normalization (Required for Cosine Similarity search)
            if normalize:
                row_sums = np.linalg.norm(embeddings, axis=1, keepdims=True)
                # Avoid divide-by-zero
                embeddings = embeddings / np.where(row_sums == 0, 1.0, row_sums)
                
            return embeddings
            
        except Exception as e:
            logger.error(f"Embedding encoding failed: {e}")
            # Raise so the API knows to send a 500 error instead of silent zeros
            raise e

    def unload(self):
        """Unload model to free RAM/VRAM."""
        if self._model:
            logger.info("Unloading Embedder...")
            del self._model
            self._model = None
            self._loaded = False
            vram_guard.clear_cache()

# Global Singleton (Lazy loaded. Will not consume memory until embedder.load() is called)
embedder = Embedder(dimensionality=256)