"""
HackT Sovereign Core - RAG Prompt Formatter
=============================================
"""

from typing import List, Dict, Optional
from .base import format_chatml, inject_context
from .code import CODE_ANALYSIS_SYSTEM, CODE_FIX_SYSTEM
from .speech import SPEECH_SYSTEM, SPEECH_IDLE

def build_final_prompt(
    query: str,
    prompt_type: str,
    project_context: Optional[str] = None,
    retrieved_chunks: Optional[List[Dict]] = None,
    system_state: Optional[Dict] = None
) -> dict:
    """
    Assembles the final ChatML string based on the requested type.
    Returns a dict containing the formatted string and max_tokens config.
    """
    # 1. Build the context block
    context_block = inject_context(project_context, retrieved_chunks, system_state)
    
    # 2. Select Template & Config
    if prompt_type == "code_audit":
        system_msg = CODE_ANALYSIS_SYSTEM.template
        max_tokens = 768
    elif prompt_type == "code_fix":
        system_msg = CODE_FIX_SYSTEM.template
        max_tokens = 512
    elif prompt_type == "speech_idle":
        system_msg = SPEECH_IDLE.template
        max_tokens = 128
    elif prompt_type == "speech":
        system_msg = SPEECH_SYSTEM.template
        max_tokens = 256
    else:
        # Default RAG Chat
        system_msg = "You are HackT, a sovereign cybersecurity AI. Answer the user based strictly on the provided context. Do not hallucinate."
        max_tokens = 512

    # 3. Format into Qwen ChatML
    final_prompt_string = format_chatml(
        system=system_msg,
        user=query,
        context=context_block
    )
    
    return {
        "prompt": final_prompt_string,
        "max_tokens": max_tokens
    }