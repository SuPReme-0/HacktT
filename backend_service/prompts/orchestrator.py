"""
HackT Sovereign Core - Prompt Orchestrator (v3.0)
=================================================
Dynamic ChatML Prompt Router featuring:
- Strict ChatML Formatting (Anti-Hallucination)
- Dynamic Token Budgeting
- Vault-Aware Intent Classification (Routes queries to specific RAG Vaults)
- Diff Bridge Support (Requests original_code + suggested_fix)
"""

import re
from typing import Dict, List, Optional, Any
from utils.logger import get_logger
from utils.config import config

logger = get_logger("hackt.prompts.orchestrator")

# ==============================================================================
# Base ChatML Templates
# ==============================================================================

BASE_SYSTEM_PROMPT = """<|im_start|>system
You are HackT, a Sovereign Cybersecurity AI operating locally on the user's hardware.
Your primary directive is to secure the user's digital perimeter, analyze code for vulnerabilities, and provide actionable intelligence.
Rules:
1. Be concise, direct, and highly technical.
2. Ground your answers strictly in the provided Knowledge Vault context. If the context does not answer the question, state that you do not know. Do not hallucinate external facts.
3. If providing code fixes, output ONLY the corrected code block. Do not wrap it in excessive explanations unless asked.
4. Maintain a professional, 'JARVIS-like' tone. Do not use emojis or overly enthusiastic language.
<|im_end|>
"""

RAG_CONTEXT_TEMPLATE = """
--- KNOWLEDGE VAULT CONTEXT ---
{vault_data}
-------------------------------
"""

SYSTEM_STATE_TEMPLATE = """
--- ACTIVE SYSTEM STATE ---
{state_data}
---------------------------
"""

# ==============================================================================
# Specialized Task Templates
# ==============================================================================

# 🚨 UPGRADED: Now requests original_code for React Diff Bridge
AUDIT_TEMPLATE = """<|im_start|>user
{system_state}

{rag_context}

Analyze the provided Active System State for security threats. 
You must output your analysis STRICTLY in the following JSON format. Do not output any other text or markdown before or after the JSON.

{{
  "threat_level": "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "explanation": "A concise, 1-2 sentence explanation of the threat or confirming safety.",
  "original_code": "The exact vulnerable code snippet (for diff display)",
  "suggested_fix": "The EXACT corrected code block to replace the vulnerable code",
  "diff_start_line": "The line number where the fix should be applied"
}}
<|im_end|>
<|im_start|>assistant
"""

# Used by the Idle Manager (Background Voice Reports)
IDLE_BARK_TEMPLATE = """<|im_start|>user
{system_state}

Generate a brief (1-2 sentences max), professional status update suitable for text-to-speech. 
Do not ask questions. If heavy compute is active (CPU/VRAM high), report it. If the system is idle, provide a standard secure perimeter update.
<|im_end|>
<|im_start|>assistant
"""

# Standard Interactive Chat
CHAT_TEMPLATE = """<|im_start|>user
{system_state}

{rag_context}

{query}
<|im_end|>
<|im_start|>assistant
"""


class PromptOrchestrator:
    """
    Central hub for compiling prompts, managing token budgets, and classifying intent.
    """
    
    def __init__(self):
        # Intent classification keywords for Vault Routing
        self.library_keywords = re.compile(r'\b(iso|nist|mitre|cve|owasp|standard|define|what is|documentation|policy)\b', re.IGNORECASE)
        self.laboratory_keywords = re.compile(r'\b(exploit|payload|fix|debug|vulnerability|xss|sqli|buffer overflow|bypass|script)\b', re.IGNORECASE)

    def classify_vault_intent(self, query: str) -> Optional[str]:
        """
        Lightweight heuristic to route the query to the correct RAG Vault.
        Matches the `target_vault` parameters expected by `rag.py`.
        """
        if not query:
            return None
            
        is_library = bool(self.library_keywords.search(query))
        is_laboratory = bool(self.laboratory_keywords.search(query))
        
        if is_library and not is_laboratory:
            return "library"
        elif is_laboratory and not is_library:
            return "laboratory"
        else:
            return None # Ambiguous or covers both, so search everything

    def compile_rag_context(self, retrieved_chunks: List[Dict]) -> str:
        """Formats raw RAG chunks into a cohesive context block."""
        if not retrieved_chunks:
            return ""
            
        context_str = ""
        for i, chunk in enumerate(retrieved_chunks):
            text = chunk.get("text", "")
            if text:
               context_str += f"[{i+1}] {text}\n\n"
               
        if not context_str:
            return ""
            
        return RAG_CONTEXT_TEMPLATE.format(vault_data=context_str.strip())

    def compile_system_state(self, system_state: Optional[Dict[str, Any]]) -> str:
        """Formats active IDE/Browser/Hardware state into a context block."""
        if not system_state:
            return ""
            
        state_str = ""
        for key, value in system_state.items():
             state_str += f"{key}: {value}\n"
             
        return SYSTEM_STATE_TEMPLATE.format(state_data=state_str.strip())

    def route(self, query: str, mode: str = "active", query_type: str = "chat", 
              retrieved_chunks: Optional[List[Dict]] = None, 
              system_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Master Prompt Compiler.
        Constructs the final ChatML payload based on the requested task type.
        """
        rag_str = self.compile_rag_context(retrieved_chunks or [])
        state_str = self.compile_system_state(system_state)
        
        # 1. STRICT JSON AUDIT (Threat Scanner / Browser Proxy)
        if query_type == "audit":
            prompt = BASE_SYSTEM_PROMPT + AUDIT_TEMPLATE.format(
                system_state=state_str,
                rag_context=rag_str
            )
            return {"prompt": prompt, "max_tokens": 768} # More tokens for diff data
            
        # 2. AMBIENT VOICE REPORT (Idle Manager)
        elif query_type == "idle":
            prompt = BASE_SYSTEM_PROMPT + IDLE_BARK_TEMPLATE.format(
                system_state=state_str
            )
            return {"prompt": prompt, "max_tokens": 64}
            
        # 3. FAST VOICE COMMAND (Low Latency)
        elif query_type == "voice":
            voice_system = "<|im_start|>system\nYou are HackT. Answer concisely.\n<|im_end|>\n"
            prompt = voice_system + CHAT_TEMPLATE.format(
                system_state="",
                rag_context=rag_str,
                query=query
            )
            return {"prompt": prompt, "max_tokens": 150}
            
        # 4. STANDARD INTERACTIVE CHAT (Default)
        else:
            prompt = BASE_SYSTEM_PROMPT + CHAT_TEMPLATE.format(
                system_state=state_str,
                rag_context=rag_str,
                query=query
            )
            return {"prompt": prompt, "max_tokens": 1024}

# Singleton Instance
orchestrator = PromptOrchestrator()