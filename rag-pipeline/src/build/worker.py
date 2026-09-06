#!/usr/bin/env python3
"""
worker.py – Core Ingestion Worker for V21.0-Lite
=================================================
Uses compiled my-languages.so for AST parsing and import extraction.
"""

import sys
sys.setrecursionlimit(5000) # CRITICAL: Protects spawned workers from deep PDF recursion

import os
import json
import torch
import lancedb
import pandas as pd
import fcntl
import gc
import psutil
import pynvml
import hashlib
import numpy as np
import time
from pathlib import Path
from config import CONFIG, logger
from chunker import SemanticChunker
from sentence_transformers import SentenceTransformer

# ==============================================================================
# Tree-Sitter Imports (Pre-built bindings – no my-languages.so needed)
# ==============================================================================
def set_parser_language(parser, lang):
    """Set the parser's language, compatible with tree-sitter 0.21.x and >=0.22."""
    if hasattr(parser, 'set_language'):
        parser.set_language(lang)
    else:
        parser.language = lang

# ==============================================================================
# Tree-Sitter Imports (using compiled library)
# ==============================================================================
try:
    from tree_sitter import Language, Parser
    TS_AVAILABLE = True
except ImportError:
    TS_AVAILABLE = False
    logger.warning("Tree-sitter not installed; import extraction limited to regex.")

if TS_AVAILABLE:
    lib_path = CONFIG["BASE_PATH"] / "build" / "my-languages.so"
    if not lib_path.exists():
        TS_AVAILABLE = False
        logger.warning(f"Grammar library not found at {lib_path}. Run build_grammars.py")
    else:
        PY_LANG = Language(str(lib_path), 'python')
        JS_LANG = Language(str(lib_path), 'javascript')
        JAVA_LANG = Language(str(lib_path), 'java')
        GO_LANG = Language(str(lib_path), 'go')
        CPP_LANG = Language(str(lib_path), 'cpp')
        RUST_LANG = Language(str(lib_path), 'rust')
        logger.info("Tree-sitter grammars loaded from my-languages.so")

# ==============================================================================
# FILE_CACHE Loading (Critical for Graph Edge Validation)
# ==============================================================================
FILE_CACHE = set()
cache_path = os.environ.get("FILE_CACHE_PATH")
if cache_path and Path(cache_path).exists():
    with open(cache_path, 'r') as f:
        FILE_CACHE = set(json.load(f))
    logger.info(f"FILE_CACHE loaded with {len(FILE_CACHE)} entries from {cache_path}")
else:
    logger.warning("FILE_CACHE not found – graph edges may have orphans")

# ==============================================================================
# SUMMARY Loading (Critical for PDF Injection)
# ==============================================================================
PDF_SUMMARIES = {}
summary_path = Path(CONFIG.get("SUMMARIES_FILE", "summaries.json"))
if summary_path.exists():
    try:
        with open(summary_path, 'r') as f:
            PDF_SUMMARIES = json.load(f)
        logger.info(f"Loaded {len(PDF_SUMMARIES)} PDF summaries for injection.")
    except Exception as e:
        logger.warning(f"Failed to load PDF summaries: {e}")
else:
    logger.info("No summaries.json found. Proceeding without summary injection.")

# ==============================================================================
# Vault ID → Score Mapping
# ==============================================================================
VAULT_ID_TO_SCORE = {}
for vault_name, meta in CONFIG["VAULT_MAPPING"].items():
    VAULT_ID_TO_SCORE[meta["id"]] = meta["score"]

# ==============================================================================
# NVML Initialisation (once per worker process)
# ==============================================================================
try:
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
    NVML_HANDLE = pynvml.nvmlDeviceGetHandleByIndex(0)
except Exception as e:
    logger.warning(f"NVML init failed (VRAM monitoring disabled): {e}")
    NVML_AVAILABLE = False

# ==============================================================================
# Model Cache (Per Worker Process – Loaded ONCE Per Batch)
# ==============================================================================
_model = None

def get_embedding_model():
    global _model
    if _model is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Loading embedding model on {device}")
        _model = SentenceTransformer(
            CONFIG["EMBEDDING_MODEL"],
            trust_remote_code=True,
            device=device,
            cache_folder=str(CONFIG["BASE_PATH"] / "models")
        )
        logger.info(f"Embedding model loaded (will truncate to {CONFIG['EMBEDDING_TRUNCATE']} dims)")
    return _model

def check_resources():
    ram_gb = psutil.Process().memory_info().rss / 1024**3
    vram_gb = 0
    if NVML_AVAILABLE:
        try:
            info = pynvml.nvmlDeviceGetMemoryInfo(NVML_HANDLE)
            vram_gb = info.used / 1024**3
        except Exception as e:
            logger.warning(f"VRAM read failed: {e}")
    if ram_gb > CONFIG["RAM_LIMIT_GB"] or vram_gb > CONFIG["VRAM_LIMIT_GB"]:
        logger.warning(f"Resource limit exceeded: RAM={ram_gb:.2f}GB, VRAM={vram_gb:.2f}GB")
        return False
    return True

# ==============================================================================
# Language-Specific Import Extractors (All 6 Languages)
# ==============================================================================
def extract_imports_python(file_path):
    imports = []
    try:
        if TS_AVAILABLE:
            with open(file_path, 'rb') as f:
                code = f.read()
            parser = Parser()
            set_parser_language(parser, PY_LANG)
            tree = parser.parse(code)
            root = tree.root_node
            def collect(node):
                if node.type in ['import_statement', 'import_from_statement']:
                    for child in node.children:
                        if child.type == 'dotted_name':
                            imports.append(code[child.start_byte:child.end_byte].decode('utf-8').split('.')[0])
                for child in node.children:
                    collect(child)
            collect(root)
        else:
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('import '):
                        parts = line[7:].split(',')
                        for part in parts:
                            mod = part.strip().split()[0].split('.')[0]
                            if mod:
                                imports.append(mod)
                    elif line.startswith('from '):
                        parts = line[5:].split(' import ')
                        if len(parts) == 2:
                            mod = parts[0].strip().split('.')[0]
                            if mod:
                                imports.append(mod)
    except Exception as e:
        logger.warning(f"Python import extraction failed for {file_path}: {e}")
    return list(set(imports))

def extract_imports_javascript(file_path):
    imports = []
    try:
        if TS_AVAILABLE:
            with open(file_path, 'rb') as f:
                code = f.read()
            parser = Parser()
            set_parser_language(parser, JS_LANG)
            tree = parser.parse(code)
            root = tree.root_node
            query = JS_LANG.query("""
            (import_statement
              (import_clause (identifier) @import))
            """)
            for node, _ in query.captures(root):
                imports.append(code[node.start_byte:node.end_byte].decode('utf-8'))
        else:
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    if 'import' in line:
                        import re
                        m = re.search(r'from\s+[\'"]([^\'"]+)[\'"]', line)
                        if m:
                            imports.append(m.group(1))
    except Exception as e:
        logger.warning(f"JavaScript import extraction failed: {e}")
    return imports

def extract_imports_java(file_path):
    imports = []
    try:
        if TS_AVAILABLE:
            with open(file_path, 'rb') as f:
                code = f.read()
            parser = Parser()
            set_parser_language(parser, JAVA_LANG)
            tree = parser.parse(code)
            root = tree.root_node
            query = JAVA_LANG.query("(import_declaration (scoped_identifier) @import)")
            for node, _ in query.captures(root):
                imports.append(code[node.start_byte:node.end_byte].decode('utf-8'))
    except Exception as e:
        logger.warning(f"Java import extraction failed: {e}")
    return imports

def extract_imports_go(file_path):
    imports = []
    try:
        if TS_AVAILABLE:
            with open(file_path, 'rb') as f:
                code = f.read()
            parser = Parser()
            set_parser_language(parser, GO_LANG)
            tree = parser.parse(code)
            root = tree.root_node
            query = GO_LANG.query("""
            (import_declaration
              (import_spec path: (interpreted_string_literal) @import))
            """)
            for node, _ in query.captures(root):
                imports.append(code[node.start_byte:node.end_byte].decode('utf-8').strip('"'))
        else:
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    if line.strip().startswith('import '):
                        import re
                        m = re.search(r'import\s+(\S+)', line)
                        if m:
                            imports.append(m.group(1).strip('"'))
    except Exception as e:
        logger.warning(f"Go import extraction failed: {e}")
    return imports

def extract_imports_rust(file_path):
    imports = []
    try:
        if TS_AVAILABLE:
            with open(file_path, 'rb') as f:
                code = f.read()
            parser = Parser()
            set_parser_language(parser, RUST_LANG)
            tree = parser.parse(code)
            root = tree.root_node
            query = RUST_LANG.query("""
            (use_declaration (use_list (use) @import))
            """)
            for node, _ in query.captures(root):
                imports.append(code[node.start_byte:node.end_byte].decode('utf-8'))
        else:
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    if line.strip().startswith('use '):
                        parts = line.strip()[4:].split('::')
                        imports.append(parts[0])
    except Exception as e:
        logger.warning(f"Rust import extraction failed: {e}")
    return imports

def extract_imports_cpp(file_path):
    imports = []
    try:
        if TS_AVAILABLE:
            with open(file_path, 'rb') as f:
                code = f.read()
            parser = Parser()
            set_parser_language(parser, CPP_LANG)
            tree = parser.parse(code)
            root = tree.root_node
            query = CPP_LANG.query("""
            (preproc_include path: (string_literal) @import)
            """)
            for node, _ in query.captures(root):
                imports.append(code[node.start_byte:node.end_byte].decode('utf-8').strip('"<>'))
        else:
            with open(file_path, 'r', errors='ignore') as f:
                for line in f:
                    if line.strip().startswith('#include'):
                        import re
                        m = re.search(r'#include\s+[<"]([^>"]+)[>"]', line)
                        if m:
                            imports.append(m.group(1))
    except Exception as e:
        logger.warning(f"C++ import extraction failed: {e}")
    return imports

IMPORT_EXTRACTORS = {
    '.py': extract_imports_python,
    '.js': extract_imports_javascript,
    '.java': extract_imports_java,
    '.go': extract_imports_go,
    '.rs': extract_imports_rust,
    '.cpp': extract_imports_cpp,
    '.c': extract_imports_cpp,
}

def extract_imports(file_path):
    ext = Path(file_path).suffix.lower()
    func = IMPORT_EXTRACTORS.get(ext, lambda x: [])
    return func(file_path)

def validate_import(import_name, source_ext, file_cache):
    ext_map = {
        '.py': '.py',
        '.js': '.js',
        '.java': '.java',
        '.go': '.go',
        '.rs': '.rs',
        '.cpp': ['.cpp', '.c', '.h', '.hpp'],
        '.c': ['.cpp', '.c', '.h', '.hpp'],
    }
    target_exts = ext_map.get(source_ext, ['.py'])
    if isinstance(target_exts, str):
        target_exts = [target_exts]
    for f in file_cache:
        f_path = Path(f)
        f_stem = f_path.stem
        f_suffix = f_path.suffix
        if f_stem == import_name and f_suffix in target_exts:
            return True
    return False

# ==============================================================================
# Core Processing Function for a Single File
# ==============================================================================
def process_one_file(task, model, chunker):
    vault_id = task['vault_id']
    file_path = task['path']
    file_type = task['type']
    logger.info(f"  -> {file_path}")

    if not check_resources():
        return {"status": "skip", "reason": "resource_limit", "file": file_path}

    try:
        chunks = []
        
        # === SUMMARY INJECTION + FULL PDF PARSING ===
        if file_type == 'PDF':
            # 1. Grab the LLM Summary and inject it as Chunk 0 (The "Title Card")
            pre_summary = PDF_SUMMARIES.get(str(file_path))
            if pre_summary:
                chunks.append({
                    'text': f"DOCUMENT SUMMARY: {pre_summary}",
                    'raw_text': pre_summary,
                    'source': str(file_path),
                    'type': 'PDF_SUMMARY',
                    'page': 1
                })
                logger.info(f"    + Injected LLM Summary for {Path(file_path).name}")
            
            # 2. Chunk the ACTUAL full PDF content so the RAG can read it
            pdf_chunks = chunker.chunk_pdf(file_path, vault_id)
            if pdf_chunks:
                chunks.extend(pdf_chunks)
        else:
            # Normal code chunking
            chunks = chunker.chunk_code(file_path, vault_id)
            
        if not chunks:
            return {"status": "skip", "reason": "no_chunks", "file": file_path}

        texts = [c['text'] for c in chunks]
        embeddings = []
        for i in range(0, len(texts), CONFIG["EMBEDDING_BATCH_SIZE"]):
            batch = texts[i:i + CONFIG["EMBEDDING_BATCH_SIZE"]]
            emb = model.encode(batch, convert_to_numpy=True)
            emb = emb[:, :CONFIG["EMBEDDING_TRUNCATE"]]
            if CONFIG["EMBEDDING_QUANTIZE"] == "int8":
                emb = np.round(emb * 127).astype('int8')
            embeddings.extend(emb)
            torch.cuda.empty_cache()

        db = lancedb.connect(str(CONFIG["INDEX_PATH"]))
        data = []
        chunk_id = None
        authority_score = VAULT_ID_TO_SCORE.get(vault_id, 1.0)

        for i, chunk in enumerate(chunks):
            raw_text = chunk.get('raw_text', chunk['text'])
            chunk_id = hashlib.sha256(f"{file_path}:{raw_text[:1000]}".encode()).hexdigest()
            data.append({
                "id": chunk_id,
                "vector": embeddings[i].tolist(),
                "text": chunk['text'],
                "raw_text": raw_text,
                "vault_id": vault_id,
                "source": chunk['source'],
                "type": chunk['type'],
                "authority_score": authority_score,
                "page": chunk.get('page'),
            })

        tbl_name = "vault_chunks"
        if tbl_name not in db.table_names():
            import pyarrow as pa
            vector_dtype = pa.int8() if CONFIG["EMBEDDING_QUANTIZE"] == "int8" else pa.float32()
            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(vector_dtype, CONFIG["EMBEDDING_TRUNCATE"])),
                pa.field("text", pa.string()),
                pa.field("raw_text", pa.string()),
                pa.field("vault_id", pa.int32()),
                pa.field("source", pa.string()),
                pa.field("type", pa.string()),
                pa.field("authority_score", pa.float32()),
                pa.field("page", pa.int32()),
            ])
            db.create_table(tbl_name, data, schema=schema)
        else:
            db.open_table(tbl_name).add(data)

        if file_type == 'CODE':
            imports = extract_imports(file_path)
            src_name = str(Path(file_path).relative_to(CONFIG["RAW_PATH"]))
            source_ext = Path(file_path).suffix.lower()
            valid_edges = []
            for imp in imports:
                if validate_import(imp, source_ext, FILE_CACHE):
                    valid_edges.append({
                        "src": src_name,
                        "dst": imp,
                        "relation": "IMPORTS",
                        "vault_id": vault_id
                    })
            if valid_edges:
                edge_path = CONFIG["INTERMEDIATE_PATH"] / "graph_edges.csv"
                lock_path = str(edge_path) + ".lock"
                with open(lock_path, 'w') as lock_file:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    try:
                        header = not edge_path.exists()
                        pd.DataFrame(valid_edges).to_csv(edge_path, mode='a', header=header, index=False)
                    finally:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                try:
                    os.unlink(lock_path)
                except:
                    pass

        del embeddings, data
        torch.cuda.empty_cache()
        gc.collect()
        return {"status": "success", "file": file_path, "chunk_id": chunk_id}

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return {"status": "error", "file": file_path, "error": str(e)}

# ==============================================================================
# Batch Entry Point
# ==============================================================================
def process_batch(batch_tasks):
    model = get_embedding_model()
    chunker = SemanticChunker()
    results = []
    batch_start = time.time()
    for task in batch_tasks:
        if time.time() - batch_start > CONFIG["BATCH_TIMEOUT"]:
            logger.error(f"Batch timeout after {CONFIG['BATCH_TIMEOUT']}s at file {task['path']}")
            results.append({"status": "error", "file": task['path'], "error": "batch_timeout"})
            break
        results.append(process_one_file(task, model, chunker))
    return results