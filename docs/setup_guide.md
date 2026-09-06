# HackT Setup Guide

This guide will walk you through setting up the HackT Sovereign AI Agent in the new monolithic repository structure.

## Prerequisites

- **Python**: 3.11+
- **Node.js**: 18+
- **Rust Toolchain**: For Tauri backend compilation
- **FFmpeg**: Required for Faster-Whisper and Kokoro TTS audio processing
- **Hardware**: Minimum 8GB RAM. 6GB+ Dedicated VRAM recommended for Passive Mode (Florence-2 Vision).

## 1. Backend Setup

The backend is built with FastAPI and runs the core AI inference services.

```bash
cd backend

# Create a virtual environment (recommended)
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Model Download
You need to download the quantized Qwen 3.5 4B model manually:

```bash
python -c "from huggingface_hub import hf_hub_download; hf_hub_download('Qwen/Qwen3.5-4B-gguf', 'qwen3.5-4b-q4_k_m.gguf')"
```
*Move the downloaded `.gguf` file to the `backend/models/llm/` directory.*

## 2. Frontend & Desktop Setup (Tauri + React)

The frontend contains the UI and the Rust-based Tauri desktop bindings.

```bash
cd frontend

# Install Node dependencies
npm install

# Start the development server (starts both Vite and Tauri)
npm run tauri:dev
```

## 3. RAG Pipeline Setup (Optional)

If you wish to rebuild the vector databases or structural graphs manually, use the `rag-pipeline/` directory.

```bash
cd rag-pipeline

# Install pipeline-specific requirements
pip install -r requirements.txt

# Run the build orchestrator
python run_build.py
```

## Configuration

A sample `config.json` is provided in the `backend/` folder. Copy it and modify as needed to adjust hyperparameters, thread counts, or model file paths.

> [!IMPORTANT]
> If you experience out-of-memory (OOM) crashes, adjust the `force_cpu_mode` flag to `true` in your `config.json` or ensure that no other heavy GPU workloads are running alongside HackT.
