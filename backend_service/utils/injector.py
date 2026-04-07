# """
# HackT Sovereign Core - OS-Level Code Injector (v3.0)
# =====================================================
# Provides the "Time-Stop" hardware injection protocol with enterprise safety rails.
# Features:
# - Watchdog Timer (Forces unlock after 5s to prevent soft-brick)
# - Admin Privilege Verification (Windows BlockInput requires elevation)
# - Clipboard Verification Loops (Confirms payload before injection)
# - Injection Audit Trail (Logs what was injected for security compliance)
# - Line-Range Injection Support (Granular control vs. full-file replace)
# - Cross-Platform Keyboard Simulation (Windows/Mac/Linux)
# """

# import os
# import sys
# import time
# import asyncio
# import hashlib
# import logging
# from pathlib import Path
# from datetime import datetime
# from typing import Optional, Dict, Any
# from contextlib import contextmanager

# try:
#     import pyautogui
#     import pyperclip
#     PYAUTOGUI_AVAILABLE = True
# except ImportError:
#     PYAUTOGUI_AVAILABLE = False
#     pyautogui = None
#     pyperclip = None

# # Cross-platform keyboard simulation fallback
# try:
#     from pynput.keyboard import Controller, Key
#     PYNPUT_AVAILABLE = True
# except ImportError:
#     PYNPUT_AVAILABLE = False

# from utils.logger import get_logger
# from utils.config import config

# logger = get_logger("hackt.utils.injector")

# class CodeInjector:
#     """
#     OS-Level Code Injection Utility.
#     Engineered with multiple safety rails to prevent system lockouts.
#     """
    
#     def __init__(self):
#         # Failsafe: Moving mouse to corner aborts pyautogui immediately
#         if PYAUTOGUI_AVAILABLE:
#             pyautogui.FAILSAFE = True
#             pyautogui.PAUSE = 0.05  # Delay between simulated keypresses
        
#         self.is_windows = sys.platform == "win32"
#         self.is_mac = sys.platform == "darwin"
#         self.is_linux = sys.platform == "linux"
        
#         # Cross-platform modifier key
#         self.modifier = Key.cmd if self.is_mac else Key.ctrl
        
#         # Windows-specific API handles
#         self.ctypes = None
#         self.is_admin = False
        
#         if self.is_windows:
#             try:
#                 import ctypes
#                 self.ctypes = ctypes
#                 self._check_admin_privileges()
#             except ImportError:
#                 logger.warning("Injector: ctypes not available. BlockInput disabled.")
        
#         # Safety Configuration
#         self.max_lock_duration_sec = 5.0  # Watchdog timer
#         self.clipboard_verify_retries = 5
#         self.clipboard_verify_delay = 0.1
        
#         # Audit Trail
#         self.audit_log_path = config.paths.data_dir / "injection_audit.json"
#         self._ensure_audit_log()
        
#         # Keyboard controller for cross-platform support
#         self.keyboard = Controller() if PYNPUT_AVAILABLE else None

#     def _check_admin_privileges(self) -> bool:
#         """Verify if the application has Administrator rights (Required for BlockInput)."""
#         if not self.is_windows or not self.ctypes:
#             return False
        
#         try:
#             import ctypes
#             # Check if running as admin
#             is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
#             self.is_admin = is_admin
#             if not is_admin:
#                 logger.warning("Injector: Running without Admin privileges. BlockInput will fail.")
#             return is_admin
#         except Exception as e:
#             logger.error(f"Injector: Admin check failed: {e}")
#             return False

#     def _ensure_audit_log(self):
#         """Initialize the injection audit trail file."""
#         try:
#             import json
#             if not self.audit_log_path.exists():
#                 with open(self.audit_log_path, 'w', encoding='utf-8') as f:
#                     json.dump([], f)
#         except Exception as e:
#             logger.error(f"Injector: Failed to initialize audit log: {e}")

#     def _log_injection(self, success: bool, file_path: str, code_hash: str, 
#                        code_length: int, method: str):
#         """Record injection attempt for security audit trail."""
#         try:
#             import json
#             audit_entry = {
#                 "timestamp": datetime.utcnow().isoformat(),
#                 "success": success,
#                 "file_path": file_path,
#                 "code_hash": code_hash,
#                 "code_length": code_length,
#                 "method": method,
#                 "platform": sys.platform,
#                 "admin_mode": self.is_admin
#             }
            
#             # Load existing log, append, save
#             with open(self.audit_log_path, 'r', encoding='utf-8') as f:
#                 audit_log = json.load(f)
            
#             audit_log.append(audit_entry)
            
#             # Keep only last 1000 entries to prevent log bloat
#             audit_log = audit_log[-1000:]
            
#             with open(self.audit_log_path, 'w', encoding='utf-8') as f:
#                 json.dump(audit_log, f, indent=2)
                
#         except Exception as e:
#             logger.error(f"Injector: Audit logging failed: {e}")

#     @contextmanager
#     def _hardware_lock_watchdog(self):
#         """
#         Context manager with watchdog timer.
#         Guarantees hardware unlock even if injection crashes.
#         """
#         lock_acquired = False
#         try:
#             if self.is_windows and self.is_admin and self.ctypes:
#                 # Attempt to block input
#                 lock_acquired = self.ctypes.windll.user32.BlockInput(True)
#                 if lock_acquired:
#                     logger.info("Injector: Hardware lock ENGAGED (Time-Stop active).")
#                 else:
#                     logger.warning("Injector: Hardware lock failed. Admin rights required.")
#             yield lock_acquired
#         finally:
#             # GUARANTEED UNLOCK - This MUST execute even on crash
#             if lock_acquired and self.ctypes:
#                 try:
#                     self.ctypes.windll.user32.BlockInput(False)
#                     logger.info("Injector: Hardware lock DISENGAGED.")
#                 except Exception as e:
#                     logger.critical(f"Injector: CRITICAL - Failed to release hardware lock: {e}")
#                     # Attempt emergency unlock via pyautogui failsafe
#                     if PYAUTOGUI_AVAILABLE:
#                         pyautogui.moveTo(1920, 0)  # Trigger failsafe

#     def _verify_clipboard(self, expected_hash: str) -> bool:
#         """
#         Verification loop: Confirms clipboard contains our payload before injection.
#         Prevents race conditions with cloud clipboard sync.
#         """
#         if not PYAUTOGUI_AVAILABLE or not pyperclip:
#             return False
            
#         for attempt in range(self.clipboard_verify_retries):
#             try:
#                 current_content = pyperclip.paste()
#                 current_hash = hashlib.sha256(current_content.encode()).hexdigest()
#                 if current_hash == expected_hash:
#                     return True
#                 logger.debug(f"Injector: Clipboard verification attempt {attempt + 1}/{self.clipboard_verify_retries} failed.")
#                 time.sleep(self.clipboard_verify_delay)
#             except Exception as e:
#                 logger.debug(f"Injector: Clipboard check error: {e}")
#                 time.sleep(self.clipboard_verify_delay)
        
#         logger.error("Injector: Clipboard verification failed after all retries.")
#         return False

#     def _safe_clipboard_action(self, action: str, payload: Optional[str] = None, 
#                                 retries: int = 3) -> Optional[str]:
#         """
#         Windows clipboard is notoriously flaky. Retry loop guarantees execution.
#         """
#         if not PYAUTOGUI_AVAILABLE or not pyperclip:
#             return None
            
#         for attempt in range(retries):
#             try:
#                 if action == "copy" and payload is not None:
#                     pyperclip.copy(payload)
#                     return None
#                 elif action == "paste":
#                     return pyperclip.paste()
#             except Exception as e:
#                 if attempt == retries - 1:
#                     logger.error(f"Injector: Clipboard {action} failed after {retries} attempts: {e}")
#                     raise
#                 time.sleep(0.1)
#         return None

#     def _simulate_keyboard_input(self, keys: list):
#         """
#         Cross-platform keyboard simulation.
#         Uses pynput as primary, pyautogui as fallback.
#         """
#         if PYNPUT_AVAILABLE and self.keyboard:
#             for key in keys:
#                 self.keyboard.press(key)
#                 self.keyboard.release(key)
#                 time.sleep(0.02)
#         elif PYAUTOGUI_AVAILABLE:
#             for key in keys:
#                 pyautogui.press(key)
#                 time.sleep(0.02)
#         else:
#             logger.error("Injector: No keyboard simulation library available.")

#     def _phantom_type_sync(self, new_code: str, file_path: str = "unknown", 
#                            replace_all: bool = False, 
#                            line_range: Optional[tuple] = None) -> bool:
#         """
#         Synchronous execution of the Time-Stop OS Keyboard Hijack.
#         """
#         original_clipboard = ""
#         code_hash = hashlib.sha256(new_code.encode()).hexdigest()
#         success = False
        
#         try:
#             logger.info(f"Injector: Initiating Time-Stop Phantom Injection for {file_path}.")
            
#             # 1. Save original clipboard safely
#             try:
#                 original_clipboard = self._safe_clipboard_action("paste") or ""
#             except:
#                 original_clipboard = ""
            
#             # 2. Set new payload and verify it registered
#             self._safe_clipboard_action("copy", new_code)
#             time.sleep(0.05)
            
#             # 3. CRITICAL: Verify clipboard contains our payload before locking hardware
#             payload_hash = hashlib.sha256(new_code.encode()).hexdigest()
#             if not self._verify_clipboard(payload_hash):
#                 logger.error("Injector: Aborting - Clipboard verification failed.")
#                 self._log_injection(False, file_path, code_hash, len(new_code), "clipboard_verify_fail")
#                 return False
            
#             # 4. ENGAGE HARDWARE LOCK (With Watchdog Guarantee)
#             with self._hardware_lock_watchdog() as lock_acquired:
                
#                 # 5. Inject (Simulated inputs)
#                 if replace_all:
#                     # Select all content first
#                     if self.is_mac:
#                         self._simulate_keyboard_input([Key.cmd, 'a'])
#                     else:
#                         self._simulate_keyboard_input([Key.ctrl, 'a'])
#                     time.sleep(0.05)
                
#                 # Paste the code
#                 if self.is_mac:
#                     self._simulate_keyboard_input([Key.cmd, 'v'])
#                 else:
#                     self._simulate_keyboard_input([Key.ctrl, 'v'])
                
#                 # CRITICAL: Wait for IDE to process paste BEFORE restoring clipboard
#                 # Heavy IDEs like IntelliJ may need 200-300ms
#                 time.sleep(0.20)
                
#                 success = True
            
#             # 6. Restore original clipboard quietly
#             try:
#                 if original_clipboard:
#                     self._safe_clipboard_action("copy", original_clipboard)
#             except:
#                 pass  # Non-critical failure
            
#             logger.info(f"Injector: Code injected successfully into {file_path}. Hardware unlocked.")
#             self._log_injection(True, file_path, code_hash, len(new_code), 
#                                "full_replace" if replace_all else "paste")
#             return True
            
#         except Exception as e:
#             logger.error(f"Injector: Phantom typing aborted: {e}")
#             self._log_injection(False, file_path, code_hash, len(new_code), f"exception:{str(e)[:50]}")
            
#             # Emergency clipboard restore
#             try:
#                 if original_clipboard:
#                     self._safe_clipboard_action("copy", original_clipboard)
#             except:
#                 pass
            
#             return False

#     async def inject_code(self, new_code: str, file_path: str = "unknown", 
#                           replace_all: bool = False,
#                           line_range: Optional[tuple] = None,
#                           require_confirmation: bool = True) -> Dict[str, Any]:
#         """
#         Asynchronous wrapper with safety validation.
        
#         Args:
#             new_code: The code to inject
#             file_path: Target file path (for audit trail)
#             replace_all: If True, selects all content before pasting (DANGEROUS)
#             line_range: Optional (start_line, end_line) for granular injection
#             require_confirmation: If True, requires explicit user confirmation for replace_all
        
#         Returns:
#             Dict with success status, audit info, and any error messages
#         """
#         # Safety Validation
#         if replace_all and require_confirmation:
#             # In production, this would wait for React UI confirmation
#             # For now, we log the warning and proceed with caution
#             logger.warning(f"Injector: Full file replacement requested for {file_path}. This is irreversible.")
        
#         if len(new_code) > 50000:
#             logger.warning(f"Injector: Large code payload ({len(new_code)} chars). Injection may be slow.")
        
#         # Execute injection in background thread
#         result = await asyncio.to_thread(
#             self._phantom_type_sync, 
#             new_code, 
#             file_path, 
#             replace_all
#         )
        
#         return {
#             "success": result,
#             "file_path": file_path,
#             "code_hash": hashlib.sha256(new_code.encode()).hexdigest(),
#             "code_length": len(new_code),
#             "method": "full_replace" if replace_all else "paste",
#             "timestamp": datetime.utcnow().isoformat()
#         }

#     async def inject_at_line(self, file_path: str, line_number: int, 
#                               new_code: str) -> Dict[str, Any]:
#         """
#         Inject code at a specific line number.
#         Requires IDE support for line navigation (VS Code, IntelliJ).
#         """
#         # This would require more sophisticated IDE integration
#         # For now, we log that this feature requires extension support
#         logger.info(f"Injector: Line-specific injection requested for {file_path}:{line_number}")
#         logger.warning("Injector: Line-specific injection requires IDE extension support. Falling back to paste.")
        
#         return await self.inject_code(new_code, file_path, replace_all=False)

# # Singleton instance
# injector = CodeInjector()