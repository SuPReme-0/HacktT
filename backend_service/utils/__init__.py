"""
HackT Sovereign Core - Utilities Package
=========================================
Foundational utilities for configuration, logging, and state management.
Designed to be imported early in the bootstrap sequence without circular dependencies.
"""

# 1. Configuration (The Source of Truth)
# Must be imported first to ensure paths and settings are available
from utils.config import config

# 2. Logger (Standardized Logging)
# Safe to import anywhere after config
from utils.logger import get_logger, log_system_info, log_shutdown

# 3. Preprocessor (Content Cleaning & Chunking)
# Used by ingestion and code_watcher
from utils.preprocessor import processor

# 4. Runtime State (Mutable Global State)
# Prevents circular imports with main.py for things like 'current_threat_level'
from utils.state import app_state

# 5. Legacy/Archived (Do not import by default)
# from utils.injector import injector  # Archived for UI Diff Bridge

__all__ = [
    "config",
    "get_logger",
    "log_system_info",
    "log_shutdown",
    "processor",
    "app_state"
]