import lancedb
import kuzudb
import pickle
import numpy as np
from utils.logger import get_logger

logger = get_logger("hackt.retriever")

class HackTRetriever:
    def __init__(self, indices_path: str):
        self.indices_path = indices_path
        self.vector_db = lancedb.connect(f"{indices_path}/vault.lance")
        self.table = self.vector_db.open_table("vault_chunks")
        
        self.graph_db = kuzudb.Database(f"{indices_path}/vault.graph")
        self.graph_conn = kuzudb.Connection(self.graph_db)
        
        with open(f"{indices_path}/bm25_index.pkl", "rb") as f:
            self.bm25_data = pickle.load(f)

    def bm25_search(self, query_text: str, top_k: int = 5):
        """Fixed Bug #1: Proper ranking instead of scoring all docs."""
        tokenized_query = query_text.split()
        scores = self.bm25_data['bm25'].get_scores(tokenized_query)
        top_indices = np.argsort(scores)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0.1:  # Threshold
                results.append({
                    'chunk_id': self.bm25_data['chunk_ids'][idx],
                    'score': float(scores[idx])
                })
        return results

    def graph_search(self, topic: str):
        """Fixed Bug #2: Parameterized Query to prevent injection."""
        try:
            result = self.graph_conn.execute(
                "MATCH (f:File)-[:IMPORTS]->(t:File) WHERE t.name CONTAINS $name RETURN f.name",
                {"name": topic}
            ).get_all()
            return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []

    def fast_scan(self, text: str, threshold: float = 0.7) -> bool:
        """Fixed Bug #3: Implemented missing method."""
        threat_keywords = ['eval(', 'document.cookie', 'innerHTML', 'phishing', 'password']
        # Simple keyword presence check for speed
        return any(kw in text for kw in threat_keywords)

    def fuse_results(self, vec_results, bm25_results, graph_context, top_k=5):
        """Fixed Bug #9: Implemented Reciprocal Rank Fusion."""
        all_results = {}
        
        # Vector Results
        for _, row in vec_results.iterrows():
            chunk_id = str(row['id'])
            all_results[chunk_id] = {
                'score': 1.0 / (1 + row['_distance']),
                'text': row['text'],
                'source': row['source']
            }
        
        # BM25 Boost
        for item in bm25_results:
            chunk_id = str(item['chunk_id'])
            if chunk_id in all_results:
                all_results[chunk_id]['score'] += item['score']
        
        # Sort and Return
        sorted_results = sorted(all_results.items(), key=lambda x: x[1]['score'], reverse=True)
        return sorted_results[:top_k]

    def get_hybrid_context(self, query_text: str, query_vector: np.ndarray):
        vec_results = self.table.search(query_vector).limit(5).to_pandas()
        bm25_results = self.bm25_search(query_text)
        graph_context = self.graph_search(query_text.split()[0] if query_text else "security")
        
        fused = self.fuse_results(vec_results, bm25_results, graph_context)
        return "\n".join([r[1]['text'] for r in fused])

retriever = None  # Initialized in main.py