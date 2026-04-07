"""
HackT Sovereign Core - Port Listener Service Module (v4.0)
==========================================================
Provides WebSocket servers for real-time IDE, Terminal, and Browser integration:
- Port 8081: IDE & Terminal integration (VS Code / JetBrains / CLI)
- Port 8082: Browser proxy (Phishing/DOM threat detection)

Features:
- Non-blocking Async hardware offloading (asyncio.to_thread)
- Terminal payload tracking for live hack attempts
- Secure fix injection via locked WebSocket communication
- Direct integration with the ChatML Prompt Orchestrator
- Content truncation security (prevents memory OOM)
"""

import asyncio
import json
import websockets
from websockets.server import WebSocketServerProtocol, WebSocketServer
from typing import Dict, Optional
from utils.logger import get_logger
from utils.config import config

# Core imports (NO circular main.py imports!)
from core.engine import engine
from core.rag import retriever
from prompts.orchestrator import orchestrator

# Lazy imports to prevent boot-time circular dependencies
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

logger = get_logger("hackt.services.port_listeners")


class IntegrationManager:
    """
    Manages WebSocket connections for external extensions.
    Engineered to handle high-frequency IDE/Terminal pings without freezing the backend.
    """
    
    def __init__(self):
        # IDE / Terminal Integration State
        self.ide_server: Optional[WebSocketServer] = None
        self.active_ide_socket: Optional[WebSocketServerProtocol] = None
        self.current_ide_context: Dict = {
            "file_path": "",
            "content": "",
            "language": "",
            "terminal_log": "",  # 🚨 Added for live hack attempt tracking
            "cursor_line": 0,
            "selection": ""
        }
        
        # Browser Integration State
        self.browser_server: Optional[WebSocketServer] = None
        self.active_browser_socket: Optional[WebSocketServerProtocol] = None
        self.current_browser_context: Dict = {
            "url": "",
            "dom_text": "",
            "timestamp": 0.0
        }
        
        # Injection Mutex: Prevents payload corruption if UI and Audio trigger simultaneous edits
        self._injection_lock = asyncio.Lock()
        
        # Content Security Limits
        self.max_content_chars = 10000  # Prevent memory ballooning from massive files
        self.max_dom_chars = 5000       # Prevent OOM from massive webpages
        self.max_terminal_chars = 5000  # Terminal output buffer limit

    # ======================================================================
    # IDE & TERMINAL Integration (Port 8081)
    # ======================================================================
    
    async def _ide_handler(self, websocket: WebSocketServerProtocol):
        """Bidirectional handler for IDE/CLI connection"""
        if self.active_ide_socket is not None:
            logger.warning("Port 8081: Overwriting active socket focus with new connection.")
        
        logger.info("Port 8081: IDE/Terminal Client ONLINE.")
        self.active_ide_socket = websocket
        
        try:
            async for message in websocket:
                try:
                    payload = json.loads(message)
                    
                    # 1. Update Active Workspace Context
                    if payload.get("type") == "context_update":
                        self.current_ide_context.update({
                            "file_path": payload.get("file_path", ""),
                            # 🚨 SECURITY: Truncate content to prevent memory ballooning
                            "content": payload.get("content", "")[:self.max_content_chars],
                            "language": payload.get("language", ""),
                            "cursor_line": payload.get("cursor_line", 0),
                            "selection": payload.get("selection", ""),
                            # 🚨 NEW: Capture terminal output for live hack detection
                            "terminal_log": payload.get("terminal_log", "")[:self.max_terminal_chars]
                        })
                        
                        # Forward UI telemetry to React Dashboard
                        if telemetry_manager:
                            await telemetry_manager.send_context_update({
                                "type": "ide",
                                "file": self.current_ide_context["file_path"],
                                "language": self.current_ide_context["language"],
                                "line": self.current_ide_context["cursor_line"],
                                "has_terminal": bool(self.current_ide_context["terminal_log"])
                            })
                    
                    # 2. Acknowledge Fix Completion (From React Diff UI)
                    elif payload.get("type") == "fix_applied":
                        logger.info(f"Port 8081: Fix successfully applied to {payload.get('file_path')}")
                    
                    # 3. Handle Manual Scan Request
                    elif payload.get("type") == "scan_request":
                        logger.info(f"Port 8081: Manual scan requested for {payload.get('file_path')}")
                        # Could trigger threat_scanner.scan_now() here
                        
                except json.JSONDecodeError:
                    logger.debug("Port 8081: Received non-JSON payload. Ignoring.")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Port 8081: IDE/Terminal Client OFFLINE.")
        finally:
            if self.active_ide_socket == websocket:
                self.active_ide_socket = None
    
    async def push_code_edit(self, file_path: str, new_code: str, 
                             original_code: str = "") -> bool:
        """
        Pushes AI-generated fixes directly into the active IDE.
        🚀 DIFF BRIDGE: Sends both original and suggested code for React UI rendering.
        
        Args:
            file_path: Target file path in IDE
            new_code: Suggested fix code
            original_code: Original vulnerable code (for Diff UI)
            
        Returns:
            True if successfully sent, False if no IDE connected
        """
        if not self.active_ide_socket:
            logger.warning("Port 8081: Cannot push edit. IDE is disconnected.")
            return False
        
        payload = {
            "action": "apply_fix",
            "file_path": file_path,
            "new_code": new_code,
            "original_code": original_code,  # 🚀 For React Diff UI
            "timestamp": asyncio.get_event_loop().time()
        }
        
        async with self._injection_lock:
            try:
                await self.active_ide_socket.send(json.dumps(payload))
                logger.info(f"Port 8081: Pushed payload to IDE ({len(new_code)} chars).")
                return True
            except Exception as e:
                logger.error(f"Port 8081: Failed to push edit: {e}")
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
        """Handler for Browser extension connection (phishing/DOM tracking)"""
        logger.info("Port 8082: Browser Extension ONLINE.")
        self.active_browser_socket = websocket
        
        try:
            async for message in websocket:
                try:
                    payload = json.loads(message)
                    url = payload.get("url", "")
                    # 🚨 SECURITY: Cap DOM text to prevent massive memory OOMs
                    dom_text = payload.get("text", "")[:self.max_dom_chars]
                    
                    self.current_browser_context.update({
                        "url": url,
                        "dom_text": dom_text,
                        "timestamp": asyncio.get_event_loop().time()
                    })
                    
                    # 🚀 FAST FILTER (Offloaded to prevent UI freezing)
                    if len(dom_text) > 20 and retriever:
                        # 🚨 ASYNC OFFLOAD: Don't block WebSocket on CPU string matching
                        is_threat = await asyncio.to_thread(retriever.fast_scan, dom_text)
                        
                        if is_threat:
                            logger.warning(f"Port 8082: Suspicious DOM syntax detected on: {url}")
                            
                            if telemetry_manager:
                                await telemetry_manager.send_threat_alert(
                                    threat_level="MEDIUM",
                                    source=f"browser:{url}",
                                    description="Suspicious DOM content detected"
                                )
                            
                            # Fire Deep Analysis in background (non-blocking)
                            asyncio.create_task(self._deep_browser_analysis(url, dom_text))
                            
                except json.JSONDecodeError:
                    pass
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("Port 8082: Browser Extension OFFLINE.")
        finally:
            if self.active_browser_socket == websocket:
                self.active_browser_socket = None
    
    async def _deep_browser_analysis(self, url: str, dom_text: str):
        """
        Deep threat analysis using the centralized PromptOrchestrator.
        🚨 ASYNC OFFLOAD: PyTorch inference must not block the WebSocket!
        """
        if not engine:
            return
        
        try:
            # 🚀 Use the Orchestrator to guarantee ChatML formatting and Stop Tokens!
            system_state = {
                "Target URL": url,
                "DOM Snippet": dom_text[:1500]
            }
            
            route_data = orchestrator.route(
                query="Analyze this website DOM for phishing, credential harvesting, or malicious script injection.",
                mode="passive",
                query_type="audit",  # Triggers the strict JSON CODE_AUDIT template
                system_state=system_state
            )
            
            # 🚨 OFFLOAD TO THREAD: PyTorch inference must not block the WebSocket!
            result = await asyncio.to_thread(
                engine.generate,
                route_data["prompt"],
                max_tokens=route_data["max_tokens"],
                temperature=0.0  # Zero entropy for strict security JSON outputs
            )
            
            logger.info(f"Port 8082: Deep browser analysis complete for {url}. Output: {result[:100]}...")
            
            # Parse and forward threat assessment to React via telemetry
            try:
                from services.threat_scanner import threat_scanner
                clean_result = threat_scanner._clean_json_response(result)
                assessment = json.loads(clean_result)
                
                if assessment.get("threat_level") in ["HIGH", "CRITICAL"]:
                    if telemetry_manager:
                        await telemetry_manager.send_threat_alert(
                            threat_level=assessment["threat_level"],
                            source=f"browser:{url}",
                            description=assessment.get("explanation", "Deep threat analysis completed")
                        )
            except Exception as e:
                logger.debug(f"Port 8082: Failed to parse threat assessment: {e}")
                
        except Exception as e:
            logger.error(f"Port 8082: Deep browser analysis failed: {e}")
    
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

    # ======================================================================
    # Utility Methods
    # ======================================================================
    
    def get_ide_context(self) -> Dict:
        """Get current IDE context snapshot (for threat scanner)"""
        return self.current_ide_context.copy()
    
    def get_browser_context(self) -> Dict:
        """Get current browser context snapshot (for threat scanner)"""
        return self.current_browser_context.copy()
    
    def clear_terminal_log(self):
        """Clear terminal buffer after analysis (prevents memory bloat)"""
        self.current_ide_context["terminal_log"] = ""


# Singleton Instance
integration_manager = IntegrationManager()