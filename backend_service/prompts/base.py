"""
HackT Sovereign Core - Base Templates & Utilities (v2.0)
=========================================================
Formats prompts into strict ChatML to ensure Qwen 3.5 instruction adherence.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel

class PromptTemplate(BaseModel):
    template: str
    output_format: str = "text"  # "text" or "json"
    
    def format(self, **kwargs) -> str:
        return self.template.format(**kwargs)

def format_chatml(system: str, user: str, context: Optional[str] = None) -> str:
    """
    CRITICAL: Qwen 3.5 strictly requires <|im_start|> and <|im_end|> tokens.
    """
    prompt = f"<|im_start|>system\n{system}\n"
    
    if context:
        prompt += f"\n=== SYSTEM CONTEXT ===\n{context}\n"
        
    # 🚨 FIX: Added <|im_end|> after system block
    prompt += f"<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
    return prompt

def inject_context(
    project_context: Optional[str] = None,
    retrieved_chunks: Optional[List[Dict]] = None,
    system_state: Optional[Dict] = None
) -> str:
    """Safely builds the context injection block without wasting tokens."""
    sections = []
    
    if system_state:
        state_text = "\n".join([f"{k}: {v}" for k, v in system_state.items()])
        sections.append(f"[SYSTEM STATE]\n{state_text}")
        
    if project_context:
        sections.append(f"[ACTIVE PROJECT]\n{project_context}")
        
    if retrieved_chunks:
        chunks_text = "\n\n".join([
            f"Source [{i+1}]: {c.get('source', 'unknown')}\n{c.get('text', '')[:600]}"
            for i, c in enumerate(retrieved_chunks)
        ])
        sections.append(f"[KNOWLEDGE VAULT]\n{chunks_text}")
        
    return "\n\n".join(sections)