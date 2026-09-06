#!/usr/bin/env python3
"""
build_grammars.py – Compile Tree-Sitter Grammars into a Single Shared Library
============================================================================
This script clones the official grammar repositories at specific ABI-14
compatible tags and compiles them into a single `my-languages.so` file.

The library is placed in CONFIG["BASE_PATH"] / "build". After compilation,
the ingestion pipeline (chunker.py and worker.py) can load it directly.

Requirements:
- git installed
- C compiler (gcc, clang, or MSVC)
- tree-sitter Python package (0.21.3)
"""

import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

# Add project root to path so we can import config
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config import CONFIG, logger
except ImportError:
    # Fallback if config not found
    CONFIG = {"BASE_PATH": Path.home() / "hackt_vault"}
    logger = print

try:
    from tree_sitter import Language
except ImportError:
    logger.error("tree-sitter not installed. Run: pip install tree-sitter==0.21.3")
    sys.exit(1)

# ==============================================================================
# FAILSAFE: Check for Tree-sitter v0.22+ which removed build_library
# ==============================================================================
if not hasattr(Language, "build_library"):
    logger("\n🚨 CRITICAL ERROR: Your tree-sitter version is too new!")
    logger("The 'Language.build_library' function was removed in tree-sitter v0.22.0.")
    logger("To fix this and compile 'my-languages.so', run this in your terminal:")
    logger("    pip install tree-sitter==0.21.3")
    sys.exit(1)

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
BUILD_DIR = CONFIG["BASE_PATH"] / "build"
LIBRARY_PATH = BUILD_DIR / "my-languages.so"

# Grammar repositories with pinned tags (ABI-14 compatible)
GRAMMARS = {
    "python": {
        "url": "https://github.com/tree-sitter/tree-sitter-python.git",
        "tag": "v0.20.4"
    },
    "javascript": {
        "url": "https://github.com/tree-sitter/tree-sitter-javascript.git",
        "tag": "v0.20.3"
    },
    "java": {
        "url": "https://github.com/tree-sitter/tree-sitter-java.git",
        "tag": "v0.20.2"
    },
    "go": {
        "url": "https://github.com/tree-sitter/tree-sitter-go.git",
        "tag": "v0.20.0"
    },
    "cpp": {
        "url": "https://github.com/tree-sitter/tree-sitter-cpp.git",
        "tag": "v0.20.3"
    },
    "rust": {
        "url": "https://github.com/tree-sitter/tree-sitter-rust.git",
        "tag": "v0.20.4"
    },
}

def check_git():
    """Ensure git is installed."""
    if shutil.which("git") is None:
        logger.error("git is not installed. Please install git first.")
        sys.exit(1)

def clone_and_checkout(url, dest, tag):
    """Clone the repository and checkout the specified tag."""
    if dest.exists():
        logger(f"Updating existing repository in {dest}")
        subprocess.run(["git", "-C", str(dest), "fetch", "--tags"], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", tag], check=True)
    else:
        logger(f"Cloning {url} into {dest}")
        subprocess.run(["git", "clone", url, str(dest)], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", tag], check=True)

def main():
    logger("=" * 70)
    logger("Compiling Tree-Sitter Grammars (ABI 14) for V21.0-Lite")
    logger("=" * 70)

    check_git()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # Create a temporary directory for all grammar sources
    with tempfile.TemporaryDirectory(prefix="tree-sitter-") as tmpdir:
        grammar_paths = []
        for lang, info in GRAMMARS.items():
            repo_dir = Path(tmpdir) / f"tree-sitter-{lang}"
            clone_and_checkout(info["url"], repo_dir, info["tag"])
            grammar_paths.append(str(repo_dir))

        logger(f"Compiling {len(grammar_paths)} grammars into {LIBRARY_PATH}")
        try:
            Language.build_library(str(LIBRARY_PATH), grammar_paths)
            logger("✅ Compilation successful!")
        except Exception as e:
            logger(f"Compilation failed: {e}")
            logger("Please ensure you have a C compiler installed (gcc, clang, or MSVC).")
            sys.exit(1)

    # Optional: verify the library by loading one language
    try:
        lib = Language(str(LIBRARY_PATH), "python")
        logger("Embedded languages: " + ", ".join(GRAMMARS.keys()))
    except Exception as e:
        logger(f"Verification failed: {e}")

    logger("=" * 70)
    logger("Grammar compilation complete. You can now run the ingestion pipeline.")
    logger("=" * 70)

if __name__ == "__main__":
    main()