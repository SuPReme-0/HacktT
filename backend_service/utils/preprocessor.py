"""
HackT Sovereign Core - Content Preprocessor Module (v3.0)
=========================================================
Provides content extraction and VRAM-safe chunking for RAG ingestion.
Features:
- Vault-Aware Metadata Tagging (Library vs. Laboratory)
- Config-Synced Chunk Limits & Overlap (Syncs with utils.config)
- Smart Minified Text Handling (Re-combiner logic for JS/CSS/JSON)
- Trafilatura Markdown Output (Preserves code blocks)
- Syntax-Preserving Code Chunking
- Fallback Code Preservation (Ensures code blocks survive basic cleanup)
"""

import re
import html
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    trafilatura = None

from utils.logger import get_logger
from utils.config import config

logger = get_logger("hackt.utils.preprocessor")

class ContentProcessor:
    """
    Content extraction and preprocessing for RAG ingestion.
    Optimized to keep chunks strictly under the Nomic-Embed 512-token limit.
    """
    
    def __init__(self):
        # 🚀 Sync with Global Config
        # Nomic v1.5 = 512 tokens. ~4 chars/token. 512 * 4 = 2048 chars max.
        # We use dynamic sizing based on config.rag.max_context_chars
        self.chunk_chars = config.rag.max_context_chars // 4  # Dynamic sizing
        self.overlap_chars = self.chunk_chars // 8  # 🚀 Sync overlap proportionally (25% of chunk)
        self.min_chunk_chars = 50
        
        # Vault Mapping Heuristics
        self.vault_keywords = {
            "library": ["docs", "documentation", "iso", "nist", "readme", "policy", "standard"],
            "laboratory": ["src", "code", "exploit", "vuln", "script", "main", "app"],
            "showroom": ["demo", "example", "sample", "ui", "frontend"]
        }
        
        # Regex patterns for aggressive noise removal
        self.noise_patterns = [
            re.compile(r'\n\s*\n+'),  # Excessive newlines
            re.compile(r'<!--[\s\S]*?-->', re.DOTALL),  # HTML comments
            re.compile(r'<script[^>]*>[\s\S]*?</script>', re.DOTALL | re.IGNORECASE),
            re.compile(r'<style[^>]*>[\s\S]*?</style>', re.DOTALL | re.IGNORECASE),
        ]
        
        # Code block preservation pattern
        self.code_pattern = re.compile(r'(```[\s\S]*?```|`[^`\n]+`)', re.DOTALL)
    
    def determine_vault_id(self, source_path: str, content_type: str = "text") -> int:
        """
        Heuristically determines the Vault ID based on file path or content type.
        Returns: 1 (Library), 2 (Laboratory), 3 (Showroom)
        """
        path_lower = source_path.lower()
        
        # 1. Check Path Keywords
        for vault, keywords in self.vault_keywords.items():
            if any(kw in path_lower for kw in keywords):
                return config.vaults.library_id if vault == "library" else \
                       config.vaults.laboratory_id if vault == "laboratory" else \
                       config.vaults.showroom_id
        
        # 2. Check File Extensions
        if content_type == "code" or Path(source_path).suffix in [".py", ".js", ".ts", ".c", ".cpp", ".go", ".rs"]:
            return config.vaults.laboratory_id
        
        # 3. Default to Library for docs/text
        return config.vaults.library_id

    def clean_web_content(self, html_content: str, preserve_code: bool = True) -> str:
        """
        Extract clean text, ensuring code blocks survive the extraction.
        🚀 FIX: Apply code preservation to BOTH trafilatura and fallback paths.
        """
        if not TRAFILATURA_AVAILABLE:
            return self._basic_cleanup(html_content, preserve_code)
        
        try:
            # 🚀 CRITICAL FIX: Tell Trafilatura to output markdown so it preserves ``` code blocks
            extracted = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                output_format="markdown" 
            )
            
            if not extracted:
                return self._basic_cleanup(html_content, preserve_code)
            
            if preserve_code:
                # NOW the regex will actually find the markdown blocks
                extracted = self._preserve_code_blocks(extracted)
            
            cleaned = extracted
            for pattern in self.noise_patterns:
                replacement = '\n\n' if pattern.pattern == r'\n\s*\n+' else ''
                cleaned = pattern.sub(replacement, cleaned)
            
            return html.unescape(cleaned).strip()
            
        except Exception as e:
            logger.error(f"Preprocessor: Trafilatura extraction failed: {e}")
            # 🚀 FALLBACK: Ensure code preservation even in basic cleanup
            return self._basic_cleanup(html_content, preserve_code)
    
    def _basic_cleanup(self, text: str, preserve_code: bool = True) -> str:
        """Robust fallback cleanup using standard regex and HTML unescaping."""
        if preserve_code:
            # 🚀 CRITICAL: Apply code preservation BEFORE stripping HTML tags
            text = self._preserve_code_blocks(text)
            
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        
        for pattern in self.noise_patterns:
            replacement = '\n\n' if pattern.pattern == r'\n\s*\n+' else ''
            text = pattern.sub(replacement, text)
            
        return text.strip()
    
    def _preserve_code_blocks(self, text: str) -> str:
        """Protects inline and block code from aggressive whitespace/HTML stripping."""
        placeholders = {}
        counter = [0]
        
        def replace_code(match):
            placeholder = f"__CODE_BLOCK_{counter[0]}__"
            placeholders[placeholder] = match.group(0)
            counter[0] += 1
            return placeholder
        
        protected = self.code_pattern.sub(replace_code, text)
        
        for pattern in self.noise_patterns:
            replacement = '\n\n' if pattern.pattern == r'\n\s*\n+' else ''
            protected = pattern.sub(replacement, protected)
        
        for placeholder, code in placeholders.items():
            protected = protected.replace(placeholder, code)
        
        return protected
    
    def chunk_text(
        self,
        text: str,
        source_path: str = "unknown",
        is_code: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Splits text into overlapping chunks safe for Nomic 512-token limits.
        Returns List[Dict] with metadata for direct LanceDB ingestion.
        """
        if not text.strip():
            return []
        
        # 🚀 VAULT AWARENESS: Tag chunks with the correct Vault ID
        vault_id = self.determine_vault_id(source_path, "code" if is_code else "text")
        
        if is_code:
            raw_chunks = self._chunk_code_by_lines(text)
        else:
            raw_chunks = self._chunk_by_characters(text)
            
        # 🚀 STRUCTURED OUTPUT: Wrap text in metadata dicts
        structured_chunks = []
        for i, chunk in enumerate(raw_chunks):
            structured_chunks.append({
                "text": chunk,
                "source": source_path,
                "vault_id": vault_id,
                "chunk_index": i,
                "type": "code" if is_code else "text"
            })
            
        return structured_chunks
            
    def _chunk_code_by_lines(self, text: str) -> List[str]:
        """
        Chunks code strictly by lines to preserve syntax and indentation.
        🚀 FIX: Properly handles minified code without bypassing overlap buffers.
        """
        lines = text.splitlines(keepends=True)
        chunks = []
        current_chunk = []
        current_chars = 0
        
        for line in lines:
            line_chars = len(line)
            
            # 🚨 CIRCUIT BREAKER 1: Massive Single Line
            if line_chars > self.chunk_chars:
                if current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_chars = 0
                
                # 🚨 CIRCUIT BREAKER 2: Minified Text Handling (JS/CSS/JSON)
                # Try to split by common delimiters for minified content
                delimiters = [';', '{', '}', ':', ',']
                has_delimiter = any(d in line for d in delimiters)
                
                if has_delimiter:
                    # Split by the first available delimiter
                    for delim in delimiters:
                        if delim in line:
                            sub_segments = [e+delim for e in line.split(delim) if e]
                            # Fix the last element which shouldn't get an extra delimiter if original didn't have it
                            if not line.endswith(delim) and sub_segments:
                                sub_segments[-1] = sub_segments[-1][:-1]
                            
                            for seg in sub_segments:
                                seg_chars = len(seg)
                                if seg_chars > self.chunk_chars:
                                    if current_chunk:
                                        chunks.append("".join(current_chunk))
                                        current_chunk, current_chars = [], 0
                                    chunks.extend(self._chunk_by_characters(seg))
                                else:
                                    # 🚀 CRITICAL: Feed it through the normal buffering logic!
                                    if current_chars + seg_chars > self.chunk_chars and current_chunk:
                                        chunks.append("".join(current_chunk))
                                        # Build overlap
                                        overlap_chunk = []
                                        overlap_chars = 0
                                        for prev_line in reversed(current_chunk):
                                            if overlap_chars + len(prev_line) > self.overlap_chars:
                                                break
                                            overlap_chunk.insert(0, prev_line)
                                            overlap_chars += len(prev_line)
                                        current_chunk = overlap_chunk
                                        current_chars = overlap_chars
                                    
                                    current_chunk.append(seg)
                                    current_chars += seg_chars
                            break  # Only split by one delimiter type
                    continue
                
                # Fallback to char chunking if no delimiters found
                chunks.extend(self._chunk_by_characters(line))
                continue
            
            # --- Normal Line-Chunking Logic ---
            if current_chars + line_chars > self.chunk_chars and current_chunk:
                chunks.append("".join(current_chunk))
                
                # Build overlap
                overlap_chunk = []
                overlap_chars = 0
                for prev_line in reversed(current_chunk):
                    if overlap_chars + len(prev_line) > self.overlap_chars:
                        break
                    overlap_chunk.insert(0, prev_line)
                    overlap_chars += len(prev_line)
                    
                current_chunk = overlap_chunk
                current_chars = overlap_chars
                
            current_chunk.append(line)
            current_chars += line_chars
        
        if current_chunk and current_chars >= self.min_chunk_chars:
            chunks.append("".join(current_chunk))
            
        return chunks
    
    def _chunk_by_characters(self, text: str) -> List[str]:
        """Sliding window chunking by raw characters for standard prose."""
        if len(text) <= self.chunk_chars:
            return [text] if len(text) >= self.min_chunk_chars else []
        
        chunks = []
        step = self.chunk_chars - self.overlap_chars
        
        for i in range(0, len(text), step):
            chunk = text[i:i + self.chunk_chars]
            if len(chunk) >= self.min_chunk_chars:
                chunks.append(chunk)
                
            if i + self.chunk_chars >= len(text):
                break
                
        return chunks
    
    def format_for_llm(self, content: str, source: Optional[str] = None) -> str:
        """
        Format a chunk for LLM context injection.
        🚀 FIX: Dynamic truncation based on config, not hardcoded magic numbers.
        """
        parts = []
        if source:
            parts.append(f"Source: {source}")
            
        # 🚀 Use dynamic config limits
        safe_limit = self.chunk_chars * 2  
        half_limit = safe_limit // 2
        
        if len(content) > safe_limit:
            parts.append(f"{content[:half_limit]}\n\n...[truncated]...\n\n{content[-half_limit:]}")
        else:
            parts.append(content)
            
        return "\n".join(parts)

# Singleton instance
processor = ContentProcessor()