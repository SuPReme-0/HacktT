# backend_service/utils/downloader.py
import os
import urllib.request
import zipfile
import shutil
from pathlib import Path

def run_bootstrap():
    try:
        from huggingface_hub import snapshot_download, hf_hub_download
    except ImportError:
        print("❌ ERROR: Missing 'huggingface_hub'. Run: pip install huggingface-hub")
        return

    # 🚀 Windows Compatibility: Disable symlinks to avoid requiring Admin Privileges
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

    MODELS_DIR = Path("./models").resolve()
    MODELS_DIR.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🚀 HACKT SOVEREIGN CORE - MODEL BOOTSTRAPPER")
    print("=" * 60)
    
    # ---------------------------------------------------------
    # 1. Fetch RAG Index (Tantivy + Vector + Graph)
    # ---------------------------------------------------------
    index_target_dir = MODELS_DIR / "index"
    zip_path = MODELS_DIR / "index.zip"
    
    if not (index_target_dir.exists() and any(index_target_dir.iterdir())):
        print("\n🗄️ [1/6] Syncing Custom RAG Vault Index...")
        try:
            hf_hub_download(
                repo_id="PRiyanshu0-1/hackt-agent-rag-index",
                repo_type="dataset", 
                filename="index.zip",
                local_dir=MODELS_DIR,
            )
            
            print("  📦 Extracting vault index...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extracting directly to ensure models/index/vault.graph structure
                zip_ref.extractall(index_target_dir)
            
            zip_path.unlink()
            print("  ✅ Vault Index successfully installed!")
        except Exception as e:
            print(f"  ❌ Index Sync Failed: {e}")
    else:
        print("\n🗄️ [1/6] Vault Index already present.")

    # ---------------------------------------------------------
    # 2. Master LLM (Qwen 3.5 4B)
    # ---------------------------------------------------------
    print("\n🧠 [2/6] Syncing Master LLM (Qwen 3.5 4B Instruct)...")
    snapshot_download(
        repo_id="unsloth/Qwen3.5-4B-GGUF",
        local_dir=MODELS_DIR,
        allow_patterns=["*q4_k_m.gguf", "*Q4_K_M.gguf"],
        local_dir_use_symlinks=False # Force actual file copy
    )

    # ---------------------------------------------------------
    # 3. Vision Core (Florence-2)
    # ---------------------------------------------------------
    print("\n👁️ [3/6] Syncing Vision Core (Florence-2-base)...")
    snapshot_download(
        repo_id="microsoft/Florence-2-base",
        local_dir=MODELS_DIR / "florence-2",
        ignore_patterns=["*.msgpack", "*.h5", "rust_model.ot", "*.md"],
        local_dir_use_symlinks=False
    )

    # ---------------------------------------------------------
    # 4. RAG Embedder (Nomic-v1.5)
    # ---------------------------------------------------------
    print("\n🕸️ [4/6] Syncing RAG Embedder (Nomic-Embed-v1.5)...")
    snapshot_download(
        repo_id="nomic-ai/nomic-embed-text-v1.5",
        local_dir=MODELS_DIR / "nomic-embed",
        ignore_patterns=["*.msgpack", "*.h5", "rust_model.ot"],
        local_dir_use_symlinks=False
    )

    # ---------------------------------------------------------
    # 5. Voice Engine (Faster-Whisper)
    # ---------------------------------------------------------
    print("\n🎤 [5/6] Syncing Voice Engine (Faster-Whisper)...")
    snapshot_download(
        repo_id="Systran/faster-whisper-small",
        local_dir=MODELS_DIR / "whisper",
        local_dir_use_symlinks=False
    )

    # ---------------------------------------------------------
    # 6. Piper TTS (Flattened Directory Structure)
    # ---------------------------------------------------------
    print("\n🔊 [6/6] Syncing Voice Synthesis (Piper TTS Engine)...")
    piper_dir = MODELS_DIR / "piper"
    piper_dir.mkdir(exist_ok=True)
    
    # Download ONNX Voice Model
    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
    for f in ["en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json"]:
        dest = piper_dir / f
        if not dest.exists():
            print(f"  ⬇️ Downloading {f}...")
            urllib.request.urlretrieve(f"{base_url}{f}", dest)

    # Download and Flatten Engine
    piper_exe = piper_dir / "piper.exe"
    if not piper_exe.exists():
        print("  ⬇️ Downloading Piper Windows Engine...")
        zip_url = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
        zip_path = piper_dir / "piper.zip"
        urllib.request.urlretrieve(zip_url, zip_path)
        
        temp_extract = piper_dir / "temp_extract"
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
        
        # Move files from /temp_extract/piper/* to /piper/ (Flattening)
        inner_dir = temp_extract / "piper"
        for item in inner_dir.iterdir():
            shutil.move(str(item), str(piper_dir / item.name))
        
        # Cleanup
        zip_path.unlink()
        shutil.rmtree(temp_extract)
        print("  ✅ Piper Engine successfully installed & flattened!")
    else:
        print("  ✅ Piper Engine already present.")
            
    print("\n✅ ALL MODELS & INDEXES SYNCED SUCCESSFULLY.")