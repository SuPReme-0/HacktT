"""
HackT Sovereign Core - OS-Level Code Injector
==============================================
Provides the "Time-Stop" hardware injection protocol.
Seizes control of the OS clipboard and keyboard to physically inject
AI-generated code fixes directly into the active window.
"""

import time
import sys
import pyautogui
import pyperclip
from utils.logger import get_logger

logger = get_logger("hackt.utils.injector")

class CodeInjector:
    """
    OS-Level Code Injection Utility.
    Cross-platform safe, but hardware locking is Windows-only.
    """
    def __init__(self):
        # Failsafe: slamming the mouse to the corner of the screen aborts pyautogui
        pyautogui.FAILSAFE = True 
        pyautogui.PAUSE = 0.05  # Delay between simulated keypresses
        
        self.is_windows = sys.platform == "win32"
        self.is_mac = sys.platform == "darwin"
        
        # Cross-platform modifier key
        self.modifier = 'command' if self.is_mac else 'ctrl'

        self.ctypes = None
        if self.is_windows:
            import ctypes
            self.ctypes = ctypes

    def _toggle_block_input(self, state: bool):
        """
        Calls the Windows user32.dll to physically block/unblock hardware input.
        Requires the .exe/script to be run as Administrator.
        """
        if not self.is_windows or not self.ctypes:
            return # Safe fallback for Mac/Linux
            
        try:
            # BlockInput returns True if successful, False if it lacks Admin rights
            success = self.ctypes.windll.user32.BlockInput(state)
            if not success and state:
                logger.warning("Injector: Failed to lock hardware. App likely missing Admin privileges.")
        except Exception as e:
            logger.error(f"Injector: BlockInput API call failed: {e}")

    def phantom_type(self, new_code: str) -> bool:
        """
        Strategy 2: Time-Stop OS Keyboard Hijack.
        Freezes the user, pastes the code, and unfreezes the user in <200ms.
        
        Args:
            new_code: The raw text/code to inject.
            
        Returns:
            True if injection executed without crashing.
        """
        try:
            logger.info("Injector: Initiating Time-Stop Phantom Injection.")
            
            # 1. Save clipboard and set new payload
            original_clipboard = pyperclip.paste()
            pyperclip.copy(new_code)
            
            # CRITICAL: Allow OS clipboard manager 50ms to register the new payload
            time.sleep(0.05) 
            
            # 2. ENGAGE HARDWARE LOCK (Time Stop)
            self._toggle_block_input(True)
            
            try:
                # 3. Inject (Simulated inputs bypass the BlockInput lock)
                pyautogui.hotkey(self.modifier, 'a')  
                time.sleep(0.05)                
                pyautogui.hotkey(self.modifier, 'v')  
                
                # CRITICAL: Wait 100ms for the IDE to process the paste command 
                # BEFORE we restore the clipboard, otherwise it pastes the old code.
                time.sleep(0.1) 
            finally:
                # 4. DISENGAGE HARDWARE LOCK (Must be in a finally block)
                # If pyautogui crashes, we MUST release the lock or the PC is soft-bricked!
                self._toggle_block_input(False)
            
            # 5. Restore clipboard quietly
            pyperclip.copy(original_clipboard)
            
            logger.info("Injector: Code injected successfully. Hardware unlocked.")
            return True
            
        except Exception as e:
            logger.error(f"Injector: Phantom typing aborted: {e}")
            # Failsafe unlock just in case
            self._toggle_block_input(False) 
            return False

# Singleton instance
injector = CodeInjector()