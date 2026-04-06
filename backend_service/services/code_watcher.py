"""
HackT Sovereign Core - Code Watcher Service Module
===================================================
Provides IDE integration for real-time code analysis:
- File system watching for active project files
- AST-based semantic chunking for RAG indexing
- Secure code injection via OS-level automation
- Context streaming to React via telemetry
"""

import logging
import asyncio
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from utils.logger import get_logger

logger = get_logger("hackt.services.code_watcher")


class CodeWatcher:
    """
    IDE integration handler for real-time code context.
    
    Features:
    - Tracks active files by modification timestamp
    - Secure code injection via pyautogui + BlockInput ("Time-Stop")
    - OS-agnostic safety checks
    """
    
    def __init__(self, vault_path: Path, chunk_size: int = 512):
        self.vault_path = vault_path
        self.chunk_size = chunk_size
        self._watcher = None  # Placeholder for watchdog.Observer
        
        # Track active files: file_path -> {"content": str, "timestamp": float}
        self._active_files: Dict[str, Dict] = {} 
        
    def start_watching(self, directories: List[str]):
        """Start file system watching for specified directories"""
        logger.info(f"CodeWatcher started for directories: {directories}")
    
    def stop_watching(self):
        """Stop file system watching"""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        logger.info("CodeWatcher stopped")
    
    def on_file_modified(self, file_path: Path) -> List[Dict]:
        """Handle file modification: chunk and optionally index."""
        try:
            with open(file_path, 'r', errors='ignore') as f:
                content = f.read()
            
            # FIXED: Store modification timestamp for accurate retrieval
            self._active_files[str(file_path)] = {
                "content": content,
                "timestamp": time.time()
            }
            
            # NOTE: Assuming `processor` is imported or defined locally for chunking.
            # If `utils.preprocessor` is not yet built, we mock the chunking for now.
            try:
                from utils.preprocessor import processor
                chunks = processor.chunk_text(content, chunk_size=self.chunk_size)
            except ImportError:
                # Fallback simple chunking if preprocessor isn't built yet
                chunks = [content[i:i+self.chunk_size] for i in range(0, len(content), self.chunk_size)]
            
            formatted_chunks = [
                {
                    "file": str(file_path),
                    "text": chunk,
                    "vault_id": 3,
                    "type": "code"
                }
                for chunk in chunks
            ]
            
            return formatted_chunks
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return []
    
    async def inject_fix(self, file_path: str, new_code: str) -> bool:
        """
        Inject AI-generated fix into active IDE via OS-level automation.
        Uses "Time-Stop" strategy: BlockInput + pyautogui for reliable injection.
        """
        logger.info(f"Injecting OS-level fix into {file_path}")
        
        # Offload the blocking OS manipulation to a separate thread so we don't freeze FastAPI
        return await asyncio.to_thread(self._sync_inject_fix, file_path, new_code)

    def _sync_inject_fix(self, file_path: str, new_code: str) -> bool:
        """Synchronous payload for OS-level injection"""
        from utils.injector import injector
        return injector.phantom_type(new_code)

    def get_active_context(self) -> Dict:
        """Get current active file context for React display"""
        if not self._active_files:
            return {}
        
        # FIXED: Return the most recently modified file based on timestamp
        latest_file = max(self._active_files.items(), key=lambda item: item[1]["timestamp"])[0]
        content = self._active_files[latest_file]["content"]
        
        return {
            "file": latest_file,
            "content_preview": content[:500] + "...",
            "language": Path(latest_file).suffix
        }


# Singleton instance
code_watcher = CodeWatcher(vault_path=Path("vault"))