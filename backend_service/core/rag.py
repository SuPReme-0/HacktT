"""
HackT Sovereign Core - Adaptive Hybrid Retriever (v4.3)
=======================================================
Production-sealed RAG implementation featuring:
- Native LanceDB Hybrid Search (Tantivy FTS + Vector in Rust)
- Strict Vault-Aware Routing
- Dynamic Anti-Hallucination Shield
- Batch Graph Authority Boosting
- Fixed: LanceDB Hybrid API Syntax & Python Variable Scoping
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Any

from utils.logger import get_logger
from utils.config import config

try:
    import lancedb
except ImportError:
    lancedb = None

try:
    import kuzu
except ImportError:
    kuzu = None

logger = get_logger("hackt.core.rag")

class HybridRetriever:
    """
    Knowledge Vault interaction layer.
    Engineered for zero-hallucination, ultra-low latency context retrieval.
    """
    
    def __init__(self):
        self.index_dir = config.paths.models_dir / "index"
        
        # Database Connections
        self.vector_table = None
        self.graph_conn = None
        self._db = None 
        
        self.semantic_threshold = config.rag.semantic_threshold
        self.max_context_chars = config.rag.max_context_chars
        
        self.vault_map = {
            "library": config.vaults.library_id,      # 1
            "laboratory": config.vaults.laboratory_id,  # 2
            "showroom": config.vaults.showroom_id     # 3
        }
        
        self._initialize_databases()
    
    def _initialize_databases(self):
        """Safely boots local embedded databases with concurrency safety."""
        # 1. LanceDB 
        if lancedb:
            try:
                lance_path = str(self.index_dir)
                self._db = lancedb.connect(lance_path)
                        
                if "vault_chunks" in self._db.table_names():
                    self.vector_table = self._db.open_table("vault_chunks")
                    logger.info("RAG: LanceDB Vector & Tantivy FTS Engines ONLINE.")
                else:
                    logger.warning("RAG: LanceDB table 'vault_chunks' missing. Awaiting data ingestion.")
            except Exception as e:
                logger.error(f"RAG: LanceDB connection failed: {e}")
        
        # 2. KùzuDB 
        if kuzu:
            try:
                graph_path = str(self.index_dir / "vault.graph")
                if Path(graph_path).exists():
                    db = kuzu.Database(graph_path, read_only=True)
                    self.graph_conn = kuzu.Connection(db)
                    logger.info("RAG: KùzuDB Graph Engine ONLINE (Read-Only).")
            except Exception as e:
                logger.error(f"RAG: KùzuDB connection failed: {e}")
    
    def retrieve(
        self,
        query: str,
        query_vector: np.ndarray,
        mode: str = "active",
        query_type: str = "chat",
        target_vault: Optional[str] = None,
        limit: int = 15
    ) -> List[Dict]:
        
        if not self.vector_table:
            logger.error("RAG: Vector table offline. Cannot retrieve.")
            return []
        
        # ==================================================================
        # 1. VAULT FILTERING
        # ==================================================================
        prefilter = None
        if target_vault and target_vault.lower() in self.vault_map:
            v_id = self.vault_map[target_vault.lower()]
            prefilter = f"vault_id = {v_id}"
            logger.debug(f"RAG: Routing query strictly to Vault {v_id} ({target_vault})")
        
        # ==================================================================
        # 2. VOICE BYPASS CIRCUIT (Pure Vector)
        # ==================================================================
        if query_type == "voice":
            search_obj = self.vector_table.search(query_vector.flatten()).limit(3)
            if prefilter:
                search_obj = search_obj.where(prefilter)
            
            results = search_obj.to_pandas().to_dict('records')
            return self._pack_context(results)
        
        # ==================================================================
        # 3. NATIVE HYBRID RRF SEARCH 
        # ==================================================================
        # 🛡️ CRITICAL FIX 1: Initialize variable BEFORE the try block to prevent Scope Errors
        raw_results = [] 
        
        try:
            # 🛡️ CRITICAL FIX 2: Modern LanceDB API strict syntax for Hybrid Search
            search_obj = self.vector_table.search(query_type="hybrid") \
                                          .vector(query_vector.flatten()) \
                                          .text(query)
            
            if prefilter:
                search_obj = search_obj.where(prefilter)
            
            search_obj = search_obj.limit(limit)
            raw_results = search_obj.to_pandas().to_dict('records')
            logger.debug(f"RAG: Hybrid search returned {len(raw_results)} results")
            
        except Exception as e:
            logger.error(f"RAG: Native hybrid search failed: {e}")
            logger.info("RAG: Falling back to Vector-only search.")
            
            # 🛡️ CRITICAL FIX 3: Actually execute the fallback if Tantivy fails
            try:
                search_obj = self.vector_table.search(query_vector.flatten())
                if prefilter:
                    search_obj = search_obj.where(prefilter)
                
                search_obj = search_obj.limit(limit)
                raw_results = search_obj.to_pandas().to_dict('records')
            except Exception as fallback_e:
                logger.error(f"RAG: Fallback vector search also failed: {fallback_e}")
                raw_results = [] # Failsafe
        
        # ==================================================================
        # 4. GRAPH BOOST
        # ==================================================================
        if mode == "passive" and self.graph_conn and raw_results:
            raw_results = self._graph_boost_authority(raw_results)
        
        # ==================================================================
        # 5. ANTI-HALLUCINATION & TOKEN PACKING
        # ==================================================================
        return self._pack_context(raw_results)
    
    def _graph_boost_authority(self, chunks: List[Dict]) -> List[Dict]:
        if not self.graph_conn or not chunks:
            return chunks
        
        try:
            source_files = list({chunk.get("source") for chunk in chunks if chunk.get("source")})
            if not source_files:
                return chunks

            safe_files = [str(f).replace("'", "''").replace('"', '""') for f in source_files]

            query = """
            MATCH (f:File)
            WHERE f.name IN $filenames
            RETURN f.name, f.authority_score
            """
            result = self.graph_conn.execute(query, {"filenames": safe_files})
            
            auth_map = {}
            while result.has_next():
                row = result.get_next()
                auth_map[row[0]] = float(row[1])

            for chunk in chunks:
                source_file = chunk.get("source", "")
                auth_score = auth_map.get(source_file, 0.0)
                chunk["graph_score"] = auth_score
                
                max_boost = 0.2
                boost = min(auth_score * 0.1, max_boost) if auth_score else 0.0
                
                if "_distance" in chunk:
                    chunk["boosted_score"] = chunk["_distance"] - boost
                elif "_score" in chunk:
                    chunk["boosted_score"] = chunk["_score"] + boost
                else:
                    chunk["boosted_score"] = chunk.get("_score", 0.0) + boost
            
            if any("_distance" in c for c in chunks if "boosted_score" in c):
                return sorted(chunks, key=lambda x: x.get("boosted_score", float('inf')))
            else:
                return sorted(chunks, key=lambda x: x.get("boosted_score", 0.0), reverse=True)
            
        except Exception as e:
            logger.debug(f"RAG: Graph batch boost skipped (non-fatal): {e}")
            return chunks
    
    def _pack_context(self, raw_results: List[Dict]) -> List[Dict]:
        packed_results = []
        current_chars = 0
        
        for doc in raw_results:
            if "_distance" in doc:
                if doc["_distance"] > self.semantic_threshold:
                    continue
            elif "_score" in doc:
                if doc["_score"] < 0.1:
                    continue
            
            text_len = len(doc.get("text", ""))
            if current_chars + text_len > self.max_context_chars:
                break 
            
            packed_results.append(doc)
            current_chars += text_len
        
        if not packed_results:
            logger.info("RAG: No context met threshold requirements. LLM flying blind.")
        
        return packed_results
    
    def get_vault_stats(self) -> Dict[str, int]:
        if not self.vector_table:
            return {}
        
        stats = {}
        try:
            for vault_name, vault_id in self.vault_map.items():
                if hasattr(self.vector_table, 'count_rows'):
                    count = self.vector_table.count_rows(f"vault_id = {vault_id}")
                else:
                    df = self.vector_table.search([0.0]*256).where(f"vault_id = {vault_id}").limit(1000).to_pandas()
                    count = len(df)
                stats[vault_name] = count
        except Exception as e:
            logger.warning(f"RAG: Failed to get vault stats: {e}")
            for vault_name in self.vault_map:
                stats[vault_name] = 0
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        return {
            "vector_table": self.vector_table is not None,
            "graph_conn": self.graph_conn is not None,
            "semantic_threshold": self.semantic_threshold,
            "max_context_chars": self.max_context_chars,
            "vault_map": self.vault_map
        }

# Singleton Instance
retriever = HybridRetriever()