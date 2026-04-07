"""
HackT Sovereign Core - Logger Module (v3.0)
===========================================
Provides structured, thread-safe logging with:
- Circular-dependency safe path resolution (PyInstaller compatible)
- VRAM-safe auto-rotating file handlers (prevents infinite disk bloat)
- Sensitive data redaction (API keys, tokens, passwords)
- JSON structured logging option for telemetry parsing
- Color-coded console output for development debugging
- Async-safe logging wrappers
"""

import logging
import json
import os
import sys
import re
import traceback
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict

# ==============================================================================
# Configuration Constants
# ==============================================================================

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
JSON_LOG_FORMAT = "{\"timestamp\":\"%(asctime)s\",\"level\":\"%(levelname)s\",\"module\":\"%(name)s\",\"message\":\"%(message)s\"}"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Sensitive data patterns to redact from logs (Security Critical)
SENSITIVE_PATTERNS = [
    (re.compile(r'(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', re.IGNORECASE), r'\1=***REDACTED***'),
    (re.compile(r'(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{4,})["\']?', re.IGNORECASE), r'\1=***REDACTED***'),
    (re.compile(r'(secret|token|bearer)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?', re.IGNORECASE), r'\1=***REDACTED***'),
    (re.compile(r'(sk_live_|sk_test_|pk_live_|pk_test_)[a-zA-Z0-9]{20,}', re.IGNORECASE), r'***STRIPE_KEY_REDACTED***'),
    (re.compile(r'AWS[A-Z0-9]{16,}', re.IGNORECASE), r'***AWS_KEY_REDACTED***'),
]

# Console color codes for development
COLOR_CODES = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m"
}

# Global flag to ensure we only attach handlers once
_logging_initialized = False

# ==============================================================================
# Custom Formatters
# ==============================================================================

class ColoredConsoleFormatter(logging.Formatter):
    """Adds color codes to console output for easier debugging."""
    
    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        if levelname in COLOR_CODES:
            record.levelname = f"{COLOR_CODES[levelname]}{levelname}{COLOR_CODES['RESET']}"
        return super().format(record)


class RedactingFormatter(logging.Formatter):
    """Automatically redacts sensitive data from log messages before writing."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Redact the message
        record.msg = self._redact(str(record.msg))
        
        # Redact exception info if present
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            record.exc_text = self._redact(exc_text)
            
        return super().format(record)
    
    def _redact(self, text: str) -> str:
        """Apply all sensitive data patterns to the text."""
        for pattern, replacement in SENSITIVE_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


class JSONFormatter(logging.Formatter):
    """Outputs logs as JSON for easy telemetry parsing."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.name,
            "message": self._redact(record.getMessage()),
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra context if provided
        if hasattr(record, 'extra_context'):
            log_data["context"] = record.extra_context
            
        return json.dumps(log_data)
    
    def _redact(self, text: str) -> str:
        for pattern, replacement in SENSITIVE_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

# ==============================================================================
# Path Resolution (PyInstaller Safe)
# ==============================================================================

def _get_safe_log_dir() -> Path:
    """
    Isolates path resolution to prevent circular dependencies with config.py.
    Safely resolves the PyInstaller execution path to prevent writing logs to Temp.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled .exe
        base_dir = Path(sys.executable).parent
    else:
        # Running as python script
        base_dir = Path(__file__).resolve().parent.parent
        
    log_dir = base_dir / "logs"
    
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fallback to user's temp directory if we can't write to app dir
        import tempfile
        log_dir = Path(tempfile.gettempdir()) / "hackt_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
    return log_dir

# ==============================================================================
# Base Logger Setup
# ==============================================================================

def _setup_base_logger():
    """Configures the master 'hackt' logger with size-capped rotating files."""
    global _logging_initialized
    if _logging_initialized:
        return

    # 1. Grab the master base logger for the entire app
    base_logger = logging.getLogger("hackt")
    base_logger.setLevel(logging.DEBUG)  # Let handlers filter levels
    base_logger.propagate = False        # Prevent double-logging to root

    # 2. Rotating File Handler (Human-readable)
    log_file = _get_safe_log_dir() / "hackt_runtime.log"
    
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB max per file (increased for production)
        backupCount=5,              # Keep 5 backups
        encoding="utf-8",
        delay=True                  # Don't create file until first log write
    )
    file_handler.setFormatter(RedactingFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    file_handler.setLevel(logging.DEBUG)
    base_logger.addHandler(file_handler)

    # 3. JSON Log File (For telemetry/analysis)
    json_log_file = _get_safe_log_dir() / "hackt_events.json"
    
    json_handler = RotatingFileHandler(
        filename=json_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
        delay=True
    )
    json_handler.setFormatter(JSONFormatter())
    json_handler.setLevel(logging.INFO)  # Only INFO and above for JSON
    base_logger.addHandler(json_handler)

    # 4. Console Handler (Color-coded for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredConsoleFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    
    # Allow environment override for console verbosity
    env_level = os.environ.get("HACKT_LOG_LEVEL", "INFO").upper()
    console_handler.setLevel(getattr(logging, env_level, logging.INFO))
    base_logger.addHandler(console_handler)

    # 5. Error-Only Handler (Separate file for quick debugging)
    error_file = _get_safe_log_dir() / "hackt_errors.log"
    
    error_handler = RotatingFileHandler(
        filename=error_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
        delay=True
    )
    error_handler.setFormatter(RedactingFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))
    error_handler.setLevel(logging.ERROR)
    base_logger.addHandler(error_handler)

    _logging_initialized = True

# ==============================================================================
# Public API
# ==============================================================================

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


def log_with_context(logger: logging.Logger, level: int, message: str, context: Optional[Dict[str, Any]] = None, **kwargs):
    """
    Logs a message with additional structured context.
    
    Args:
        logger: The logger instance
        level: Logging level (e.g., logging.INFO)
        message: The log message
        context: Optional dict of extra context to include
        **kwargs: Additional keyword arguments
    """
    record = logger.makeRecord(
        logger.name, level, "", 0, message, (), None,
        extra={'extra_context': context} if context else None
    )
    logger.handle(record)


# Async-safe logging wrapper (prevents event loop blocking)
async def async_log(logger: logging.Logger, level: int, message: str, **kwargs):
    """
    Non-blocking logging for async contexts.
    Offloads I/O to a thread to prevent event loop freezes.
    """
    import asyncio
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: logger.log(level, message, **kwargs)
    )


# Singleton logger for module-level use
logger = get_logger("hackt.utils.logger")

# ==============================================================================
# System Info Logging
# ==============================================================================

def log_system_info():
    """Log basic system hardware information at startup for remote telemetry."""
    import platform
    
    logger.info("=== HackT Sovereign Core Boot Sequence ===")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Python: {sys.version.split(' ')[0]}")
    logger.info(f"Frozen/Compiled: {getattr(sys, 'frozen', False)}")
    logger.info(f"Log Directory: {_get_safe_log_dir()}")
    
    try:
        import psutil
        logger.info(f"CPU: {psutil.cpu_count(logical=True)} cores")
        logger.info(f"System RAM: {psutil.virtual_memory().total / (1024**3):.1f} GB")
    except ImportError:
        logger.debug("psutil not available - skipping RAM/CPU detection")
    
    # GPU info if available
    try:
        import torch
        if torch.cuda.is_available():
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
            logger.info(f"CUDA Version: {torch.version.cuda}")
        else:
            logger.info("GPU: None detected (Running in CPU Fallback mode)")
    except ImportError:
        logger.debug("PyTorch not available - skipping GPU detection")
    
    logger.info("==========================================")


def log_shutdown():
    """Log graceful shutdown sequence."""
    logger.info("=== HackT Sovereign Core Shutdown Sequence ===")
    logger.info("Flushing log handlers...")
    logging.shutdown()
    logger.info("Shutdown complete.")


# ==============================================================================
# Exception Handling Utility
# ==============================================================================

def log_exception(logger: logging.Logger, message: str, exc: Exception, context: Optional[Dict] = None):
    """
    Logs an exception with full traceback and optional context.
    
    Args:
        logger: The logger instance
        message: Custom error message
        exc: The exception object
        context: Optional dict of extra context
    """
    log_with_context(
        logger,
        logging.ERROR,
        f"{message}: {str(exc)}",
        context={
            **(context or {}),
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    )


# Auto-initialize on import
_setup_base_logger()    