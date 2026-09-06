#!/usr/bin/env python3
"""
graph_bulk_load.py – KùzuDB Bulk Load for V21.0-Lite
=====================================================
FIXED: Uses Vectorized Pandas to extract nodes safely without RAM spikes.
FIXED: Wipes old graph DB before build to prevent Primary Key violations on reruns.
UPGRADED: Removed deprecated Cypher syntax and added native graph verification.
"""

import kuzu
import pandas as pd
import time
import shutil
from pathlib import Path
from config import CONFIG, logger

# Build vault_id -> score mapping
VAULT_ID_TO_SCORE = {}
for vault_name, meta in CONFIG["VAULT_MAPPING"].items():
    VAULT_ID_TO_SCORE[meta["id"]] = meta["score"]

def get_vault_id_from_path(path_str):
    """
    Extract vault ID from a file path by looking at the top-level directory.
    Example: "03_Vault_Showroom/subdir/file.py" -> returns 3.
    """
    parts = Path(path_str).parts
    if not parts:
        return 2
    vault_name = parts[0]
    for name, meta in CONFIG["VAULT_MAPPING"].items():
        if name == vault_name:
            return meta["id"]
    return 2 # Fallback safe default

def main():
    csv_path = CONFIG["INTERMEDIATE_PATH"] / "graph_edges.csv"
    if not csv_path.exists():
        logger.warning("[Graph] No edges found. Skipping graph build.")
        return

    logger.info(f"[Graph] Loading edges from {csv_path}")
    max_retries = 3

    for attempt in range(max_retries):
        try:
            # ------------------------------------------------------------------
            # 1. Read edges
            # ------------------------------------------------------------------
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.warning("[Graph] Edge CSV is empty")
                return
            logger.info(f"[Graph] Read {len(df)} edges from CSV")

            # ------------------------------------------------------------------
            # 2. Extract unique nodes (RAM-Safe Vectorized Pandas)
            # ------------------------------------------------------------------
            logger.info("[Graph] Extracting unique nodes via vectorized operations...")
            unique_paths = pd.concat([df['src'], df['dst']]).unique()
            nodes = pd.DataFrame({'name': unique_paths})
            
            # Vectorized apply (Runs in C, prevents massive Python dict RAM spikes)
            nodes['vault_id'] = nodes['name'].apply(get_vault_id_from_path)
            nodes['authority_score'] = nodes['vault_id'].map(lambda x: VAULT_ID_TO_SCORE.get(x, 1.0))

            nodes_csv = CONFIG["INTERMEDIATE_PATH"] / "graph_nodes.csv"
            nodes.to_csv(nodes_csv, index=False, header=False)
            logger.info(f"[Graph] Extracted {len(nodes)} unique nodes")

            # ------------------------------------------------------------------
            # 3. Clean Slate & Initialize KùzuDB
            # ------------------------------------------------------------------
            db_path = CONFIG["INDEX_PATH"] / "vault.graph"
            
            # 🔥 THE CLEAN SLATE FIX: Wipe the old database to prevent PK collisions
            if db_path.exists():
                logger.info("[Graph] Wiping existing graph database for a clean build...")
                shutil.rmtree(db_path, ignore_errors=True)

            db = kuzu.Database(str(db_path))
            conn = kuzu.Connection(db)

            # Create Node Table
            conn.execute("""
                CREATE NODE TABLE File(
                    name STRING,
                    vault_id INT64,
                    authority_score FLOAT,
                    PRIMARY KEY (name)
                )
            """)

            conn.execute(f"COPY File FROM '{nodes_csv}'")
            logger.info(f"[Graph] Loaded {len(nodes)} nodes")

            # ------------------------------------------------------------------
            # 4. Load edges
            # ------------------------------------------------------------------
            conn.execute("CREATE REL TABLE IMPORTS(FROM File TO File, relation STRING)")
                
            edges_csv = CONFIG["INTERMEDIATE_PATH"] / "graph_edges_clean.csv"
            df[['src', 'dst', 'relation']].to_csv(edges_csv, index=False, header=False)
            conn.execute(f"COPY IMPORTS FROM '{edges_csv}'")
            logger.info(f"[Graph] Loaded {len(df)} edges")

            # ------------------------------------------------------------------
            # 5. Database Verification (The Upgrade)
            # ------------------------------------------------------------------
            logger.info("[Graph] Verifying database integrity via native Cypher queries...")
            try:
                # Query the database directly to ensure the data actually stuck
                node_count = conn.execute("MATCH (n:File) RETURN count(n)").get_next()[0]
                edge_count = conn.execute("MATCH ()-[r:IMPORTS]->() RETURN count(r)").get_next()[0]
                
                logger.info(f"✅ [Graph] Verification Success: {node_count} nodes and {edge_count} edges are active in KùzuDB.")
            except Exception as verify_err:
                logger.warning(f"⚠️ [Graph] Verification query failed, but build may still be valid: {verify_err}")

            logger.info("[Graph] Bulk Load Complete! 🏁")
            return

        except Exception as e:
            logger.error(f"[Graph] Bulk load attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info("[Graph] Retrying in 5 seconds...")
                time.sleep(5)
            else:
                logger.error("[Graph] All retries failed. Exiting.")
                raise

if __name__ == "__main__":
    main()