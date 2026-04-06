"""
HackT Sovereign Core - Content Preprocessor Module
===================================================
Provides content extraction and chunking for RAG:
- Web content cleaning via trafilatura
- Syntax-preserving code chunking with overlap
- Noise pattern filtering
- Token-efficient formatting
"""

import re
import logging
from typing import List, Optional

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    trafilatura = None

logger = logging.getLogger("hackt.utils.preprocessor")


class ContentProcessor:
    """
    Content extraction and preprocessing for RAG ingestion.
    
    Features:
    - HTML to clean text extraction
    - Code block preservation
    - Noise pattern removal
    - Line-aware chunking for code (preserves indentation)
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_length: int = 20,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length
        
        # Regex patterns for noise removal
        self.noise_patterns = [
            re.compile(r'\n\s*\n'),  # Excessive newlines
            re.compile(r'', re.DOTALL),  # HTML comments
            re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE),  # Scripts
            re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE),  # Styles
        ]
        
        # Code block preservation pattern
        self.code_pattern = re.compile(r'(```[\s\S]*?```|`[^`]+`)', re.DOTALL)
    
    def clean_web_content(self, html_content: str, preserve_code: bool = True) -> str:
        """Extract clean text from HTML content."""
        if not TRAFILATURA_AVAILABLE:
            return self._basic_cleanup(html_content, preserve_code)
        
        try:
            extracted = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                include_images=False,
                no_fallback=False,
                favor_precision=True,
            )
            
            if not extracted:
                return self._basic_cleanup(html_content, preserve_code)
            
            if preserve_code:
                extracted = self._preserve_code_blocks(extracted)
            
            cleaned = extracted
            for pattern in self.noise_patterns:
                cleaned = pattern.sub('\n', cleaned)
            
            return cleaned.strip()
            
        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            return self._basic_cleanup(html_content, preserve_code)
    
    def _basic_cleanup(self, text: str, preserve_code: bool = True) -> str:
        """Fallback cleanup when trafilatura is unavailable."""
        if preserve_code:
            text = self._preserve_code_blocks(text)
            
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
        
        for pattern in self.noise_patterns:
            text = pattern.sub('\n', text)
            
        return text.strip()
    
    def _preserve_code_blocks(self, text: str) -> str:
        """Protect code blocks from aggressive cleanup."""
        placeholders = {}
        counter = [0]
        
        def replace_code(match):
            placeholder = f"__CODE_BLOCK_{counter[0]}__"
            placeholders[placeholder] = match.group(0)
            counter[0] += 1
            return placeholder
        
        protected = self.code_pattern.sub(replace_code, text)
        
        for pattern in self.noise_patterns:
            protected = pattern.sub('\n', protected)
        
        # Restore code blocks
        for placeholder, code in placeholders.items():
            protected = protected.replace(placeholder, code)
        
        return protected
    
    def chunk_text(
        self,
        text: str,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
        is_code: bool = True,  # Default True to protect IDE files
    ) -> List[str]:
        """
        Split text into overlapping chunks for vector indexing.
        
        Args:
            text: Input text to chunk
            chunk_size: Override default chunk size (in words approx)
            overlap: Override default overlap
            is_code: If True, uses line-aware chunking to preserve indentation
        """
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.chunk_overlap
        
        if not text.strip():
            return []
        
        if is_code:
            return self._chunk_code_by_lines(text, chunk_size, overlap)
        else:
            return self._chunk_by_words(text, chunk_size, overlap)
            
    def _chunk_code_by_lines(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Chunk code strictly by lines to preserve indentation and syntax structure.
        """
        lines = text.splitlines(keepends=True)
        chunks = []
        current_chunk = []
        current_words = 0
        
        for line in lines:
            line_words = len(line.split())
            
            # If adding this line exceeds the chunk size, finalize the current chunk
            if current_words + line_words > chunk_size and current_chunk:
                chunks.append("".join(current_chunk))
                
                # Calculate overlap: keep the last N lines that roughly equal the overlap limit
                overlap_chunk = []
                overlap_words = 0
                for prev_line in reversed(current_chunk):
                    if overlap_words >= overlap:
                        break
                    overlap_chunk.insert(0, prev_line)
                    overlap_words += len(prev_line.split())
                    
                current_chunk = overlap_chunk
                current_words = overlap_words
                
            current_chunk.append(line)
            current_words += line_words
            
        if current_chunk:
            chunks.append("".join(current_chunk))
            
        return chunks
    
    def _chunk_by_words(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Standard sliding window for normal paragraphs (destroys newlines)."""
        words = text.split()
        if len(words) <= chunk_size:
            return [text] if len(words) >= self.min_chunk_length else []
        
        chunks = []
        step = chunk_size - overlap
        
        for i in range(0, len(words), step):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) >= self.min_chunk_length:
                chunks.append(" ".join(chunk_words))
        
        return chunks
    
    def format_for_llm(self, content: str, source: Optional[str] = None) -> str:
        """Format content for LLM context injection."""
        parts = []
        if source:
            parts.append(f"Source: {source}")
            
        if len(content) > 2000:
            parts.append(f"{content[:1000]}\n...[truncated]...\n{content[-1000:]}")
        else:
            parts.append(content)
            
        return "\n".join(parts)


# Singleton instance
processor = ContentProcessor()