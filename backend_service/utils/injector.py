import time
import ctypes
import pyautogui
import pyperclip
import logging
from utils.logger import get_logger

logger = get_logger("hackt.utils.injector")

class CodeInjector:
    def __init__(self):
        pyautogui.FAILSAFE = True 
        pyautogui.PAUSE = 0.05  # Faster execution

    def _toggle_block_input(self, state: bool):
        """
        Calls the Windows user32.dll to physically block/unblock hardware input.
        Requires the .exe to be run as Administrator.
        """
        try:
            # BlockInput returns True if successful, False if it lacks Admin rights
            success = ctypes.windll.user32.BlockInput(state)
            if not success and state:
                logger.warning("Injector: Failed to lock hardware. App likely missing Admin privileges.")
        except Exception as e:
            logger.error(f"Injector: BlockInput API call failed: {e}")

    def phantom_type(self, new_code: str):
        """
        Strategy 2: Time-Stop OS Keyboard Hijack.
        Freezes the user, pastes the code, and unfreezes the user in <200ms.
        """
        try:
            logger.info("Injector: Initiating Time-Stop Phantom Injection.")
            
            # 1. Save clipboard
            original_clipboard = pyperclip.paste()
            pyperclip.copy(new_code)
            
            # 2. ENGAGE HARDWARE LOCK (Time Stop)
            self._toggle_block_input(True)
            
            try:
                # 3. Inject (Simulated inputs bypass the BlockInput lock)
                pyautogui.hotkey('ctrl', 'a')  
                time.sleep(0.05)                
                pyautogui.hotkey('ctrl', 'v')  
            finally:
                # 4. DISENGAGE HARDWARE LOCK (CRITICAL: Must be in a finally block)
                # If pyautogui crashes, we MUST release the lock or the PC is soft-bricked!
                self._toggle_block_input(False)
            
            # 5. Restore clipboard
            time.sleep(0.05)
            pyperclip.copy(original_clipboard)
            
            logger.info("Injector: Code injected successfully. Hardware unlocked.")
            return True
            
        except Exception as e:
            logger.error(f"Injector: Phantom typing aborted: {e}")
            # Failsafe unlock just in case
            self._toggle_block_input(False) 
            return False

injector = CodeInjector()