"""
HackT Sovereign Core - Prompts Package
=======================================
Centralized prompt engineering and intent routing.
Ensures consistent ChatML formatting and Vault-aware routing across all services.
"""

# 1. The Master Orchestrator (Intent Classification & Routing)
from prompts.orchestrator import orchestrator

# 2. Output Schemas (Pydantic Models for Structured Generation)
from prompts.schemas import ThreatLevel, Vulnerability, CodeAnalysisOutput

# 3. Base Utilities (ChatML Formatting)
from prompts.base import format_chatml, inject_context

__all__ = [
    "orchestrator",
    "ThreatLevel",
    "Vulnerability",
    "CodeAnalysisOutput",
    "format_chatml",
    "inject_context",
]