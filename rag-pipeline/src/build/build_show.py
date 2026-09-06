#!/usr/bin/env python3
"""
build_showcase.py - Compiles BM25 and Graph DBs from partial ingestion data.
Run this when you need to present your current progress without finishing the full queue.
"""

import sys
import subprocess
from pathlib import Path

# 1. Dynamically set project root so imports work perfectly regardless of where you run this
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

# 2. Import the exact BM25 builder from your master script
try:
    from src.build.master import build_bm25_index
except ImportError as e:
    print(f"❌ ERROR: Could not import master.py modules. Check your paths: {e}")
    sys.exit(1)

def main():
    print("=" * 70)
    print("🚀 HACKT KNOWLEDGE VAULT - SHOWCASE BUILDER")
    print("=" * 70)
    print("This will compile your partial dataset so it is ready for querying.")
    print("Your main ingestion progress (processed.log) will NOT be affected.\n")

    # Step 1: Build the LanceDB Native FTS (Tantivy)
    print("⚡ [1/2] Forcing Native Full-Text Search (BM25) Index Build...")
    try:
        build_bm25_index()
        print("  ✅ FTS Index complete.\n")
    except Exception as e:
        print(f"  ❌ FTS Index failed: {e}\n")

    # Step 2: Build the KùzuDB Graph
    print("🕸️  [2/2] Forcing Graph Database Build...")
    graph_script = current_dir / 'graph_bulk_load.py'
    
    if not graph_script.exists():
        print(f"  ❌ Cannot find {graph_script.name} in {current_dir}")
        sys.exit(1)

    try:
        # Using subprocess for safer execution and to catch any terminal errors
        subprocess.run([sys.executable, str(graph_script)], check=True)
        print("  ✅ Graph Database complete.\n")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Graph build failed with exit code {e.returncode}\n")
        sys.exit(1)

    print("=" * 70)
    print("🎉 SHOWCASE BUILD COMPLETE! You are ready to present.")
    print("When you are ready to resume the remaining files, just run ./launch_ingestion.sh")
    print("=" * 70)

if __name__ == "__main__":
    main()