import logging
import os
import sys
from datetime import datetime

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger that writes to both the console 
    and a rolling daily file in the user's AppData directory.
    """
    logger = logging.getLogger(name)
    
    # Prevent adding duplicate handlers if called multiple times
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.INFO)

    # Determine secure log path: %AppData%/HackT/logs/ on Windows
    if sys.platform == "win32":
        base_dir = os.environ.get("APPDATA", os.path.expanduser("~"))
        log_dir = os.path.join(base_dir, "HackT", "logs")
    else:
        # Fallback for Linux/Mac during development
        log_dir = os.path.join(os.path.expanduser("~"), ".hackt", "logs")

    os.makedirs(log_dir, exist_ok=True)
    
    # Create a new log file for each day
    log_file = os.path.join(log_dir, f"runtime_{datetime.now().strftime('%Y%m%d')}.log")

    # Standardized Formatter
    formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. File Handler (UTF-8 to prevent char encoding crashes on Windows)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 2. Console Handler (Useful when testing the FastAPI server directly)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger