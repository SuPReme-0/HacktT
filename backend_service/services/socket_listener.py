import asyncio
import websockets
import json
from core.retriever import retriever
from utils.logger import get_logger

logger = get_logger("hackt.services.sockets")

class IntegrationManager:
    def __init__(self):
        self.ide_server = None
        self.browser_server = None
        # NEW: Store the active IDE connection so we can push data to it
        self.active_ide_socket = None 
        # NEW: Keep track of the file currently open in the IDE
        self.current_ide_context = {"file_path": "", "content": ""}

    async def _ide_handler(self, websocket):
        """Bidirectional IDE Handler"""
        logger.info("IDE Client Connected to Port 8081.")
        self.active_ide_socket = websocket
        
        try:
            async for message in websocket:
                payload = json.loads(message)
                
                # Keep our internal state synced with the IDE
                if payload.get("type") == "context_update":
                    self.current_ide_context["file_path"] = payload.get("file_path")
                    self.current_ide_context["content"] = payload.get("content")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("IDE Client Disconnected.")
        finally:
            self.active_ide_socket = None

    async def push_code_edit(self, file_path: str, new_code: str):
        """Called by the LLM when a fix is ready to be injected."""
        if not self.active_ide_socket:
            logger.warning("Cannot push edit: IDE is not connected to Port 8081.")
            return False
            
        payload = {
            "action": "apply_fix",
            "file_path": file_path,
            "new_code": new_code
        }
        
        try:
            await self.active_ide_socket.send(json.dumps(payload))
            logger.info(f"Pushed code fix to IDE for {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to push IDE edit: {e}")
            return False

    async def start_ide_socket(self, port: int):
        if self.ide_server:
            return
        self.ide_server = await websockets.serve(self._ide_handler, "127.0.0.1", port)
        logger.info(f"IDE Listener ONLINE on ws://127.0.0.1:{port}")

    async def stop_ide_socket(self):
        if self.ide_server:
            self.ide_server.close()
            await self.ide_server.wait_closed()
            self.ide_server = None
            logger.info("IDE Listener OFFLINE.")

    # ---------------------------------------------------------
    # 2. BROWSER LISTENER (Port 8082)
    # ---------------------------------------------------------
    async def _browser_handler(self, websocket):
        """Receives DOM updates and URLs from the Chrome Extension."""
        logger.info("Browser Extension Connected.")
        try:
            async for message in websocket:
                payload = json.loads(message)
                url = payload.get("url", "")
                dom_text = payload.get("text", "")
                
                # Fast Filter (Stage 1) - Checks for phishing patterns, exposed eval(), etc.
                if len(dom_text) > 20:
                    is_threat = retriever.fast_scan(dom_text)
                    if is_threat:
                        logger.warning(f"Browser Threat detected on: {url}")
                        # Trigger Tauri event to flash Bubble Yellow/Red
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info("Browser Extension Disconnected.")

    async def start_browser_socket(self, port: int):
        if self.browser_server:
            return
        self.browser_server = await websockets.serve(self._browser_handler, "127.0.0.1", port)
        logger.info(f"Browser Proxy ONLINE on ws://127.0.0.1:{port}")

    async def stop_browser_socket(self):
        if self.browser_server:
            self.browser_server.close()
            await self.browser_server.wait_closed()
            self.browser_server = None
            logger.info("Browser Proxy OFFLINE.")

integration_manager = IntegrationManager()