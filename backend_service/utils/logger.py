"""
HackT Sovereign Core - Logger Module
====================================
Provides structured, thread-safe logging with:
- Daily rotating file logs in the local project workspace
- Console output for development
- Hierarchical propagation (no duplicate file handlers)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Log format: [timestamp] [level] [module]: message
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Global flag to ensure we only attach handlers to the root once
_logging_initialized = False


def _setup_base_logger():
    """Configures the master 'hackt' logger to prevent I/O contention."""
    global _logging_initialized
    if _logging_initialized:
        return

    # 1. Grab the master base logger for the entire app
    base_logger = logging.getLogger("hackt")
    base_logger.setLevel(logging.DEBUG)  # Let the handlers filter the levels
    base_logger.propagate = False        # Prevent double-logging to root

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # 2. File Handler (Routed to local project workspace to match config.py)
    # This keeps your development environment clean and centralized
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"runtime_{datetime.now().strftime('%Y%m%d')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # Capture everything to file
    base_logger.addHandler(file_handler)

    # 3. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Allow environment override for console verbosity
    env_level = os.environ.get("HACKT_LOG_LEVEL", "INFO").upper()
    console_handler.setLevel(getattr(logging, env_level, logging.INFO))
    base_logger.addHandler(console_handler)

    _logging_initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger attached to the 'hackt' hierarchy.
    
    Args:
        name: Logger name (e.g., 'hackt.core.engine')
        
    Returns:
        Configured logging.Logger instance
    """
    _setup_base_logger()
    return logging.getLogger(name)


# Singleton logger for module-level use
logger = get_logger("hackt.utils.logger")


def log_system_info():
    """Log basic system hardware information at startup."""
    import platform
    
    logger.info("=== HackT Sovereign Core Init ===")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version.split(' ')[0]}")
    
    try:
        import psutil
        logger.info(f"CPU: {psutil.cpu_count(logical=True)} cores")
        logger.info(f"RAM: {psutil.virtual_memory().total / (1024**3):.1f} GB")
    except ImportError:
        logger.debug("psutil not available - skipping RAM/CPU detection")
    
    # GPU info if available
    try:
        import torch
        if torch.cuda.is_available():
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
        else:
            logger.info("GPU: None detected (Running in CPU mode)")
    except ImportError:
        logger.debug("PyTorch not available - skipping GPU detection")
    
    logger.info("=================================")