# backend_service/utils/downloader.py
import os
import urllib.request
import zipfile
from pathlib import Path

def run_bootstrap():
    try:
        from huggingface_hub import snapshot_download, hf_hub_download
    except ImportError:
        print("❌ ERROR: Missing 'huggingface_hub' dependency. Install with: pip install huggingface-hub")
        return

    MODELS_DIR = Path("./models").resolve()
    MODELS_DIR.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🚀 HACKT SOVEREIGN CORE - MODEL BOOTSTRAPPER")
    print("=" * 60)
    
    # ---------------------------------------------------------
    # 1. Fetch RAG Index (from Hugging Face)
    # ---------------------------------------------------------
    index_target_dir = MODELS_DIR / "index"
    zip_path = MODELS_DIR / "index.zip"
    
    if not (index_target_dir.exists() and any(index_target_dir.iterdir())):
        print("\n🗄️ [1/6] Syncing Custom RAG Vault Index...")
        try:
            # We download directly to the models folder
            hf_hub_download(
                repo_id="PRiyanshu0-1/hackt-agent-rag-index",
                repo_type="dataset", # Explicitly tell HF it's a dataset repo
                filename="index.zip",
                local_dir=MODELS_DIR,
            )
            
            print("  📦 Extracting index.zip...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # We extract to a temp folder then move, or extract directly to /index
                # to ensure we don't clutter the models/ root.
                zip_ref.extractall(index_target_dir)
            
            zip_path.unlink()
            print("  ✅ Vault Index successfully installed!")
        except Exception as e:
            print(f"  ❌ Index Sync Failed: {e}")
            # Non-fatal error, we can continue but RAG will be empty
    else:
        print("\n🗄️ [1/6] Vault Index already present.")

    # ---------------------------------------------------------
    # 2. Sync All Other Models (Using native snapshot_download)
    # ---------------------------------------------------------
    
    # LLM
    print("\n🧠 [2/6] Syncing Master LLM (Qwen 3.5 4B Instruct)...")
    snapshot_download(
        repo_id="unsloth/Qwen3.5-4B-GGUF",
        local_dir=MODELS_DIR,
        allow_patterns=["*q4_k_m.gguf", "*Q4_K_M.gguf"]
    )

    # Vision
    print("\n👁️ [3/6] Syncing Vision Core (Florence-2-base)...")
    snapshot_download(
        repo_id="microsoft/Florence-2-base",
        local_dir=MODELS_DIR / "florence-2",
        ignore_patterns=["*.msgpack", "*.h5", "rust_model.ot"]
    )

    # Embedder
    print("\n🕸️ [4/6] Syncing RAG Embedder (Nomic-Embed-v1.5)...")
    snapshot_download(
        repo_id="nomic-ai/nomic-embed-text-v1.5",
        local_dir=MODELS_DIR / "nomic-embed",
        ignore_patterns=["*.msgpack", "*.h5", "rust_model.ot"]
    )

    # STT
    print("\n🎤 [5/6] Syncing Voice Engine (Faster-Whisper)...")
    snapshot_download(
        repo_id="Systran/faster-whisper-small",
        local_dir=MODELS_DIR / "whisper"
    )

    # 6. Fetch TTS (Pre-Compiled Windows Engine)
    print("\n🔊 [6/6] Syncing Voice Synthesis (Piper TTS Engine)...")
    piper_dir = MODELS_DIR / "piper"
    piper_dir.mkdir(exist_ok=True)
    
    # Download the ONNX Voice Model
    base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
    for f in ["en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json"]:
        dest = piper_dir / f
        if not dest.exists():
            print(f"  ⬇️ Downloading {f}...")
            urllib.request.urlretrieve(f"{base_url}{f}", dest)

    piper_exe = piper_dir / "piper" / "piper.exe"
    if not piper_exe.exists():
        print("  ⬇️ Downloading Piper Windows Engine...")
        zip_url = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
        zip_path = piper_dir / "piper.zip"
        urllib.request.urlretrieve(zip_url, zip_path)
        
        print("  📦 Extracting Piper Engine...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(piper_dir)
        zip_path.unlink()
        print("  ✅ Piper Engine successfully installed!")
    else:
        print("  ✅ Piper Engine already present.")
            
    print("\n✅ ALL MODELS & INDEXES SYNCED SUCCESSFULLY.")