"""
HackT Sovereign Core - RAG Prompt Formulation
=============================================
Structures the prompt for the SovereignEngine to ensure it grounds
its answers in the retrieved Knowledge Vault context and avoids hallucination.
"""

def build_rag_prompt(query: str, project_context: str, retrieved_chunks: str) -> str:
    """
    Constructs the final prompt injected into Qwen 3.5.
    
    Args:
        query: The user's actual question.
        project_context: Active IDE/Browser state (e.g., current file name).
        retrieved_chunks: The formatted string from HybridRetriever in core/rag.py.
        
    Returns:
        A ChatML formatted string ready for core/engine.py
    """
    
    # 1. Strict System Constraints to prevent hallucination
    system_instruction = (
        "You are HackT, a sovereign cybersecurity AI agent. "
        "You must answer the user's query strictly based on the provided Knowledge Vault Context. "
        "If the context does not contain the answer, state clearly that you do not have that information in your vault, but provide your best analytical assessment based on the code context. "
        "Always cite your sources using the exact [Source: X] format provided in the vault context."
    )
    
    # 2. Format into ChatML (The specific token structure Qwen expects)
    prompt = f"""<|system|>
{system_instruction}

=== ACTIVE PROJECT CONTEXT ===
{project_context if project_context else "No active files or monitors detected."}

=== KNOWLEDGE VAULT CONTEXT ===
{retrieved_chunks if retrieved_chunks else "No relevant knowledge retrieved from vaults."}
<|end|>
<|user|>
{query}
<|end|>
<|assistant|>
"""
    return prompt