#!/usr/bin/env python3
"""
master.py – Orchestrator for V21.0-Lite Ingestion with Session Limit
=====================================================================
FIXES:
  - Added Strict Whitelist (ignores .git, node_modules, etc.)
  - Fixed "Perfectionist Trap" so Graph builds even if a few files fail
  - Drops BUILD_COMPLETE marker for the run_build.py orchestrator
  - FIXED: Replaced RAM-crashing rank_bm25 with LanceDB Native FTS (Tantivy)
"""

import os
import sys
import json
import multiprocessing
multiprocessing.set_start_method('spawn', force=True)
import signal
import shutil
import time
from pathlib import Path
from config import CONFIG, logger, check_disk_space, disk_space_warning, get_build_metadata
from worker import process_batch

# ==============================================================================
# CONFIGURATION
# ==============================================================================
MAX_SESSION_HOURS = 100
MAX_SESSION_SECONDS = int(MAX_SESSION_HOURS * 3600)

PROCESSED_LOG = CONFIG["CHECKPOINT_PATH"] / "processed.log"
FILE_CACHE_PATH = CONFIG["INTERMEDIATE_PATH"] / "file_cache.json"
BUILD_COMPLETE_MARKER = CONFIG["BASE_PATH"] / "BUILD_COMPLETE"

# Strict Whitelist for junk directories
IGNORE_DIRS = {'node_modules', 'venv', 'env', '__pycache__', '.venv', 'dist', 'build', '.idea', '.vscode', 'target', 'out'}

shutdown_flag = False

def signal_handler(sig, frame):
    global shutdown_flag
    logger.warning(f"Shutdown signal received (signal {sig}). Finishing current batch...")
    shutdown_flag = True

def load_processed_files():
    if not PROCESSED_LOG.exists():
        return set()
    with PROCESSED_LOG.open('r') as f:
        return {line.strip() for line in f if line.strip()}

def get_tasks():
    processed = load_processed_files()
    tasks = []
    for vault_name, meta in CONFIG["VAULT_MAPPING"].items():
        vault_path = CONFIG["RAW_PATH"] / vault_name
        if not vault_path.exists():
            logger.warning(f"Vault not found: {vault_path}")
            continue
            
        for root, dirs, files in os.walk(vault_path):
            # Apply strict whitelist to ignore junk folders
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in IGNORE_DIRS]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                f_path = os.path.join(root, file)
                if f_path in processed:
                    continue
                    
                if file.endswith(tuple(CONFIG["PDF_EXTENSIONS"])):
                    tasks.append({
                        'type': 'PDF',
                        'path': f_path,
                        'vault_id': meta["id"],
                        'vault_name': vault_name,
                    })
                elif file.endswith(tuple(CONFIG["CODE_EXTENSIONS"])):
                    tasks.append({
                        'type': 'CODE',
                        'path': f_path,
                        'vault_id': meta["id"],
                        'vault_name': vault_name,
                    })
    tasks.sort(key=lambda t: t['path'])
    return tasks

def build_file_cache():
    if FILE_CACHE_PATH.exists():
        logger.info("File cache already exists – skipping rebuild")
        os.environ["FILE_CACHE_PATH"] = str(FILE_CACHE_PATH)
        return
        
    file_cache = set()
    for vault_name in CONFIG["VAULT_MAPPING"].keys():
        vault_path = CONFIG["RAW_PATH"] / vault_name
        if vault_path.exists():
            for root, dirs, files in os.walk(vault_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in IGNORE_DIRS]
                for file in files:
                    if file.startswith('.'): continue
                    if file.endswith(tuple(CONFIG["CODE_EXTENSIONS"])):
                        file_cache.add(file)
                        rel_path = str(Path(root).relative_to(CONFIG["RAW_PATH"]) / file)
                        file_cache.add(rel_path)
                        
    FILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FILE_CACHE_PATH.open('w') as f:
        json.dump(list(file_cache), f)
    os.environ["FILE_CACHE_PATH"] = str(FILE_CACHE_PATH)
    logger.info(f"[Master] Built file cache with {len(file_cache)} entries -> {FILE_CACHE_PATH}")

def build_bm25_index():
    try:
        import lancedb
        logger.info("[BM25] Building native Full-Text Search index via LanceDB (Tantivy)...")
        db = lancedb.connect(str(CONFIG["INDEX_PATH"]))
        
        if "vault_chunks" not in db.table_names():
            logger.warning("[BM25] 'vault_chunks' table does not exist. Skipping.")
            return
            
        table = db.open_table("vault_chunks")
        
        # 🔥 The RAM-Safe Native FTS (Runs on disk, uses Tantivy backend)
        table.create_fts_index("raw_text", replace=True)
        logger.info("[BM25] Native FTS Index built successfully on disk!")
        
    except Exception as e:
        logger.error(f"[BM25] Failed to build FTS index: {e}")

def cleanup_orphan_locks():
    for lock in CONFIG["INTERMEDIATE_PATH"].glob("*.lock"):
        try:
            lock.unlink()
            logger.info(f"Cleaned orphan lock: {lock}")
        except Exception as e:
            logger.warning(f"Failed to clean lock {lock}: {e}")

def main():
    global shutdown_flag
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 70)
    logger.info("HACKT KNOWLEDGE VAULT V21.0-LITE - BUILD STARTING")
    logger.info(f"Session Limit: {MAX_SESSION_HOURS} hours (auto-resume enabled)")
    logger.info("=" * 70)

    metadata = get_build_metadata()
    logger.info(f"Build Version: {metadata['version']}")
    logger.info(f"Batch Size: {CONFIG['BATCH_SIZE']} files")
    logger.info(f"RAM Limit: {CONFIG['RAM_LIMIT_GB']}GB")
    logger.info(f"VRAM Limit: {CONFIG['VRAM_LIMIT_GB']}GB")

    check_disk_space()
    build_file_cache()
    cleanup_orphan_locks()

    tasks = get_tasks()
    logger.info(f"Found {len(tasks)} files to process (excluding already completed)")

    if not tasks:
        logger.info("No tasks to process. Triggering Graph & BM25 build...")
        build_bm25_index()
        logger.info("Starting Graph Bulk Load...")
        os.system(f"{sys.executable} {Path(__file__).parent / 'graph_bulk_load.py'}")
        
        # Drop the marker for run_build.py
        with open(BUILD_COMPLETE_MARKER, 'w') as f:
            f.write("DONE")
            
        logger.info("🎉 HACKT KNOWLEDGE VAULT V21.0-LITE - BUILD FINISHED")
        return

    batch_size = CONFIG["BATCH_SIZE"]
    batches = [tasks[i:i+batch_size] for i in range(0, len(tasks), batch_size)]
    logger.info(f"Created {len(batches)} batches of size {batch_size}")

    processed = 0
    errors = 0
    error_log = CONFIG["LOGS_PATH"] / "errors.csv"
    start_time = time.time()
    session_start = time.time()
    pool = None
    error_log.parent.mkdir(parents=True, exist_ok=True)
    
    session_reached = False

    try:
        for batch_idx, batch in enumerate(batches):
            if time.time() - session_start >= MAX_SESSION_SECONDS:
                logger.info(f"⏱️  Session limit reached ({MAX_SESSION_HOURS}h). Exiting gracefully.")
                session_reached = True
                break

            if shutdown_flag:
                logger.warning("Shutdown requested. Stopping gracefully...")
                break

            if disk_space_warning():
                logger.warning(f"Low disk space. Pausing for {CONFIG['DISK_PAUSE_SECONDS']} seconds...")
                time.sleep(CONFIG["DISK_PAUSE_SECONDS"])
                if disk_space_warning():
                    logger.error("Still low on space. Aborting.")
                    sys.exit(1)

            logger.info(f"Processing batch {batch_idx+1}/{len(batches)} ({len(batch)} files)")

            pool = multiprocessing.Pool(processes=CONFIG["WORKERS"])
            result_async = pool.apply_async(process_batch, (batch,))

            try:
                batch_results = result_async.get(timeout=CONFIG["BATCH_TIMEOUT"])
            except multiprocessing.TimeoutError:
                logger.error(f"Batch {batch_idx+1} timed out after {CONFIG['BATCH_TIMEOUT']}s.")
                pool.terminate()
                pool.join()
                for task in batch:
                    with open(error_log, 'a') as f:
                        f.write(f"{task['path']},batch_timeout\n")
                pool = None
                errors += len(batch)
                continue
            except Exception as e:
                logger.error(f"Batch {batch_idx+1} failed: {e}")
                pool.terminate()
                pool.join()
                for task in batch:
                    with open(error_log, 'a') as f:
                        f.write(f"{task['path']},worker_crash\n")
                pool = None
                errors += len(batch)
                continue

            for result in batch_results:
                if time.time() - session_start >= MAX_SESSION_SECONDS:
                    logger.info(f"⏱️  Session limit reached mid-batch. Exiting gracefully.")
                    session_reached = True
                    break

                if result['status'] == 'success':
                    processed += 1
                    with PROCESSED_LOG.open('a') as f:
                        f.write(result['file'] + '\n')
                        f.flush()
                else:
                    errors += 1
                    with open(error_log, 'a') as f:
                        f.write(f"{result['file']},{result.get('error','unknown')}\n")

            if pool:
                pool.close()
                pool.join()
                pool = None

            if session_reached:
                break

            elapsed = time.time() - start_time
            rate = processed / elapsed if processed > 0 else 0
            remaining = (len(tasks) - (processed + errors)) / rate if rate > 0 else 0
            logger.info(
                f"Completed {batch_idx+1}/{len(batches)} batches, "
                f"success: {processed}, errors: {errors}. "
                f"Session: {(time.time()-session_start)/3600:.1f}h/{MAX_SESSION_HOURS}h. "
                f"ETA: {remaining/3600:.1f} hours"
            )

    finally:
        if pool:
            pool.close()
            pool.join()

    # ========================================================================
    # BUILD BM25 + GRAPH IF WE FINISHED THE QUEUE (No Session Timeout/Shutdown)
    # ========================================================================
    if not session_reached and not shutdown_flag:
        logger.info("=" * 70)
        logger.info(f"✅ ALL INGESTION COMPLETE. Success: {processed}, Errors: {errors}")
        logger.info(f"Total time: {(time.time() - start_time)/3600:.1f} hours")
        logger.info("=" * 70)

        build_bm25_index()
        logger.info("Starting Graph Bulk Load...")
        os.system(f"{sys.executable} {Path(__file__).parent / 'graph_bulk_load.py'}")

        # Drop the marker for run_build.py
        with open(BUILD_COMPLETE_MARKER, 'w') as f:
            f.write("DONE")

        logger.info("=" * 70)
        logger.info("🎉 HACKT KNOWLEDGE VAULT V21.0-LITE - BUILD FINISHED")
        logger.info("=" * 70)
    else:
        logger.info("=" * 70)
        logger.info(f"⏸️  SESSION PAUSED. Success: {processed}, Errors: {errors}")
        logger.info(f"   Session time: {(time.time()-session_start)/3600:.1f}h")
        logger.info(f"   To continue: python src/build/master.py (or run_build.py)")
        logger.info("=" * 70)

if __name__ == "__main__":
    main()