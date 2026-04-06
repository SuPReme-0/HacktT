"""
HackT Sovereign Core - Port Listener Service Module
====================================================
Provides WebSocket servers for real-time IDE and Browser integration:
- Port 8081: IDE integration (VS Code / JetBrains extension)
- Port 8082: Browser proxy (Chrome extension for phishing detection)

Features:
- Bidirectional communication with extensions
- Real-time code context streaming
- Secure fix injection via OS-level automation
- Threat detection from browser DOM analysis
"""

import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol, WebSocketServer
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger("hackt.services.port_listeners")


class IntegrationManager:
    """
    Manages WebSocket connections for IDE and Browser extensions.
    
    Features:
    - IDE listener on port 8081: Code context, fix injection
    - Browser listener on port 8082: DOM analysis, phishing detection
    - Secure code injection via WebSockets
    - Real-time context streaming to React via telemetry_manager
    """
    
    def __init__(self):
        # IDE integration state
        self.ide_server: Optional[WebSocketServer] = None
        self.active_ide_socket: Optional[WebSocketServerProtocol] = None
        self.current_ide_context: Dict = {"file_path": "", "content": "", "language": ""}
        
        # Browser integration state
        self.browser_server: Optional[WebSocketServer] = None
        self.active_browser_socket: Optional[WebSocketServerProtocol] = None
        self.current_browser_context: Dict = {"url": "", "dom_text": "", "threats": []}
        
        # Injection state (Prevents race conditions if multiple fixes are pushed simultaneously)
        self._injection_lock = asyncio.Lock()
        
    # ======================================================================
    # IDE Integration (Port 8081)
    # ======================================================================
    
    async def _ide_handler(self, websocket: WebSocketServerProtocol):
        """Bidirectional handler for IDE extension connection"""
        if self.active_ide_socket is not None:
            logger.warning("Multiple IDE connections detected. Overwriting active socket focus.")
            
        logger.info("IDE Client Connected to Port 8081.")
        self.active_ide_socket = websocket
        
        try:
            async for message in websocket:
                try:
                    payload = json.loads(message)
                    
                    # Handle context updates from IDE
                    if payload.get("type") == "context_update":
                        self.current_ide_context.update({
                            "file_path": payload.get("file_path", ""),
                            "content": payload.get("content", ""),
                            "language": payload.get("language", ""),
                            "cursor_line": payload.get("cursor_line", 0),
                            "selection": payload.get("selection", "")
                        })
                        
                        # LOCAL IMPORT: Forward context to React via telemetry
                        from services.websocket import telemetry_manager
                        await telemetry_manager.send_context_update({
                            "type": "ide",
                            "file": self.current_ide_context["file_path"],
                            "language": self.current_ide_context["language"],
                            "line": self.current_ide_context["cursor_line"]
                        })
                    
                    # Handle fix application confirmation
                    elif payload.get("type") == "fix_applied":
                        logger.info(f"Fix applied successfully to {payload.get('file_path')}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from IDE: {message[:100]}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("IDE Client Disconnected.")
        finally:
            # Only clear if this was the currently active socket
            if self.active_ide_socket == websocket:
                self.active_ide_socket = None
    
    async def push_code_edit(self, file_path: str, new_code: str) -> bool:
        """
        Push AI-generated fix to connected IDE via WebSocket.
        
        Args:
            file_path: Target file path in IDE
            new_code: Complete replacement code or diff
            
        Returns:
            True if successfully sent, False if no IDE connected
        """
        if not self.active_ide_socket:
            logger.warning("Cannot push edit: IDE is not connected to Port 8081.")
            return False
        
        payload = {
            "action": "apply_fix",
            "file_path": file_path,
            "new_code": new_code,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # FIXED: Wrap in lock to prevent payload corruption from rapid concurrent requests
        async with self._injection_lock:
            try:
                await self.active_ide_socket.send(json.dumps(payload))
                logger.info(f"Pushed code fix to IDE for {file_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to push IDE edit: {e}")
                return False
    
    async def start_ide_socket(self, port: int = 8081):
        """Start IDE WebSocket server"""
        if self.ide_server:
            return
        
        self.ide_server = await websockets.serve(
            self._ide_handler,
            "127.0.0.1",
            port,
            ping_interval=30,
            ping_timeout=10
        )
        logger.info(f"IDE Listener ONLINE on ws://127.0.0.1:{port}")
    
    async def stop_ide_socket(self):
        """Stop IDE WebSocket server"""
        if self.ide_server:
            self.ide_server.close()
            await self.ide_server.wait_closed()
            self.ide_server = None
            logger.info("IDE Listener OFFLINE.")
    
    # ======================================================================
    # Browser Integration (Port 8082)
    # ======================================================================
    
    async def _browser_handler(self, websocket: WebSocketServerProtocol):
        """Handler for Browser extension connection (phishing detection)"""
        logger.info("Browser Extension Connected to Port 8082.")
        self.active_browser_socket = websocket
        
        try:
            async for message in websocket:
                try:
                    payload = json.loads(message)
                    url = payload.get("url", "")
                    dom_text = payload.get("text", "")
                    
                    # Update browser context
                    self.current_browser_context.update({
                        "url": url,
                        "dom_text": dom_text,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    
                    # Fast threat filter (Stage 1)
                    if len(dom_text) > 20:
                        # LOCAL IMPORT: Pull active retriever from main, NOT core.rag
                        from main import retriever
                        
                        if retriever:
                            is_threat = retriever.fast_scan(dom_text)
                            
                            if is_threat:
                                logger.warning(f"Browser Threat detected on: {url}")
                                
                                # Alert React via telemetry
                                from services.websocket import telemetry_manager
                                await telemetry_manager.send_threat_alert(
                                    threat_level="MEDIUM",
                                    source=f"browser:{url}"
                                )
                                
                                # Trigger deeper analysis in background
                                asyncio.create_task(self._deep_browser_analysis(url, dom_text))
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from Browser: {message[:100]}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Browser Extension Disconnected.")
        finally:
            if self.active_browser_socket == websocket:
                self.active_browser_socket = None
    
    async def _deep_browser_analysis(self, url: str, dom_text: str):
        """Run deeper threat analysis on suspicious page"""
        # LOCAL IMPORTS
        from main import engine
        
        if not engine:
            return

        try:
            from prompts.threat_prompt import THREAT_ASSESSMENT_PROMPT
            prompt = THREAT_ASSESSMENT_PROMPT.format(
                input_text=f"URL: {url}\n\nPage Content:\n{dom_text[:1500]}",
                context="No additional context for browser scan."
            )
        except ImportError:
            # Fallback if prompts module is not yet built
            prompt = f"Analyze this website for phishing or malicious scripts. URL: {url}\nContent: {dom_text[:1500]}"
        
        try:
            result = engine.generate(prompt, max_tokens=256, temperature=0.0)
            # In a full implementation, we would parse this JSON and escalate to CRITICAL if needed
            logger.info(f"Deep browser analysis completed for {url}. Result: {result[:100]}...")
        except Exception as e:
            logger.error(f"Deep browser analysis failed: {e}")
    
    async def start_browser_socket(self, port: int = 8082):
        """Start Browser WebSocket server"""
        if self.browser_server:
            return
        
        self.browser_server = await websockets.serve(
            self._browser_handler,
            "127.0.0.1",
            port,
            ping_interval=30,
            ping_timeout=10
        )
        logger.info(f"Browser Proxy ONLINE on ws://127.0.0.1:{port}")
    
    async def stop_browser_socket(self):
        """Stop Browser WebSocket server"""
        if self.browser_server:
            self.browser_server.close()
            await self.browser_server.wait_closed()
            self.browser_server = None
            logger.info("Browser Proxy OFFLINE.")


# Singleton instance
integration_manager = IntegrationManager()