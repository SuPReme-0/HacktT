"""
HackT Sovereign Core - Code Watcher Service Module (v3.0)
=========================================================
Provides IDE integration for real-time code analysis:
- Debounced file system watching (Watchdog)
- VRAM-safe Active Context windowing (Config-synced)
- Telemetry broadcasting to React via WebSocket
- Terminal log context support for live hack detection
- Diff Bridge Ready (Supplies fix data, frontend applies it)
"""

import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object

from utils.logger import get_logger
from utils.config import config

# Lazy import for WebSocket to prevent boot-time circular dependencies
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

logger = get_logger("hackt.services.code_watcher")


class ActiveFileHandler(FileSystemEventHandler):
    """
    Handles OS-level file modification events.
    Passes events back to the main CodeWatcher with debounce protection.
    """

    def __init__(self, watcher_instance):
        self.watcher = watcher_instance
        self.ignored_extensions = {
            '.pyc', '.pyo', '.pyd', '.git', '.exe', '.dll', '.so', '.dylib',
            '.log', '.db', '.sqlite', '.bin', '.lock', '.cache'
        }
        self.ignored_dirs = {
            'node_modules', '.git', '__pycache__', 'venv', 'env', '.idea',
            '.vscode', 'dist', 'build', '.next', 'target', 'vendor'
        }

    def is_valid_file(self, path: str) -> bool:
        """Filters out compiled binaries, logs, and massive hidden folders."""
        path_obj = Path(path)
        if path_obj.suffix in self.ignored_extensions:
            return False
        for part in path_obj.parts:
            if part in self.ignored_dirs:
                return False
        # Only watch code-related files
        valid_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
            '.json', '.yaml', '.yml', '.md', '.rst', '.txt', '.sh', '.bash',
            '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.java', '.php', '.rb',
            '.swift', '.kt', '.scala', '.sql', '.graphql', '.vue', '.svelte'
        }
        return path_obj.suffix in valid_extensions

    def on_modified(self, event):
        if not event.is_directory and self.is_valid_file(event.src_path):
            self.watcher.trigger_file_update(event.src_path)

    def on_created(self, event):
        """Also track new file creation for real-time context."""
        if not event.is_directory and self.is_valid_file(event.src_path):
            self.watcher.trigger_file_update(event.src_path)


class CodeWatcher:
    """
    IDE integration handler for real-time code context.
    Features Debouncing, Telemetry Broadcasting, and Diff Bridge Support.
    """

    def __init__(self):
        self.vault_path = config.paths.vault_dir
        self._observer: Optional[Observer] = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

        # State Tracking
        self._active_files: Dict[str, Dict[str, Any]] = {}
        self._last_active_file: str = ""
        self._terminal_context: str = ""  # Live terminal output buffer

        # Debounce logic (Prevents parsing the same file 100 times during auto-save)
        self._debounce_timers: Dict[str, float] = {}
        self.debounce_delay_sec = config.modes.screen_scan_interval  # Sync with config

        # Context limits (Sync with RAG config for consistency)
        self.max_context_chars = config.rag.max_context_chars // 2  # Leave room for RAG + History

        # Watched directories
        self._watched_directories: List[str] = []

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Capture the FastAPI event loop for WebSocket broadcasting."""
        self._main_loop = loop

    def start_watching(self, directory: str):
        """Start file system watching for a specific project directory."""
        if not WATCHDOG_AVAILABLE:
            logger.error("CodeWatcher: watchdog not installed. pip install watchdog")
            return

        if directory in self._watched_directories:
            logger.warning(f"CodeWatcher: Already watching {directory}")
            return

        path = Path(directory)
        if not path.exists() or not path.is_dir():
            logger.error(f"CodeWatcher: Invalid directory: {directory}")
            return

        try:
            if not self._observer:
                self._observer = Observer()

            event_handler = ActiveFileHandler(self)
            self._observer.schedule(event_handler, str(path), recursive=True)
            self._observer.start()
            self._watched_directories.append(directory)
            logger.info(f"CodeWatcher: ONLINE. Monitoring: {directory}")

            # Broadcast to React that watching has started
            self._broadcast_context_update()

        except Exception as e:
            logger.error(f"CodeWatcher: Failed to start observer: {e}")

    def stop_watching(self):
        """Stop file system watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            self._watched_directories.clear()
            logger.info("CodeWatcher: OFFLINE.")

    def trigger_file_update(self, file_path: str):
        """
        Called by the OS Event Handler.
        Implements Debouncing so we only read the file when the user pauses typing/saving.
        """
        current_time = time.time()
        self._debounce_timers[file_path] = current_time

        # Fire and forget an async background task to check the debounce timer later
        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._process_if_debounced(file_path, current_time),
                self._main_loop
            )
        else:
            # Fallback if event loop isn't captured yet
            asyncio.create_task(self._process_if_debounced(file_path, current_time))

    async def _process_if_debounced(self, file_path: str, trigger_time: float):
        """Wait for the debounce delay, then process if no new events occurred."""
        await asyncio.sleep(self.debounce_delay_sec)

        # If the timer has been updated by a newer event, abort this specific execution
        if self._debounce_timers.get(file_path) != trigger_time:
            return

        self._read_and_store_file(file_path)
        # Broadcast context update to React after processing
        await self._broadcast_context_update_async()

    def _read_and_store_file(self, file_path: str):
        """Safely read the file into memory and extract VRAM-safe context."""
        try:
            # Files can be locked by the OS during saving, try/except is mandatory
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # File is too large! We must truncate to protect the LLM context window.
            # We take the TOP and BOTTOM of the file, as that's usually where imports/exports and active work is.
            is_truncated = False
            if len(content) > self.max_context_chars:
                half = self.max_context_chars // 2
                content = f"{content[:half]}\n\n...[CODE TRUNCATED FOR CONTEXT SAFETY]...\n\n{content[-half:]}"
                is_truncated = True

            self._active_files[file_path] = {
                "content": content,
                "timestamp": time.time(),
                "is_truncated": is_truncated,
                "line_count": content.count('\n') + 1
            }
            self._last_active_file = file_path

            logger.debug(f"CodeWatcher: Context updated for {Path(file_path).name}")

        except PermissionError:
            pass  # File currently locked by IDE, watchdog will catch it on the next save
        except Exception as e:
            logger.error(f"CodeWatcher: Failed to read {file_path}: {e}")

    def update_terminal_context(self, terminal_output: str):
        """
        Update the live terminal log buffer (called by port_listeners.py).
        Used for detecting live hack attempts, nmap scans, etc.
        """
        # Truncate to prevent memory bloat
        self._terminal_context = terminal_output[-5000:]
        logger.debug(f"CodeWatcher: Terminal context updated ({len(self._terminal_context)} chars)")

    async def _broadcast_context_update_async(self):
        """Broadcast context update to React via WebSocket."""
        if telemetry_manager and self._main_loop:
            context = self.get_active_context()
            if context:
                await telemetry_manager.send_context_update({
                    "type": "ide",
                    "file": context.get("file_path", ""),
                    "file_name": context.get("file_name", ""),
                    "language": context.get("language", ""),
                    "line_count": context.get("line_count", 0),
                    "is_truncated": context.get("is_truncated", False)
                })

    def _broadcast_context_update(self):
        """Synchronous wrapper for context broadcasting."""
        if self._main_loop and self._main_loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._broadcast_context_update_async(),
                self._main_loop
            )

    async def submit_fix_for_review(self, file_path: str, suggested_fix: str,
                                     threat_level: str, description: str) -> bool:
        """
        🚀 DIFF BRIDGE: Submit a fix for React UI review (NOT direct injection).
        Sends the fix data to WebSocket for the Diff Modal to display.
        User must approve in UI before any code changes are applied.
        """
        if not telemetry_manager:
            logger.error("CodeWatcher: Telemetry manager unavailable for diff bridge.")
            return False

        original_code = self._active_files.get(file_path, {}).get("content", "")

        # Broadcast the diff payload to React
        await telemetry_manager.broadcast_json({
            "type": "code_diff_available",
            "data": {
                "file_path": file_path,
                "original_code": original_code[:3000],  # Truncate for payload size
                "suggested_fix": suggested_fix,
                "threat_level": threat_level,
                "description": description,
                "timestamp": time.time()
            }
        })

        logger.info(f"CodeWatcher: Diff bridge payload sent for {file_path}")
        return True

    def get_active_context(self) -> Dict[str, Any]:
        """
        Returns the exact context string formatted for the PromptOrchestrator.
        Includes terminal output if available for live hack detection.
        """
        if not self._last_active_file or self._last_active_file not in self._active_files:
            return {}

        file_data = self._active_files[self._last_active_file]
        file_path = Path(self._last_active_file)

        # Format explicitly for the LLM
        context_str = f"File: {file_path.name}\n"
        context_str += f"Path: {file_path}\n"
        context_str += f"Status: {'Truncated' if file_data['is_truncated'] else 'Full'}\n"
        context_str += f"Lines: {file_data.get('line_count', 'Unknown')}\n"
        context_str += f"Code:\n```\n{file_data['content']}\n```"

        # Include terminal context if available (for live hack detection)
        if self._terminal_context:
            context_str += f"\n\nTerminal Output:\n```\n{self._terminal_context}\n```"

        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "language": file_path.suffix.replace('.', ''),
            "line_count": file_data.get('line_count', 0),
            "is_truncated": file_data['is_truncated'],
            "llm_context_string": context_str,
            "has_terminal_context": bool(self._terminal_context)
        }

    def get_all_watched_files(self) -> List[Dict[str, Any]]:
        """Returns metadata for all currently tracked files (for React sidebar)."""
        files = []
        for path, data in self._active_files.items():
            files.append({
                "file_path": path,
                "file_name": Path(path).name,
                "language": Path(path).suffix.replace('.', ''),
                "line_count": data.get('line_count', 0),
                "last_modified": data.get('timestamp', 0)
            })
        # Sort by most recently modified
        return sorted(files, key=lambda x: x['last_modified'], reverse=True)

    def clear_terminal_context(self):
        """Clear the terminal buffer (called after threat analysis completes)."""
        self._terminal_context = ""
        logger.debug("CodeWatcher: Terminal context cleared.")


# Singleton instance
code_watcher = CodeWatcher()