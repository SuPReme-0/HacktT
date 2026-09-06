#!/usr/bin/env python3
"""
config.py – Central Configuration for V21.0-Lite Ingestion
==========================================================
All hardware limits, paths, and feature flags are defined here.
This ensures consistency across all build components.

CRITICAL SETTINGS FOR 16GB RAM / 8GB VRAM:
- BATCH_SIZE: 100 (model loaded once per batch, not per file)
- EMBEDDING_BATCH_SIZE: 4 (fits 8GB VRAM)
- RAM_LIMIT_GB: 11.0 (leaves 1GB safety margin)
- VRAM_LIMIT_GB: 7.0 (leaves 1GB for display overhead)
- BATCH_TIMEOUT: 7200 (2 hours per batch max)

Hardware Target:
- 16GB System RAM (12GB usable in WSL2)
- 8GB VRAM (RTX 4060/3070)
- 1TB+ NVMe Storage

Build Time: ~145 hours (6 days) for 95GB data
"""

import os
import sys
import logging
import shutil
from pathlib import Path
from datetime import datetime

# ==============================================================================
# HARDWARE CONSTRAINTS (16GB System / 8GB VRAM)
# ==============================================================================
CONFIG = {
    # --------------------------------------------------------------------------
    # File System Paths (WSL2 Native - CRITICAL for performance)
    # --------------------------------------------------------------------------
    "BASE_PATH": Path.home() / "hackt_vault",
    "RAW_PATH": Path.home() / "hackt_vault" / "data" / "raw",
    "INDEX_PATH": Path.home() / "hackt_vault" / "data" / "index",
    "INTERMEDIATE_PATH": Path.home() / "hackt_vault" / "data" / "intermediate",
    "LOGS_PATH": Path.home() / "hackt_vault" / "data" / "logs",
    "CHECKPOINT_PATH": Path.home() / "hackt_vault" / "checkpoints",
    "MODELS_PATH": Path.home() / "hackt_vault" / "models",
    
    # --------------------------------------------------------------------------
    # Worker & Batch Settings (CRITICAL for 16GB RAM stability)
    # --------------------------------------------------------------------------
    "WORKERS": 1,                       # Only one worker process at a time
    "BATCH_SIZE": 100,                  # Files per batch - model loaded ONCE per batch
    "MAX_TASKS_PER_CHILD": 1,           # Worker dies after batch (OS reclaims RAM)
    "BATCH_TIMEOUT": 14400,              # 4 hours per batch - prevents hangs
    "EMBEDDING_BATCH_SIZE": 16,          # GPU batch size (fits 8GB VRAM)
    "RAM_LIMIT_GB": 11.0,               # Hard limit (OS+WSL2 4GB + master + worker)
    "VRAM_LIMIT_GB": 7.9,               # Soft limit (model + batch + context + display)
    "MIN_DISK_SPACE_GB": 50.0,          # Abort if less than this
    "DISK_CHECK_INTERVAL": 10,          # Check disk every N batches
    "DISK_PAUSE_SECONDS": 300,          # 5 minutes pause when low on space
    
    # --------------------------------------------------------------------------
    # Model & Embedding Settings
    # --------------------------------------------------------------------------
    "EMBEDDING_MODEL": "nomic-ai/nomic-embed-text-v1.5",
    "EMBEDDING_DIM": 768,
    "EMBEDDING_TRUNCATE": 256,          # Matryoshka truncation (configured at model load)
    "EMBEDDING_QUANTIZE": "float32",    # or "int8" - must be consistent across builds
    
    # --------------------------------------------------------------------------
    # Chunking Settings
    # --------------------------------------------------------------------------
    "MAX_CHUNK_TOKENS": 2500,           # Token limit per chunk (prevents context overflow)
    "TOKENS_PER_CHAR_ESTIMATE": 4,      # Heuristic: 4 chars ≈ 1 token
    
    # --------------------------------------------------------------------------
    # File Summaries (GPU-accelerated pre-processing)
    # --------------------------------------------------------------------------
    "USE_FILE_SUMMARIES": True,
    "SUMMARIES_FILE": Path.home() / "hackt_vault" / "file_summaries.json",

    # ✅ Use Qwen 3.5 4B with 4-bit quantization
    "SUMMARY_MODEL": "Qwen/Qwen3.5-4B",  # Or local path if downloaded
    "SUMMARY_DEVICE": "cuda",
    "SUMMARY_MAX_LENGTH": 100,      # Default fallback (overridden per file)
    "SUMMARY_MIN_LENGTH": 10,
    "SUMMARY_BATCH_SIZE": 4,        # Start with 8; auto-reduces on OOM
    "SUMMARY_USE_FP16": True,       # Compute in FP16 (required for quantization)
    "SUMMARY_DO_SAMPLE": False,     # Deterministic for consistency
    "SUMMARY_QUANTIZE_4BIT": True,  # Enable 4-bit quantization (new flag)
    # --------------------------------------------------------------------------
    # Vault Metadata (Security tagging for runtime filtering)
    # --------------------------------------------------------------------------
    "VAULT_MAPPING": {
        "01_Vault_Library": {"id": 1, "score": 0.9, "type": "library"},
        "02_Vault_Laboratory": {"id": 2, "score": 0.5, "type": "vulnerable"},
        "03_Vault_Showroom": {"id": 3, "score": 1.0, "type": "secure"}
    },
    
    # --------------------------------------------------------------------------
    # File Extensions (for task classification)
    # --------------------------------------------------------------------------
    "CODE_EXTENSIONS": [".py", ".js", ".java", ".c", ".cpp", ".go", ".rs", ".ts", ".jsx", ".tsx"],
    "PDF_EXTENSIONS": [".pdf"],
    
    # --------------------------------------------------------------------------
    # Schema Versioning (for future compatibility)
    # --------------------------------------------------------------------------
    "INDEX_SCHEMA_VERSION": "v21.0-lite-1",
}

# ==============================================================================
# Logging Setup (File + Console)
# ==============================================================================
def setup_logging():
    """Configure logging with file and console handlers."""
    log_path = CONFIG["LOGS_PATH"] / "build.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==============================================================================
# Directory Creation (Called at module import)
# ==============================================================================
def ensure_directories():
    """Create all required directories if they don't exist."""
    for path in [
        CONFIG["INDEX_PATH"],
        CONFIG["INTERMEDIATE_PATH"],
        CONFIG["LOGS_PATH"],
        CONFIG["CHECKPOINT_PATH"],
        CONFIG["MODELS_PATH"]
    ]:
        path.mkdir(parents=True, exist_ok=True)

ensure_directories()

# ==============================================================================
# Disk Space Checks
# ==============================================================================
def check_disk_space():
    """
    Verify at least MIN_DISK_SPACE_GB is free.
    Exits with error if insufficient space.
    """
    total, used, free = shutil.disk_usage(str(CONFIG["BASE_PATH"]))
    free_gb = free / (1024 ** 3)
    
    if free_gb < CONFIG["MIN_DISK_SPACE_GB"]:
        logger.error(f"Insufficient disk space: {free_gb:.1f}GB free, need {CONFIG['MIN_DISK_SPACE_GB']}GB")
        sys.exit(1)
    
    logger.info(f"Disk space OK: {free_gb:.1f}GB free")
    return free_gb

def disk_space_warning():
    """
    Check if disk space is below threshold.
    Returns True if space is low, False otherwise.
    """
    total, used, free = shutil.disk_usage(str(CONFIG["BASE_PATH"]))
    free_gb = free / (1024 ** 3)
    return free_gb < CONFIG["MIN_DISK_SPACE_GB"]

# ==============================================================================
# Build Metadata (For audit trail)
# ==============================================================================
def get_build_metadata():
    """Return metadata about this build for logging and debugging."""
    return {
        "version": CONFIG["INDEX_SCHEMA_VERSION"],
        "start_time": datetime.now().isoformat(),
        "batch_size": CONFIG["BATCH_SIZE"],
        "embedding_model": CONFIG["EMBEDDING_MODEL"],
        "embedding_dim": CONFIG["EMBEDDING_TRUNCATE"],
        "quantize": CONFIG["EMBEDDING_QUANTIZE"],
        "ram_limit_gb": CONFIG["RAM_LIMIT_GB"],
        "vram_limit_gb": CONFIG["VRAM_LIMIT_GB"],
    }
