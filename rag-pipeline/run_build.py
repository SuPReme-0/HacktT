#!/usr/bin/env python3
"""
run_build.py – Unified Build Orchestrator for V21.0-Lite
=========================================================
- Runs summarization (first pass), then a verification pass, then ingestion master.
- Features Auto-Retry: If a script crashes (OOM, timeout), it waits and tries again.
- All output is printed to console; logs are also written to the usual log file.
"""

import os
import sys
import signal
import subprocess
import time
from pathlib import Path

# Add project root to path so we can import config
sys.path.insert(0, str(Path(__file__).parent))
from src.build.config import CONFIG, logger, check_disk_space

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
SUMMARIES_FILE = CONFIG["SUMMARIES_FILE"]
MASTER_SCRIPT = Path(__file__).parent / "src" / "build" / "master.py"
GENERATE_SCRIPT = Path(__file__).parent / "generate_summaries.py"
BUILD_COMPLETE_MARKER = CONFIG["BASE_PATH"] / "BUILD_COMPLETE"

shutdown_flag = False
interrupted = False

def signal_handler(sig, frame):
    global shutdown_flag, interrupted
    logger.warning(f"\n🛑 User interrupt received (signal {sig}). Stopping safely...")
    shutdown_flag = True
    interrupted = True

def run_subprocess(cmd, desc):
    """Run a subprocess, print output in real time, return its exit code."""
    global shutdown_flag, interrupted
    logger.info(f"▶️ Starting: {desc}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

    for line in proc.stdout:
        print(line, end='', flush=True)
        if shutdown_flag:
            logger.warning("Shutdown requested, terminating subprocess...")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            break

    proc.wait()
    return proc.returncode

def execute_with_retries(cmd, desc, max_retries=5):
    """
    Simulates a human user: if a script crashes, it waits for VRAM to clear
    and runs it again so it can pick up from its checkpoint.
    """
    global interrupted
    
    for attempt in range(1, max_retries + 1):
        if interrupted:
            return 130 # Abort code
            
        ret_code = run_subprocess(cmd, desc)
        
        # Success!
        if ret_code == 0:
            logger.info(f"✅ {desc} completed successfully.")
            return 0
            
        # User manually stopped it
        if interrupted or shutdown_flag:
            logger.info(f"⏸️ {desc} aborted by user.")
            return 130
            
        # Subprocess crashed
        logger.warning(f"⚠️ {desc} crashed with exit code {ret_code}.")
        if attempt < max_retries:
            logger.info(f"🔄 Attempt {attempt}/{max_retries} failed. Waiting 10 seconds for VRAM to clear before retrying...")
            time.sleep(10)
        else:
            logger.error(f"❌ {desc} completely failed after {max_retries} attempts.")
            return ret_code

def main():
    global shutdown_flag, interrupted
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 70)
    print("🔨 HACKT KNOWLEDGE VAULT V21.0-LITE – UNKILLED BUILD ORCHESTRATOR")
    print("=" * 70)

    # Check disk space
    check_disk_space()

    # Phase 1: Summarization (first run – processes all files)
    logger.info("Running summarization (first pass)...")
    ret1 = execute_with_retries([sys.executable, str(GENERATE_SCRIPT)], "Summarization (first pass)", max_retries=5)
    
    if interrupted or ret1 != 0:
        print("\n⚠️ Build stopped during Phase 1. Exiting.")
        sys.exit(ret1)

    # Phase 2: Summarization verification (second run – sweeps up leftovers)
    logger.info("Running summarization (verification pass)...")
    ret2 = execute_with_retries([sys.executable, str(GENERATE_SCRIPT)], "Summarization (verification)", max_retries=3)

    if interrupted or ret2 != 0:
        print("\n⚠️ Build stopped during Phase 2. Exiting.")
        sys.exit(ret2)

    # Phase 3: Ingestion master
    logger.info("Starting ingestion master...")
    ret3 = execute_with_retries([sys.executable, str(MASTER_SCRIPT)], "Ingestion Master", max_retries=5)

    if interrupted or ret3 != 0:
        print("\n⚠️ Build stopped during Phase 3. Exiting.")
        sys.exit(ret3)

    # After master exits cleanly, check marker
    if BUILD_COMPLETE_MARKER.exists():
        logger.info("✅ Build completion marker found. All files processed and indexes built.")
    else:
        logger.info("⏸️ Build incomplete (session limit reached). Run script again to resume.")

    print("\n" + "=" * 70)
    print("🏁 BUILD PROCESS FINISHED – You can now safely close the terminal.")
    print("=" * 70)

if __name__ == "__main__":
    main()