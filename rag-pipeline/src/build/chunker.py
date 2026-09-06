#!/usr/bin/env python3
"""
chunker.py – Semantic Chunking for V21.0-Lite
==============================================
Uses compiled my-languages.so for AST-based chunking.
Features a Dual-Metric PyPDF RAM-Shield to prevent Docling from crashing on massive PDFs.
"""

import sys
sys.setrecursionlimit(5000) # CRITICAL: Protects PyPDF from deep bookmark trees

import os
import re
import json
from pathlib import Path
from config import CONFIG, logger

def set_parser_language(parser, lang):
    """Set the parser's language, compatible with tree-sitter 0.21.x and >=0.22."""
    if hasattr(parser, 'set_language'):
        parser.set_language(lang)
    else:
        parser.language = lang

try:
    from tree_sitter import Language, Parser
    from docling.document_converter import DocumentConverter
    LIBS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Optional libraries not installed: {e}")
    LIBS_AVAILABLE = False

# ==============================================================================
# Token-Aware Chunk Splitter
# ==============================================================================
def split_by_token_limit(text, max_tokens=CONFIG["MAX_CHUNK_TOKENS"]):
    if not text or not text.strip():
        return []
    token_count = len(text) // CONFIG["TOKENS_PER_CHAR_ESTIMATE"]
    if token_count <= max_tokens:
        return [text]
    sentences = re.split(r'(?<=[.!?])\s+|\n', text)
    chunks = []
    current = []
    current_len = 0
    for sent in sentences:
        sent_len = len(sent) // CONFIG["TOKENS_PER_CHAR_ESTIMATE"]
        if current_len + sent_len <= max_tokens:
            current.append(sent)
            current_len += sent_len
        else:
            if current:
                chunks.append(' '.join(current))
            if sent_len > max_tokens:
                words = sent.split()
                sub_chunk = []
                sub_len = 0
                for word in words:
                    word_len = len(word) // CONFIG["TOKENS_PER_CHAR_ESTIMATE"]
                    if sub_len + word_len <= max_tokens:
                        sub_chunk.append(word)
                        sub_len += word_len
                    else:
                        if sub_chunk:
                            chunks.append(' '.join(sub_chunk))
                        sub_chunk = [word]
                        sub_len = word_len
                if sub_chunk:
                    chunks.append(' '.join(sub_chunk))
            else:
                current = [sent]
                current_len = sent_len
    if current:
        chunks.append(' '.join(current))
    return chunks

# ==============================================================================
# Main Chunker Class
# ==============================================================================
class SemanticChunker:
    def __init__(self):
        self.parser = None
        self.languages = {}
        self.doc_converter = None

        if LIBS_AVAILABLE:
            self.parser = Parser()
            self.doc_converter = DocumentConverter()

            # Load compiled grammar library
            lib_path = CONFIG["BASE_PATH"] / "build" / "my-languages.so"
            if lib_path.exists():
                try:
                    self.languages['.py'] = Language(str(lib_path), 'python')
                    self.languages['.js'] = Language(str(lib_path), 'javascript')
                    self.languages['.java'] = Language(str(lib_path), 'java')
                    self.languages['.go'] = Language(str(lib_path), 'go')
                    self.languages['.rs'] = Language(str(lib_path), 'rust')
                    self.languages['.cpp'] = Language(str(lib_path), 'cpp')
                    self.languages['.c'] = Language(str(lib_path), 'cpp')
                    logger.info("Tree-sitter grammars loaded from my-languages.so")
                except Exception as e:
                    logger.warning(f"Failed to load grammars: {e}")
                    self.languages = {}
            else:
                logger.warning(f"Grammar library not found at {lib_path}. Install with: python build_grammars.py")
                self.languages = {}
        else:
            self.doc_converter = None
            self.languages = {}

    def _get_language(self, file_path):
        ext = Path(file_path).suffix.lower()
        return self.languages.get(ext)

    def _enrich_chunk(self, chunk, vault_id):
        # We no longer paste the summary into every chunk to prevent vector poisoning.
        # worker.py handles injecting the summary as Chunk 0.
        chunk['raw_text'] = chunk['text']
        if 'page' not in chunk:
            chunk['page'] = None
        return chunk

    def _extract_code_chunks_ast(self, code, language, file_path):
        chunks = []
        try:
            set_parser_language(self.parser, language)
            tree = self.parser.parse(code)
            root = tree.root_node

            if language.name == 'python':
                query = language.query("""
                (function_definition name: (identifier) @name) @func
                (class_definition name: (identifier) @name) @class
                """)
            elif language.name == 'javascript':
                query = language.query("""
                (function_declaration name: (identifier) @name) @func
                (method_definition name: (property_identifier) @name) @method
                (class_declaration name: (identifier) @name) @class
                """)
            elif language.name == 'java':
                query = language.query("""
                (method_declaration name: (identifier) @name) @method
                (class_declaration name: (identifier) @name) @class
                """)
            elif language.name == 'go':
                query = language.query("""
                (function_declaration name: (identifier) @name) @func
                (method_declaration name: (identifier) @name) @method
                """)
            elif language.name == 'rust':
                query = language.query("""
                (function_item name: (identifier) @name) @func
                (impl_item body: (declaration_list (function_item name: (identifier) @name) @method))
                (struct_item name: (type_identifier) @name) @struct
                """)
            elif language.name == 'cpp':
                query = language.query("""
                (function_definition declarator: (function_declarator declarator: (identifier) @name)) @func
                (class_specifier name: (type_identifier) @name) @class
                """)
            else:
                return [code.decode('utf-8', errors='replace')]

            for capture, _ in query.captures(root):
                chunk_text = code[capture.start_byte:capture.end_byte].decode('utf-8', errors='replace')
                if len(chunk_text.strip()) > 50:
                    for sub in split_by_token_limit(chunk_text):
                        chunks.append({
                            "text": sub,
                            "type": "code",
                            "source": str(file_path),
                            "chunk_type": capture.type
                        })

            if not chunks:
                fallback = code.decode('utf-8', errors='replace')
                for sub in split_by_token_limit(fallback):
                    chunks.append({"text": sub, "type": "code", "source": str(file_path)})

        except Exception as e:
            logger.warning(f"AST extraction failed for {file_path}: {e}")
            fallback = code.decode('utf-8', errors='replace')
            for sub in split_by_token_limit(fallback):
                chunks.append({"text": sub, "type": "code", "source": str(file_path)})

        return chunks

    def chunk_code(self, file_path, vault_id):
        chunks = []
        try:
            with open(file_path, 'rb') as f:
                code = f.read()

            language = self._get_language(file_path)
            if LIBS_AVAILABLE and language is not None:
                ast_chunks = self._extract_code_chunks_ast(code, language, file_path)
                for chunk in ast_chunks:
                    chunk["vault_id"] = vault_id
                    chunks.append(self._enrich_chunk(chunk, vault_id))
            else:
                fallback = code.decode('utf-8', errors='replace')
                for sub in split_by_token_limit(fallback):
                    chunk = {"text": sub, "type": "code", "vault_id": vault_id, "source": str(file_path)}
                    chunks.append(self._enrich_chunk(chunk, vault_id))

        except Exception as e:
            logger.error(f"Error chunking {file_path}: {e}")
            try:
                fallback = open(file_path, 'r', errors='ignore').read()
                for sub in split_by_token_limit(fallback):
                    chunk = {"text": sub, "type": "code", "vault_id": vault_id, "source": str(file_path)}
                    chunks.append(self._enrich_chunk(chunk, vault_id))
            except:
                pass

        return chunks

    def chunk_pdf(self, file_path, vault_id):
        chunks = []
        if not LIBS_AVAILABLE or not self.doc_converter:
            logger.warning("Docling not available; cannot chunk PDFs.")
            return chunks

        try:
            # 🛡️ THE DUAL-METRIC RAM SHIELD: Check file size AND page count
            file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
            page_count = 0
            reader = None # Initialize to None so it doesn't crash if PyPDF fails
            
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(file_path))
                page_count = len(reader.pages)
            except Exception as e:
                logger.warning(f"Could not initialize PyPDF for {Path(file_path).name}: {e}")
                page_count = 100 # Assume it's big to trigger the shield and protect Docling
            
            # If the file is > 15MB OR > 50 pages, Docling will crash the system.
            if file_size_mb > 15.0 or page_count > 50:
                logger.info(f"🛡️ RAM SHIELD TRIGGERED: {Path(file_path).name} ({file_size_mb:.1f}MB, {page_count} pages). Bypassing Docling...")
                
                if reader is None:
                    logger.error(f"Cannot extract text from {Path(file_path).name}; it is corrupted or heavily encrypted.")
                    return chunks # Return whatever we have (like the LLM Summary) and move on

                try:
                    for page_num, page in enumerate(reader.pages, start=1):
                        text = page.extract_text()
                        if text and text.strip():
                            for sub in split_by_token_limit(text):
                                chunk = {
                                    "text": sub,
                                    "type": "pdf",
                                    "vault_id": vault_id,
                                    "source": str(file_path),
                                    "section": f"Page {page_num}",
                                    "page": page_num
                                }
                                chunks.append(self._enrich_chunk(chunk, vault_id))
                    return chunks
                except Exception as pypdf_err:
                    logger.error(f"PyPDF extraction failed: {pypdf_err}")
                    return chunks

            # --- Normal Docling parsing for safe, smaller PDFs ---
            result = self.doc_converter.convert(str(file_path))
            try:
                markdown = result.document.export_to_markdown()
            except AttributeError:
                try:
                    markdown = result.document.text
                except AttributeError:
                    markdown = str(result.document.export_to_dict())

            pages = getattr(result.document, 'pages', None)
            has_page_access = pages is not None and len(pages) > 0

            if has_page_access:
                for page_num, page in enumerate(pages, start=1):
                    try:
                        page_markdown = page.export_to_markdown()
                    except AttributeError:
                        page_markdown = markdown

                    current_section = "Intro"
                    current_text = []
                    for line in page_markdown.split('\n'):
                        if line.startswith('#'):
                            if current_text:
                                full_text = "\n".join(current_text)
                                for sub in split_by_token_limit(full_text):
                                    chunk = {
                                        "text": sub,
                                        "type": "pdf",
                                        "vault_id": vault_id,
                                        "source": str(file_path),
                                        "section": current_section,
                                        "page": page_num
                                    }
                                    chunks.append(self._enrich_chunk(chunk, vault_id))
                            current_section = line.strip()
                            current_text = []
                        else:
                            current_text.append(line)
                    if current_text:
                        full_text = "\n".join(current_text)
                        for sub in split_by_token_limit(full_text):
                            chunk = {
                                "text": sub,
                                "type": "pdf",
                                "vault_id": vault_id,
                                "source": str(file_path),
                                "section": current_section,
                                "page": page_num
                            }
                            chunks.append(self._enrich_chunk(chunk, vault_id))
            else:
                logger.warning(f"Page-level access not available for {file_path}")
                current_section = "Intro"
                current_text = []
                for line in markdown.split('\n'):
                    if line.startswith('#'):
                        if current_text:
                            full_text = "\n".join(current_text)
                            for sub in split_by_token_limit(full_text):
                                chunk = {
                                    "text": sub,
                                    "type": "pdf",
                                    "vault_id": vault_id,
                                    "source": str(file_path),
                                    "section": current_section,
                                    "page": None
                                }
                                chunks.append(self._enrich_chunk(chunk, vault_id))
                        current_section = line.strip()
                        current_text = []
                    else:
                        current_text.append(line)
                if current_text:
                    full_text = "\n".join(current_text)
                    for sub in split_by_token_limit(full_text):
                        chunk = {
                            "text": sub,
                            "type": "pdf",
                            "vault_id": vault_id,
                            "source": str(file_path),
                            "section": current_section,
                            "page": None
                        }
                        chunks.append(self._enrich_chunk(chunk, vault_id))

        except Exception as e:
            logger.error(f"PDF chunking failed for {file_path}: {e}")

        return chunks