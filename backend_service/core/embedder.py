from sentence_transformers import SentenceTransformer
import numpy as np

class Embedder:
    def __init__(self, model_name: str = "nomic-ai/nomic-embed-text-v1.5"):
        # Use ONNX runtime for GPU acceleration with lower overhead
        self.model = SentenceTransformer(
            model_name, 
            trust_remote_code=True,
            model_kwargs={"device": "cuda"}
        )
        # Quantize embeddings to INT8 for storage/retrieval efficiency
        self.model.max_seq_length = 512

    def encode(self, text: str) -> np.ndarray:
        embedding = self.model.encode(text, convert_to_numpy=True)
        # Normalize for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

embedder = Embedder()