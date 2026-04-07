"""
HackT Sovereign Core - Embedding Engine (v4.0)
==============================================
Peak-performance vectorization featuring:
- FP16 Quantization (Cuts VRAM usage by 50%)
- Thread-Safe GPU Execution Locks (Prevents concurrent OOM crashes)
- LRU Embedding Cache (Eliminates redundant computations)
- Bulk Ingestion Pipeline (Optimized for vault indexing)
- Matryoshka Dimensionality Reduction (768 -> 256 dim)
- Preprocessor Integration (Seamless chunk handling)
- Config-Synced Model Paths (PyInstaller safe)
"""

import logging
import threading
import gc
import hashlib
import time
import numpy as np
from typing import List, Union, Optional, Dict, Tuple, Any
from collections import OrderedDict

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

from utils.logger import get_logger
from utils.config import config
from core.memory import vram_guard

logger = get_logger("hackt.core.embedder")


class EmbeddingCache:
    """
    LRU Cache for embeddings to eliminate redundant computations.
    Critical for chat history where same texts are embedded repeatedly.
    """
    
    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[np.ndarray]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None
    
    def set(self, key: str, value: np.ndarray):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = value
    
    def clear(self):
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0.0
        }


class Embedder:
    """
    Sentence embedding engine for vector search.
    Engineered for zero-latency thread-safe execution on constrained hardware.
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        dimensionality: Optional[int] = None,
        cache_size: int = 1000
    ):
        # 🚀 CONFIG SYNC: Read from global config, not hardcoded
        self.model_name = model_name or config.model.embedder_model
        self.dimensionality = dimensionality or config.model.embedder_dimensionality
        self.max_seq_length = config.model.embedder_max_seq_length
        
        self._model: Optional['SentenceTransformer'] = None
        self._lock = threading.Lock()
        self._loaded = False
        
        # 🚀 EMBEDDING CACHE: Eliminates redundant computations
        self._cache = EmbeddingCache(max_size=cache_size)
        
        # 🚀 PERFORMANCE METRICS
        self._total_embeddings = 0
        self._total_time_sec = 0.0
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.critical("Embedder: sentence-transformers not installed. Vector search is offline.")
        
        self.device = self._auto_detect_device()
        logger.info(f"Embedder: Initialized for {self.device} at {self.dimensionality}-dim.")
    
    def _auto_detect_device(self) -> str:
        """Auto-detect best available device based on current VRAM."""
        if vram_guard.has_cuda:
            # We only need ~270MB now due to FP16 optimization
            if vram_guard.can_load_model(0.3, include_buffer=False):
                return "cuda"
            else:
                logger.warning("Embedder: Insufficient VRAM. Falling back to CPU.")
                return "cpu"
        
        # MPS (Apple Silicon) is unstable with sentence-transformers. Default to CPU.
        return "cpu"
    
    def _generate_cache_key(self, text: str, is_document: bool) -> str:
        """Generate deterministic cache key for text."""
        prefix = "doc:" if is_document else "qry:"
        return f"{prefix}{hashlib.sha256(text.encode()).hexdigest()}"
    
    def load(self) -> bool:
        """Load the model safely into memory with FP16 precision."""
        with self._lock:
            if self._loaded:
                return True
            
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                return False
            
            try:
                logger.info(f"Embedder: Booting {self.model_name} into {self.device}...")
                model_kwargs = {"device": self.device}
                
                # 🚀 ADVANCED GPU OPTIMIZATIONS
                if self.device == "cuda":
                    import torch
                    model_kwargs["model_kwargs"] = {
                        "attn_implementation": "sdpa",  # Flash Attention
                        "torch_dtype": torch.float16    # 🚨 FP16: Cuts VRAM by 50%
                    }
                
                self._model = SentenceTransformer(
                    self.model_name,
                    trust_remote_code=True,
                    **model_kwargs
                )
                self._model.max_seq_length = self.max_seq_length
                self._loaded = True
                
                logger.info("Embedder: ONLINE, Quantized, and Ready.")
                return True
                
            except Exception as e:
                logger.error(f"Embedder: Failed to load: {e}")
                return False
    
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        return self._loaded and self._model is not None
    
    def preload(self) -> bool:
        """
        Pre-load model during bootstrap to avoid first-request latency.
        Call this in main.py before accepting user requests.
        """
        return self.load()
    
    def encode(
        self,
        texts: Union[str, List[str]],
        normalize: bool = True,
        is_document: bool = False,
        batch_size: int = 32,
        use_cache: bool = True
    ) -> np.ndarray:
        """
        Encode text into 256-dim normalized vectors safely.
        
        Args:
            texts: Single text or list of texts to embed
            normalize: Apply L2 normalization (required for cosine similarity)
            is_document: Use document prefix for Nomic model
            batch_size: Process in batches to prevent OOM
            use_cache: Check embedding cache before computing
        
        Returns:
            np.ndarray of shape (n_texts, dimensionality)
        """
        if not self._loaded and not self.load():
            raise RuntimeError("Embedding model offline.")
        
        if isinstance(texts, str):
            texts = [texts]
        
        # 🚀 CACHE CHECK: Skip computation for repeated texts
        cached_results = []
        texts_to_compute = []
        compute_indices = []
        
        if use_cache:
            for i, text in enumerate(texts):
                cache_key = self._generate_cache_key(text, is_document)
                cached = self._cache.get(cache_key)
                if cached is not None:
                    cached_results.append((i, cached))
                else:
                    texts_to_compute.append(text)
                    compute_indices.append(i)
        
        # If all texts were cached, return early
        if not texts_to_compute:
            result = np.zeros((len(texts), self.dimensionality))
            for idx, emb in cached_results:
                result[idx] = emb
            return result
        
        # Nomic v1.5 strictly requires prefixes.
        prefix = "search_document: " if is_document else "search_query: "
        
        # Generator expression for memory efficiency
        processed_texts = [
            text if text.startswith("search_") else f"{prefix}{text}"
            for text in texts_to_compute
        ]
        
        start_time = time.time()
        
        try:
            # 🚨 THREAD LOCK: Ensure only one process accesses the GPU vector engine at a time
            with self._lock:
                # 1. Generate full 768-dim embeddings with strict batching
                embeddings = self._model.encode(
                    processed_texts,
                    batch_size=batch_size,       # 🚨 Prevents OOM during bulk vault ingestion
                    convert_to_numpy=True,
                    show_progress_bar=False,
                    normalize_embeddings=False   # We MUST normalize AFTER truncation
                )
            
            # 2. Matryoshka Truncation (Slice the array down to 256)
            if self.dimensionality < embeddings.shape[1]:
                embeddings = embeddings[:, :self.dimensionality]
            
            # 3. L2 Normalization (Mathematically required for Cosine Similarity search)
            if normalize:
                row_sums = np.linalg.norm(embeddings, axis=1, keepdims=True)
                # Avoid divide-by-zero on empty/bad strings
                embeddings = embeddings / np.where(row_sums == 0, 1.0, row_sums)
            
            # 🚀 CACHE STORE: Save computed embeddings
            if use_cache:
                for i, (text_idx, _) in enumerate(cached_results):
                    pass  # Already handled above
                for i, text in enumerate(texts_to_compute):
                    cache_key = self._generate_cache_key(text, is_document)
                    self._cache.set(cache_key, embeddings[i])
            
            # 🚀 METRICS TRACKING
            elapsed = time.time() - start_time
            self._total_embeddings += len(texts_to_compute)
            self._total_time_sec += elapsed
            
            # Reconstruct full result array with cached + new embeddings
            result = np.zeros((len(texts), self.dimensionality))
            for idx, emb in cached_results:
                result[idx] = emb
            for i, text_idx in enumerate(compute_indices):
                result[text_idx] = embeddings[i]
            
            return result
            
        except Exception as e:
            logger.error(f"Embedder: Encoding failed: {e}")
            raise e
    
    def encode_bulk(
        self,
        texts: List[str],
        is_document: bool = True,
        batch_size: int = 64,
        progress_callback: Optional[callable] = None
    ) -> List[np.ndarray]:
        """
        Optimized bulk ingestion for vault indexing.
        Processes large document sets efficiently with progress tracking.
        
        Args:
            texts: List of texts to embed (can be thousands)
            is_document: Use document prefix
            batch_size: Batch size for processing
            progress_callback: Optional callback(batch_num, total_batches, embedded_count)
        
        Returns:
            List of embedding arrays (one per batch for memory efficiency)
        """
        if not self._loaded and not self.load():
            raise RuntimeError("Embedding model offline.")
        
        total_batches = (len(texts) + batch_size - 1) // batch_size
        results = []
        
        logger.info(f"Embedder: Starting bulk ingestion of {len(texts)} texts in {total_batches} batches...")
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]
            
            batch_embeddings = self.encode(
                batch_texts,
                is_document=is_document,
                batch_size=batch_size,
                use_cache=True
            )
            results.append(batch_embeddings)
            
            if progress_callback:
                progress_callback(batch_num + 1, total_batches, end_idx)
            
            # Garbage collection between batches to prevent memory creep
            if batch_num % 10 == 0:
                gc.collect()
        
        logger.info(f"Embedder: Bulk ingestion complete. {len(texts)} texts embedded.")
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get embedding performance statistics."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "dimensionality": self.dimensionality,
            "loaded": self._loaded,
            "total_embeddings": self._total_embeddings,
            "total_time_sec": round(self._total_time_sec, 2),
            "avg_time_per_embedding_ms": round(
                (self._total_time_sec / self._total_embeddings * 1000) if self._total_embeddings > 0 else 0, 2
            ),
            "cache_stats": self._cache.get_stats()
        }
    
    def clear_cache(self):
        """Clear the embedding cache (useful when switching vaults)."""
        self._cache.clear()
        logger.info("Embedder: Cache cleared.")
    
    def unload(self):
        """Violently unload model to free RAM/VRAM."""
        with self._lock:
            if self._model:
                logger.info("Embedder: Unloading from memory...")
                del self._model
                self._model = None
                self._loaded = False
                
                # 🚨 Explicit Garbage Collection
                gc.collect()
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass
                
                self._cache.clear()
                vram_guard.clear_cache()


# Global Singleton
embedder = Embedder()