import trafilatura
import re
import logging

logger = logging.getLogger("hackt.utils.preprocessor")

class ContentProcessor:
    def __init__(self):
        # Regex to strip excessive whitespace and common noise patterns
        self.noise_pattern = re.compile(r'\n\s*\n')

    def clean_web_content(self, html_content: str) -> str:
        """Extracts core text/code from HTML, discarding boilerplate."""
        try:
            # Trafilatura is optimized for speed and high-precision extraction
            extracted = trafilatura.extract(
                html_content, 
                include_comments=False,
                include_tables=True,
                no_fallback=False
            )
            if not extracted:
                return ""
            
            # Remove excessive newlines for better LLM token efficiency
            cleaned = self.noise_pattern.sub('\n', extracted)
            return cleaned.strip()
        except Exception as e:
            logger.error(f"Preprocessing failed: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> list:
        """Splits text into overlapping chunks for the Vector Engine."""
        words = text.split()
        if not words:
            return []
            
        chunks = []
        # Overlap ensures context isn't lost at the boundary of a chunk
        for i in range(0, len(words), chunk_size - overlap):
            chunks.append(" ".join(words[i:i + chunk_size]))
            
        return chunks

processor = ContentProcessor()