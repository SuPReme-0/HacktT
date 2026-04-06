"""
HackT Sovereign Core - Hybrid RAG Retriever
============================================
Provides context-aware retrieval combining:
- Vector Search (LanceDB)
- Graph Traversal (KùzuDB)
- Lexical Search (BM25)
"""

import logging
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict

try:
    import lancedb
except ImportError:
    lancedb = None

try:
    import kuzu
except ImportError:
    kuzu = None

from utils.logger import get_logger

logger = get_logger("hackt.core.rag")

class HybridRetriever:
    """
    Knowledge Vault interaction layer. 
    Retrieves context without utilizing GPU VRAM.
    """
    def __init__(self, indices_path: str = "vault"):
        self.indices_path = Path(indices_path)
        self.indices_path.mkdir(parents=True, exist_ok=True)
        
        # 1. Vector DB (LanceDB)
        self.vector_table = None
        if lancedb:
            try:
                self.vector_db = lancedb.connect(str(self.indices_path / "vault.lance"))
                # SAFEGUARD: Prevent crash if table doesn't exist yet on first boot
                if "vault_chunks" in self.vector_db.table_names():
                    self.vector_table = self.vector_db.open_table("vault_chunks")
                else:
                    logger.info("RAG: Vector table 'vault_chunks' not found. Awaiting data ingestion.")
            except Exception as e:
                logger.error(f"RAG: LanceDB init failed: {e}")
        
        # 2. Graph DB (Kùzu)
        self.graph_conn = None
        if kuzu:
            try:
                db_path = str(self.indices_path / "vault.graph")
                self.graph_db = kuzu.Database(db_path)
                self.graph_conn = kuzu.Connection(self.graph_db)
            except Exception as e:
                logger.error(f"RAG: Kùzu init failed: {e}")
        
        # 3. BM25 Index
        self.bm25_data = None
        bm25_path = self.indices_path / "bm25_index.pkl"
        if bm25_path.exists():
            try:
                with open(bm25_path, "rb") as f:
                    self.bm25_data = pickle.load(f)
            except Exception as e:
                logger.warning(f"RAG: BM25 load failed: {e}")
    
    def retrieve(self, query: str, query_vector: np.ndarray, mode: str = "active") -> str:
        """Hybrid retrieval with vector fusion."""
        context_parts = []
        
        # Vector Search
        if self.vector_table is not None:
            try:
                # FIXED: Ensure vector is a flat 1D array for LanceDB, dropping extra dims
                flat_vector = query_vector.flatten()
                vec_results = self.vector_table.search(flat_vector).limit(5).to_pandas()
                
                for _, row in vec_results.iterrows():
                    source = row.get('source', 'unknown')
                    text = row.get('text', '')
                    context_parts.append(f"[Source: {source}]\n{text[:500]}")
            except Exception as e:
                logger.error(f"RAG: Vector search failed: {e}")
        
        # Return merged context
        if context_parts:
            return "\n\n---\n\n".join(context_parts)
        return "No relevant context found in Knowledge Vault."
    
    def fast_scan(self, text: str) -> bool:
        """Quick threat keyword filter (Zero VRAM impact)"""
        if not text:
            return False
            
        threat_keywords = [
            'eval(', 'exec(', 'document.cookie', 'innerHTML', 
            'phishing', 'password=', 'secret_key', 'api_key', 'xss'
        ]
        text_lower = text.lower()
        return any(kw in text_lower for kw in threat_keywords)

# Singleton instance
retriever = HybridRetriever()