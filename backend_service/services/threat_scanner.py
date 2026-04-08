"""
HackT Sovereign Core - Threat Scanner Service Module (v7.1)
===========================================================
Provides background threat detection for Passive Mode:
- Dependency Injection Architecture (Prevents Circular Import Crashes)
- Content Hash Caching (Per-File, Skips unchanged content for CPU efficiency)
- Hybrid RAG-based threat classification (Vault-Aware via Orchestrator)
- Real-time Alerting via WebSocket (UI Diff Bridge Ready)
- VRAM-safe operation with Async Thread Offloading
- Terminal Log Monitoring (Live hack attempt detection)
"""
import asyncio
import json
import hashlib
from typing import Dict, List, Optional, Any
from utils.logger import get_logger
from utils.config import config
from prompts.orchestrator import orchestrator

# Lazy import for WebSocket to prevent boot-time circular dependencies
try:
    from services.websocket import telemetry_manager
except ImportError:
    telemetry_manager = None

logger = get_logger("hackt.services.threat_scanner")

class ThreatScanner:
    """
    Background threat detection engine for Passive Mode.
    Engineered to run silently without dropping UI framerates or blocking the Voice Engine.
    Uses Dependency Injection for core singletons to ensure PyInstaller safety.
    """
    def __init__(self, scan_interval: float = 10.0):
        self.scan_interval = scan_interval
        self.is_running = False
        self._scan_task: Optional[asyncio.Task] = None
        
        # 🚀 DEPENDENCY INJECTION PLACEHOLDERS
        self.engine = None
        self.embedder = None
        self.retriever = None
        
        # 🚀 OPTIMIZATION: Per-File Content Hash Caching
        self._last_scan_hashes: Dict[str, str] = {}
        self.max_context_chars = config.rag.max_context_chars // 2  # Sync with RAG config
        self.broadcast_callback = None  # For broadcasting alerts without direct WebSocket dependency

    def inject_dependencies(self, engine, embedder, retriever, broadcast_callback=None):
        """Cleanly inject singletons and the UI broadcast bridge."""
        self.engine = engine
        self.embedder = embedder
        self.retriever = retriever
        self.broadcast_callback = broadcast_callback
        logger.info("ThreatScanner: Dependencies & Broadcast Bridge injected.")

    def _get_content_hash(self, content: str) -> str:
        """Returns a SHA-256 hash to detect changes in context."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _extract_json_payload(self, text: str) -> str:
        """
        Surgically extracts JSON objects, ignoring LLM conversational filler.
        """
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return text[start:end+1]
        return text # Fallback in case of severe hallucination

    def start(self):
        """Start background threat scanning task"""
        if self.is_running:
            return
        if not all([self.engine, self.embedder, self.retriever]):
            logger.error("ThreatScanner: Cannot start. Missing core dependencies. Call inject_dependencies() first.")
            return
            
        self.is_running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        logger.info("Threat Scanner: ONLINE")

    def stop(self):
        """Stop background threat scanning"""
        self.is_running = False
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
        logger.info("Threat Scanner: OFFLINE")

    async def _scan_loop(self):
        """Main scanning loop: monitor → analyze → alert"""
        while self.is_running:
            try:
                # LOCAL IMPORT: Get current contexts from integration manager
                from services.port_listeners import integration_manager
                contexts = []
                
                # Check IDE context (including terminal logs)
                if integration_manager.current_ide_context.get("content"):
                    contexts.append({
                        "source": "ide",
                        "content": integration_manager.current_ide_context["content"],
                        "file": integration_manager.current_ide_context.get("file_path", ""),
                        "terminal_log": integration_manager.current_ide_context.get("terminal_log", "")
                    })
                
                # Check Browser context
                if integration_manager.current_browser_context.get("dom_text"):
                    contexts.append({
                        "source": "browser",
                        "content": integration_manager.current_browser_context["dom_text"],
                        "url": integration_manager.current_browser_context.get("url", "")
                    })

                # Analyze each context concurrently
                if contexts:
                    await asyncio.gather(*(self._analyze_context(ctx) for ctx in contexts))
                
                await asyncio.sleep(self.scan_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Threat Scanner: Loop error: {e}")
                await asyncio.sleep(5)  # Backoff on error

    async def _analyze_context(self, context: Dict):
        """Analyze a single context for security threats without blocking."""
        content = context.get("content", "")
        terminal_log = context.get("terminal_log", "")
        source = context.get("source", "unknown")
        
        # 🚀 PER-FILE IDENTIFIER
        file_identifier = context.get('file') or context.get('url') or source
        if not file_identifier:
            return

        if not content or len(content) < 20:
            return

        # 🚀 PACK CONTEXT PROPERLY (Fixes Bug 2)
        full_context = content
        if terminal_log:
            full_context = f"--- TERMINAL LOG ---\n{terminal_log}\n\n--- SOURCE CODE ---\n{content}"

        # 🚀 HASH CHECK: Skip if context hasn't changed
        c_hash = self._get_content_hash(full_context)
        if self._last_scan_hashes.get(file_identifier) == c_hash:
            return  # No changes since last scan

        if not self.retriever or not self.embedder or not self.engine:
            return

        # Stage 1: Fast keyword filter (CPU only, 0 VRAM cost)
        is_threat = await asyncio.to_thread(self.retriever.fast_scan, full_context)
        
        if is_threat:
            # Stage 2: Deep RAG analysis
            try:
                # 🚀 VAULT INTENT CLASSIFICATION
                target_vault = orchestrator.classify_vault_intent(f"security vulnerability in {source} code")
                
                # 🚀 ASYNC MATH OFFLOADING
                query_vector = await asyncio.to_thread(
                    self.embedder.encode,
                    f"security vulnerability in {source} code"
                )
                retrieved_chunks = await asyncio.to_thread(
                    self.retriever.retrieve,
                    query=f"Is this {source} content a security threat?",
                    query_vector=query_vector,
                    mode="passive",
                    query_type="audit",
                    target_vault=target_vault
                )
                
                # 🚀 ORCHESTRATOR INTEGRATION
                system_state = {
                    "Source": source,
                    "Target": file_identifier,
                    "Content Snippet": full_context[:self.max_context_chars]
                }
                route_data = orchestrator.route(
                    query="Evaluate the provided context for security threats. Output strict JSON.",
                    mode="passive",
                    query_type="audit",  # Guarantees strict JSON template
                    retrieved_chunks=retrieved_chunks,
                    system_state=system_state
                )
                
                # 🚀 ENGINE GENERATION
                result = await asyncio.to_thread(
                    self.engine.generate,
                    route_data["prompt"],
                    max_tokens=route_data["max_tokens"],
                    temperature=0.0,  # Deterministic
                    json_mode=True    # Enforce grammar if available
                )
                
                # Fixes Bug 1
                clean_result = self._extract_json_payload(result)
                assessment = json.loads(clean_result)
                
                # Alert if threat detected
                # Alert if threat detected
                if assessment.get("threat_level") in ["HIGH", "CRITICAL"]:
                    # ✅ FIXED: Use the unified internal _send_alert method
                    await self._send_alert(
                        threat_level=assessment["threat_level"],
                        source=file_identifier,
                        description=assessment.get("explanation", "Critical security vulnerability detected."),
                        original_code=content[:self.max_context_chars],
                        suggested_fix=assessment.get("suggested_fix", "")
                    )

                # Update hash only after successful processing
                self._last_scan_hashes[file_identifier] = c_hash
                
            except json.JSONDecodeError:
                logger.error(f"Threat Scanner: Failed to parse LLM JSON - Raw: {result[:100]}...")
            except Exception as e:
                logger.error(f"Threat Scanner: Classification failed: {e}")

    async def _send_alert(self, threat_level: str, source: str, description: str, 
                          original_code: str = "", suggested_fix: str = ""):
        """
        Send threat alert to React via telemetry WebSocket.
        Utilizes the injected broadcast_callback for code diffs.
        """
        # 1. Standard Telemetry Alert (For the sidebar/banner)
        if telemetry_manager:
            await telemetry_manager.send_threat_alert(
                threat_level=threat_level,
                source=source,
                description=description
            )
        
        # 2. 🚀 THE DIFF BRIDGE (For the Code Fix Modal)
        # Use the callback injected by main.py
        if self.broadcast_callback:
            await self.broadcast_callback(
                threat_level=threat_level,
                source=source,
                original_code=original_code,
                suggested_fix=suggested_fix
            )
        
        logger.warning(f"⚠️ THREAT DETECTED: {threat_level} in {source}")
        
    async def scan_now(self, content: str, source: str = "manual", 
                       file_identifier: str = "manual_scan") -> Dict:
        """
        Perform immediate threat scan (for manual triggers via HTTP endpoint).
        Returns full assessment INCLUDING original_code for UI Diff compatibility.
        """
        if not content or len(content) < 20:
            return {"threat_level": "NONE", "confidence": 0.95}
            
        if not self.retriever or not self.embedder or not self.engine:
            return {"threat_level": "UNKNOWN", "confidence": 0.0, "error": "System not ready"}
        
        is_threat = await asyncio.to_thread(self.retriever.fast_scan, content)
        if not is_threat:
            return {"threat_level": "NONE", "confidence": 0.95}
        
        try:
            target_vault = orchestrator.classify_vault_intent("security vulnerability assessment")
            query_vector = await asyncio.to_thread(self.embedder.encode, "security vulnerability assessment")
            
            retrieved_chunks = await asyncio.to_thread(
                self.retriever.retrieve,
                query="security vulnerability",
                query_vector=query_vector,
                mode="passive",
                query_type="audit",
                target_vault=target_vault
            )
            
            system_state = {"Source": source, "Content Snippet": content[:self.max_context_chars]}
            route_data = orchestrator.route(
                query="Evaluate this context for threats.",
                mode="passive",
                query_type="audit",
                retrieved_chunks=retrieved_chunks,
                system_state=system_state
            )
            
            result = await asyncio.to_thread(
                self.engine.generate,
                route_data["prompt"],
                max_tokens=256,
                temperature=0.0,
                json_mode=True
            )
            
            clean_result = self._extract_json_payload(result)
            assessment = json.loads(clean_result)
            
            assessment["original_code"] = content[:self.max_context_chars]
            assessment["file_identifier"] = file_identifier
            return assessment
            
        except Exception as e:
            logger.error(f"Manual scan JSON parse failed: {e}")
            return {
                "threat_level": "UNKNOWN",
                "confidence": 0.0,
                "error": "Failed to parse assessment"
            }

    def clear_hash_cache(self):
        """Clear the hash cache (useful when user switches projects)."""
        self._last_scan_hashes.clear()
        logger.info("ThreatScanner: Hash cache cleared.")

# Singleton instance
threat_scanner = ThreatScanner(scan_interval=config.modes.passive_scan_interval)