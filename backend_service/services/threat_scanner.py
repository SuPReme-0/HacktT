"""
HackT Sovereign Core - Threat Scanner Service Module
=====================================================
Provides background threat detection for Passive Mode:
- Continuous monitoring of IDE/Browser contexts
- Hybrid RAG-based threat classification
- Real-time alerting via WebSocket to React
- VRAM-safe operation with model caching

Runs as async task alongside main event loop.
"""

import asyncio
import logging
import json
import re
from typing import Dict, List, Optional
from utils.logger import get_logger

logger = get_logger("hackt.services.threat_scanner")


class ThreatScanner:
    """
    Background threat detection engine for Passive Mode.
    
    Features:
    - Continuous monitoring of IDE/Browser context streams
    - Hybrid RAG retrieval for threat classification
    - Severity-based alerting (LOW/MEDIUM/HIGH/CRITICAL)
    - Citation generation for audit trail
    - VRAM-aware batching to avoid model reloads
    """
    
    def __init__(self, scan_interval: float = 10.0):
        """
        Initialize threat scanner.
        
        Args:
            scan_interval: Seconds between threat scans (default: 10.0)
        """
        self.scan_interval = scan_interval
        self.is_running = False
        self._scan_task: Optional[asyncio.Task] = None
        
        # Threat classification thresholds
        self.severity_thresholds = {
            "CRITICAL": 0.9,
            "HIGH": 0.7,
            "MEDIUM": 0.4,
            "LOW": 0.1
        }
        
    def start(self):
        """Start background threat scanning task"""
        if self.is_running:
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
        
    def _clean_json_response(self, text: str) -> str:
        """Strips markdown formatting from LLM JSON responses"""
        text = text.strip()
        # Remove ```json ... ``` blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        return text.strip()
    
    async def _scan_loop(self):
        """Main scanning loop: monitor → analyze → alert"""
        while self.is_running:
            try:
                # LOCAL IMPORT: Get current contexts from integration manager
                from services.port_listeners import integration_manager
                
                contexts = []
                
                # Check IDE context
                if integration_manager.current_ide_context.get("content"):
                    contexts.append({
                        "source": "ide",
                        "content": integration_manager.current_ide_context["content"],
                        "file": integration_manager.current_ide_context.get("file_path", "")
                    })
                
                # Check Browser context
                if integration_manager.current_browser_context.get("dom_text"):
                    contexts.append({
                        "source": "browser",
                        "content": integration_manager.current_browser_context["dom_text"],
                        "url": integration_manager.current_browser_context.get("url", "")
                    })
                
                # Analyze each context for threats
                for ctx in contexts:
                    await self._analyze_context(ctx)
                
                # Wait for next scan
                await asyncio.sleep(self.scan_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Threat scan loop error: {e}")
                await asyncio.sleep(5)  # Backoff on error
    
    async def _analyze_context(self, context: Dict):
        """Analyze a single context for security threats"""
        content = context.get("content", "")
        source = context.get("source", "unknown")
        
        if not content or len(content) < 20:
            return
        
        # LOCAL IMPORT: Pull active singletons from main
        from main import engine, embedder, retriever
        
        if not retriever or not embedder or not engine:
            return # System not fully booted yet

        # Stage 1: Fast keyword filter (CPU only, 0 VRAM cost)
        if retriever.fast_scan(content):
            # Stage 2: Deep RAG analysis
            
            if not embedder._loaded:
                embedder.load()
                
            query_vector = embedder.encode(f"security vulnerability in {source} code")
            
            # Retrieve relevant security knowledge
            retrieved = retriever.retrieve(
                query=f"Is this {source} content a security threat?",
                query_vector=query_vector,
                mode="passive"
            )
            
            # Classify threat using LLM
            from prompts.threat_prompt import THREAT_ASSESSMENT_PROMPT
            prompt = THREAT_ASSESSMENT_PROMPT.format(
                input_text=content[:1500],
                context=retrieved
            )
            
            try:
                # Temperature 0.0 for deterministic JSON output
                result = engine.generate(prompt, max_tokens=256, temperature=0.0)
                clean_result = self._clean_json_response(result)
                assessment = json.loads(clean_result)
                
                # Alert if threat detected
                if assessment.get("threat_level") in ["HIGH", "CRITICAL"]:
                    await self._send_alert(
                        threat_level=assessment["threat_level"],
                        source=f"{source}:{context.get('file') or context.get('url')}",
                        description=assessment.get("explanation", "Threat detected."),
                        citations=assessment.get("citations", [])
                    )
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM Threat Assessment JSON: {e} - Raw: {result}")
            except Exception as e:
                logger.error(f"Threat classification failed: {e}")
    
    async def _send_alert(self, threat_level: str, source: str, 
                         description: str, citations: List[str]):
        """Send threat alert to React via telemetry WebSocket"""
        from services.websocket import telemetry_manager
        
        # Telemetry Manager already formats the data payload correctly
        await telemetry_manager.send_threat_alert(
            threat_level=threat_level,
            source=source
        )
        
        logger.warning(f"Threat alert broadcasted: {threat_level} - {source}")
    
    async def scan_now(self, content: str, source: str = "manual") -> Dict:
        """
        Perform immediate threat scan (for manual triggers via HTTP endpoint).
        """
        if not content or len(content) < 20:
            return {"threat_level": "NONE", "confidence": 0.95}
        
        # LOCAL IMPORT
        from main import engine, embedder, retriever
        
        if not retriever or not embedder or not engine:
            return {"threat_level": "UNKNOWN", "confidence": 0.0, "error": "System not ready"}
        
        # Fast filter first
        if not retriever.fast_scan(content):
            return {"threat_level": "NONE", "confidence": 0.95}
        
        # Deep analysis
        if not embedder._loaded:
            embedder.load()
        query_vector = embedder.encode("security vulnerability assessment")
        
        retrieved = retriever.retrieve(
            query="security vulnerability",
            query_vector=query_vector,
            mode="passive"
        )
        
        from prompts.threat_prompt import THREAT_ASSESSMENT_PROMPT
        prompt = THREAT_ASSESSMENT_PROMPT.format(
            input_text=content[:1500],
            context=retrieved
        )
        
        result = engine.generate(prompt, max_tokens=256, temperature=0.0)
        
        try:
            clean_result = self._clean_json_response(result)
            return json.loads(clean_result)
        except Exception as e:
            logger.error(f"Manual scan JSON parse failed: {e}")
            return {
                "threat_level": "UNKNOWN",
                "confidence": 0.0,
                "error": "Failed to parse assessment"
            }

# Singleton instance
threat_scanner = ThreatScanner(scan_interval=10.0)