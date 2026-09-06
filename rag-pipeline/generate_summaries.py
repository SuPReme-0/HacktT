#!/usr/bin/env python3
"""
generate_summaries.py – Qwen 3.5 4B 4-Bit Quantized for RAG Summaries
======================================================================
FINAL PRODUCTION VERSION – Optimized for 8GB VRAM with Docling PDF extraction

Features:
- ONLY processes PDFs and code files inside a 'repos' folder.
- Pre-scan all files for accurate progress bar
- Docling for high-quality PDF extraction (models downloaded once)
- 10-Page strict PDF slicer to prevent RAM crashes
- RAM SHIELD FALLBACK: Bypasses Docling using PyPDF if slicer fails on massive PDFs
- Resume from last successful file (checkpoint)
- Retry individual files up to 3 times on OOM or errors
- Bulletproof saves after every single batch
- Increased token limits to support Qwen <think> reasoning blocks
- SELF-HEALING: Auto-purges garbage summaries ("user", "assistant") and retries them.
- IRONCLAD FALLBACK: Guarantees a clean summary even if the LLM fails.
"""

import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import sys
sys.setrecursionlimit(5000)  # Prevents pypdf from crashing on complex government PDFs
import json
import torch
import gc
import shutil
import re
from pathlib import Path
from tqdm import tqdm
from transformers import BitsAndBytesConfig, AutoTokenizer, AutoModelForCausalLM, pipeline

# Import config
from src.build.config import CONFIG, logger

# ------------------------------------------------------------------------------
# PDF extraction – use Docling (default options)
# ------------------------------------------------------------------------------
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
    logger.info("docling found – using high-quality PDF extraction")
except ImportError as e:
    logger.error(f"docling not available: {e}")
    sys.exit(1)

def ensure_docling_models():
    """Clear any corrupted docling cache and force fresh download."""
    cache_dir = Path.home() / ".cache/huggingface/hub"
    docling_cache = list(cache_dir.glob("models--ds4sd--docling-models"))
    docling_cache += list(cache_dir.glob("models--docling-project--docling-models"))
    if docling_cache:
        for d in docling_cache:
            logger.info(f"Removing corrupted docling cache: {d}")
            shutil.rmtree(d, ignore_errors=True)
    try:
        from io import BytesIO
        from reportlab.pdfgen import canvas
        dummy_buffer = BytesIO()
        c = canvas.Canvas(dummy_buffer)
        c.drawString(10, 10, "Dummy")
        c.save()
        dummy_buffer.seek(0)
        converter = DocumentConverter()
        converter.convert(dummy_buffer)
        logger.info("Docling models downloaded successfully")
    except ImportError:
        logger.warning("reportlab not installed – skipping dummy PDF; models will download on first real PDF")
    except Exception as e:
        logger.warning(f"Dummy PDF conversion failed, but models may still download later: {e}")

def get_quantization_config():
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

def calculate_summary_length(text: str) -> int:
    text_len = len(text)
    if text_len < 500:
        return 30
    elif text_len < 2000:
        return 50
    elif text_len < 5000:
        return 80
    else:
        return 100

def validate_summary(summary: str, text: str) -> bool:
    if not summary or len(summary.strip()) < 15:
        return False
    
    # Explicitly reject prompt bleed artifacts
    clean_sum = summary.strip().lower()
    if clean_sum in ["user", "assistant", "system"]:
        return False
        
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                 'this', 'that', 'these', 'those', 'it', 'its'}
    words = [w.lower() for w in text.split()
             if w.lower() not in stopwords and len(w) > 4 and w.isalpha()]
    important_terms = set(words[:20])
    summary_lower = summary.lower()
    if important_terms and not any(term in summary_lower for term in important_terms):
        return False
    return True

def extract_text_from_pdf(file_path: Path, converter) -> str:
    """Extract text using docling. Forcefully slices to max 10 pages to prevent RAM crashes."""
    import tempfile
    try:
        target_path = str(file_path)
        is_sliced = False

        try:
            from pypdf import PdfReader, PdfWriter
            reader = PdfReader(target_path)
            
            if len(reader.pages) > 10:
                logger.info(f"📄 PDF '{file_path.name}' is {len(reader.pages)} pages. Slicing to first 10 pages...")
                writer = PdfWriter()
                num_pages = min(10, len(reader.pages))
                for i in range(num_pages):
                    writer.add_page(reader.pages[i])
                    
                temp_pdf = Path(tempfile.gettempdir()) / f"sliced_10_{file_path.name}"
                with open(temp_pdf, "wb") as f:
                    writer.write(f)
                
                target_path = str(temp_pdf)
                is_sliced = True
        except ImportError:
            logger.warning("pypdf not installed. Run: pip install pypdf. Attempting full file...")
        except Exception as slice_err:
            # === THE RAM SHIELD FALLBACK ===
            logger.warning(f"Failed to slice {file_path.name}: {slice_err}. Bypassing Docling and extracting raw text to protect RAM...")
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(file_path))
                fallback_text = ""
                for i in range(min(10, len(reader.pages))):
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        fallback_text += page_text + "\n"
                return fallback_text[:4000]
            except Exception as fallback_err:
                logger.error(f"Fallback extraction failed: {fallback_err}")
                return ""

        # Normal Docling flow if sliced successfully (or if under 10 pages)
        result = converter.convert(target_path)
        extracted_text = result.document.export_to_markdown()[:4000]

        if is_sliced and Path(target_path).exists():
            try:
                Path(target_path).unlink()
            except OSError:
                pass

        return extracted_text

    except Exception as e:
        logger.warning(f"Docling extraction failed for {file_path.name}: {e}")
        return ""

def extract_text_from_file(file_path: Path, converter) -> str:
    try:
        if file_path.suffix.lower() == ".pdf":
            return extract_text_from_pdf(file_path, converter)
        else:
            with open(file_path, 'r', errors='ignore') as f:
                return f.read(4000)
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return ""

def scan_all_files():
    """Walk all vaults, ignore junk, and ONLY keep PDFs and code files inside 'repos' folders."""
    files = []
    # Added 'test' and 'tests' to block the OWASP Juice Shop garbage PDFs
    IGNORE_DIRS = {'node_modules', 'venv', 'env', '__pycache__', '.venv', 'dist', 'build', '.idea', '.vscode', 'target', 'out', 'test', 'tests'}

    for vault_name in CONFIG.get("VAULT_MAPPING", {}).keys():
        vault_path = CONFIG.get("RAW_PATH", Path(".")) / vault_name
        if not vault_path.exists():
            continue

        for root, dirs, filenames in os.walk(vault_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in IGNORE_DIRS]

            for filename in filenames:
                if filename.startswith('.'):
                    continue

                fp = Path(root) / filename
                ext = fp.suffix.lower()
                code_exts = [e.lower() for e in CONFIG.get("CODE_EXTENSIONS", [])]

                is_pdf = (ext == ".pdf")
                is_code = (ext in code_exts)
                in_repos_folder = ("repos" in fp.parts)

                if is_pdf or (is_code and in_repos_folder):
                    files.append(fp)

    files.sort(key=lambda p: str(p))
    logger.info(f"Found {len(files)} target files (PDFs + Repos) to summarize after strict filtering")
    return files

def load_existing_summaries():
    """Loads summaries and automatically purges known garbage outputs to force a retry."""
    out_file = Path(CONFIG.get("SUMMARIES_FILE", "summaries.json"))
    valid_data = {}
    if out_file.exists():
        try:
            with open(out_file, 'r') as f:
                data = json.load(f)
                
            for path, summary in data.items():
                clean_sum = summary.strip().lower()
                # If the summary is garbage, we DO NOT add it to valid_data. It will be re-processed.
                if len(clean_sum) < 15 or clean_sum in ["user", "assistant", "system", "user\n", "assistant\n"]:
                    logger.info(f"🗑️ Auto-purged bad summary for {Path(path).name}. Queued for retry.")
                else:
                    valid_data[path] = summary
                    
            logger.info(f"Loaded {len(valid_data)} valid existing summaries")
            return valid_data
        except Exception as e:
            logger.warning(f"Failed to load existing summaries: {e}")
    return {}

def save_checkpoint(last_file, batch_count):
    ckpt_file = Path(CONFIG.get("SUMMARIES_FILE", "summaries.json")).parent / "summaries_checkpoint.json"
    try:
        ckpt_file.parent.mkdir(parents=True, exist_ok=True)
        with open(ckpt_file, 'w') as f:
            json.dump({"last_file": last_file, "batch_count": batch_count}, f)
    except Exception as e:
        logger.warning(f"Failed to save checkpoint: {e}")

def load_checkpoint():
    ckpt_file = Path(CONFIG.get("SUMMARIES_FILE", "summaries.json")).parent / "summaries_checkpoint.json"
    if ckpt_file.exists():
        try:
            with open(ckpt_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_file": None, "batch_count": 0}

def save_summaries_incremental(summary_map, batch_count):
    out_file = Path(CONFIG.get("SUMMARIES_FILE", "summaries.json"))
    try:
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, 'w') as f:
            json.dump(summary_map, f, indent=2)
        logger.info(f"Saved {len(summary_map)} summaries (batch {batch_count})")
    except Exception as e:
        logger.error(f"Failed to save summaries: {e}")

# ==============================================================================
# Main Execution
# ==============================================================================
def main():
    print("🔄 Generating file summaries with Qwen 3.5 4B (4-bit quantized)...")
    print("=" * 70)

    out_file = Path(CONFIG.get("SUMMARIES_FILE", "summaries.json"))
    batch_size = CONFIG.get("SUMMARY_BATCH_SIZE", 4)
    model_name = CONFIG.get("SUMMARY_MODEL", "Qwen/Qwen3.5-4B")

    ensure_docling_models()

    if not torch.cuda.is_available():
        logger.error("CUDA not available. 4-bit quantization requires GPU.")
        print("❌ ERROR: This script requires a CUDA-enabled GPU.")
        return

    device = 0
    gpu_name = torch.cuda.get_device_name(0)
    gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"  GPU: {gpu_name} ({gpu_memory_gb:.1f}GB VRAM)")
    print(f"  Using 4-bit quantization (nf4) with FP16 compute")
    print(f"  Batch size: {batch_size}")

    torch.backends.cudnn.benchmark = False

    print(f"  Loading model: {model_name} (4-bit quantized)...")
    try:
        torch.cuda.empty_cache()
        gc.collect()

        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="left"
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        quantization_config = get_quantization_config()

        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quantization_config,
            device_map="cuda:0",
            trust_remote_code=True,
            dtype=torch.float16,
            low_cpu_mem_usage=True,
            max_memory={0: "6.0GB"}
        )

        summarizer = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            device_map="cuda:0",
            dtype=torch.float16,
            batch_size=batch_size,
            return_full_text=False,
            truncation=True,
        )
        print("  ✅ Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        print("\n💡 Troubleshooting:")
        print("  1. Ensure bitsandbytes>=0.46.1 is installed: pip install -U bitsandbytes")
        print("  2. Ensure transformers is up to date: pip install -U transformers")
        return

    # 🔥 The script will now auto-purge the garbage lines from memory!
    summary_map = load_existing_summaries()
    checkpoint = load_checkpoint()

    all_files = scan_all_files()
    remaining_files = [fp for fp in all_files if str(fp) not in summary_map]
    logger.info(f"Skipping {len(all_files) - len(remaining_files)} already processed files")
    logger.info(f"Remaining files to process: {len(remaining_files)}")

    if not remaining_files:
        print("✅ All files already processed. No work to do.")
        ckpt_file = out_file.parent / "summaries_checkpoint.json"
        if ckpt_file.exists():
            ckpt_file.unlink()
        return

    try:
        pdf_converter = DocumentConverter()
        print("  ✅ PDF converter initialized (docling)")
    except Exception as e:
        logger.error(f"Failed to initialize docling: {e}")
        return

    print("  Starting file processing...")
    print("=" * 70)

    processed_count = 0
    current_batch_size = batch_size
    total_files = len(remaining_files)
    idx = 0

    last_file = checkpoint.get("last_file")
    if last_file:
        try:
            idx = next(i for i, fp in enumerate(remaining_files) if str(fp) == last_file) + 1
            processed_count = idx
            logger.info(f"Resuming from file index {idx} (last file: {last_file})")
        except StopIteration:
            pass

    with tqdm(total=total_files, desc="Summarizing files", unit="file", initial=processed_count) as pbar:
        while idx < total_files:
            batch_files = remaining_files[idx:idx + current_batch_size]
            batch_data = []
            valid_files = []

            for fp in batch_files:
                try:
                    text = extract_text_from_file(fp, pdf_converter)
                    if text.strip():
                        # Increased token limit (+300) so Qwen can finish its thoughts
                        max_len = calculate_summary_length(text) + 300
                        
                        prompt = f"""<|im_start|>system
You are an expert technical writer. Summarize the following file content in one concise sentence that captures its main purpose and key topics. Focus on what the file does, not implementation details.
<|im_end|>
<|im_start|>user
File: {fp.name}
Content preview:
{text[:3500]}

Please provide a one-sentence summary (max {max_len} tokens):
<|im_end|>
<|im_start|>assistant
---SUMMARY_START---"""
                        batch_data.append({
                            "path": str(fp),
                            "prompt": prompt,
                            "max_tokens": max_len,
                            "original_text": text[:2000]
                        })
                        valid_files.append(fp)
                    else:
                        logger.warning(f"File {fp} is empty or unreadable.")
                        # Apply fallback for empty/image-only PDFs directly
                        summary_map[str(fp)] = f"Technical document regarding the file {fp.name}."
                except Exception as e:
                    logger.warning(f"Skipping {fp}: {e}")

            if not batch_data:
                idx += len(batch_files)
                pbar.update(len(batch_files))
                continue

            success = False
            for attempt in range(3):
                try:
                    prompts = [item["prompt"] for item in batch_data]
                    max_len_batch = max(item["max_tokens"] for item in batch_data)

                    results = summarizer(
                        prompts,
                        max_new_tokens=max_len_batch,
                        do_sample=False,
                    )

                    for item, result in zip(batch_data, results):
                        raw_output = result[0]["generated_text"]

                        if "---SUMMARY_START---" in raw_output:
                            summary = raw_output.split("---SUMMARY_START---")[-1].strip()
                        else:
                            summary = raw_output.strip()

                        # 1. Nuke <think> blocks completely
                        summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL).strip()
                        if "<think>" in summary:
                            summary = summary.split("<think>")[0].strip()

                        # 2. Aggressive tag and role cleanup
                        summary = summary.replace("<|im_end|>", "").replace("<|im_start|>", "")
                        summary = re.sub(r'^(user|assistant|system)\s*', '', summary, flags=re.IGNORECASE).strip()

                        if len(summary) > 1500:
                            summary = summary[:1500] + "..."

                        # 3. THE IRONCLAD FALLBACK
                        if not validate_summary(summary, item["original_text"]):
                            logger.warning(f"Low-quality or garbage summary for {Path(item['path']).name}. Applying deterministic fallback.")
                            summary = f"Technical document regarding the file {Path(item['path']).name}."

                        summary_map[item["path"]] = summary

                    success = True
                    break
                except RuntimeError as e:
                    if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
                        logger.warning(f"OOM at batch, attempt {attempt+1}/3")
                        if attempt < 2:
                            current_batch_size = max(1, current_batch_size // 2)
                            logger.info(f"  Reduced batch size to {current_batch_size}, retrying...")
                            torch.cuda.empty_cache()
                            success = False
                            break
                        else:
                            logger.error("Batch failed after 3 OOM attempts, skipping files.")
                            for item in batch_data:
                                logger.warning(f"  Skipped: {item['path']}")
                            torch.cuda.empty_cache()
                            success = True
                            break
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Batch failed: {e}")
                    for item in batch_data:
                        logger.warning(f"  Failed: {item['path']}")
                    success = True
                    break

            if not success:
                continue

            idx += len(batch_files)
            processed_count += len(batch_files)
            pbar.update(len(batch_files))

            save_checkpoint(str(batch_files[-1]), processed_count // batch_size)

            if len(summary_map) > 0:
                save_summaries_incremental(summary_map, processed_count // batch_size)
                torch.cuda.empty_cache()

            if processed_count % (current_batch_size * 10) == 0:
                torch.cuda.empty_cache()

    save_summaries_incremental(summary_map, processed_count // batch_size)
    ckpt_file = out_file.parent / "summaries_checkpoint.json"
    if ckpt_file.exists():
        ckpt_file.unlink()

    print("=" * 70)
    print(f"✅ Generated {len(summary_map)} summaries saved to {out_file}")
    print(f"  Model: {model_name} (4-bit quantized)")
    print("=" * 70)

if __name__ == "__main__":
    main()