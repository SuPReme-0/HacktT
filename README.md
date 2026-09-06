<div align="center">
<img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg?style=for-the-badge" />
<img src="https://img.shields.io/badge/Stack-Tauri%20%7C%20React%20%7C%20FastAPI%20%7C%20Python-blue.svg?style=for-the-badge" />
<img src="https://img.shields.io/badge/AI-Llama%20%7C%20LanceDB%20%7C%20Kuzu%20%7C%20TreeSitter-orange.svg?style=for-the-badge" />
</div>

# HackT: Sovereign AI Agent — Local Cybersecurity Assistant

**HackT** is a production-ready sovereign AI agent that runs entirely on-device. It combines a TypeScript/React frontend (Tauri) with a Python FastAPI backend to provide real-time threat detection, code-level security auditing, and LLM-powered assistance — all without cloud dependencies.

Operating under **Project Trinity** architecture, HackT enforces strict zero-cloud policies: every LLM inference, vector embedding, and graph traversal executes locally using quantized models. 

---

## 📂 Repository Structure

The project has been structured into a standard monolithic repository:

```
HackT/
├── frontend/                 # React UI + Tauri Desktop application
│   ├── src/                  # React components, state, hooks
│   ├── src-tauri/            # Rust backend for system integration
│   ├── package.json          # Node dependencies and scripts
│   └── vite.config.ts        # Vite configuration
│
├── backend/                  # Python FastAPI Core Services
│   ├── main.py               # Application entry point
│   ├── core/                 # LLM Engine, RAG, Memory Guard
│   ├── services/             # Threat scanner, Websockets, Audio processing
│   └── requirements.txt      # Python dependencies
│
├── rag-pipeline/             # Vector and Graph building scripts
│   ├── run_build.py          # Orchestrator
│   └── src/                  # Parsing and embedding logic
│
└── docs/                     # Comprehensive Documentation
    ├── architecture.md       # Detailed system design
    ├── setup_guide.md        # Installation instructions
    └── threat_detection.md   # AST scanning engine details
```

---

## 🚀 Quick Start

Please see our full [Setup Guide](docs/setup_guide.md) for detailed instructions on prerequisites and environment configurations.

### 1. Run the Backend
```bash
cd backend
pip install -r requirements.txt
# Download the Qwen 3.5 4B model (see setup_guide.md)
python main.py
```

### 2. Run the Frontend (Tauri)
```bash
cd frontend
npm install
npm run tauri:dev
```

---

## 📖 Documentation

- **[System Architecture](docs/architecture.md)**: Deep dive into the VRAM guards, IPC, and model inference.
- **[Setup Guide](docs/setup_guide.md)**: Hardware requirements and step-by-step installation.
- **[Threat Detection](docs/threat_detection.md)**: Learn how the Tree-sitter AST engine parses and secures code on the fly.

---

## 🛡️ Security Promise

| Layer | Mechanism |
|-------|-----------|
| **Local-only Inference** | Qwen 3.5 4B quantized via llama-cpp-python — zero remote API calls |
| **VRAM Guard** | Real-time memory pressure monitoring with auto-degradation |
| **AST Threat Detection** | Tree-sitter-based pattern matching for 6 languages |
| **Code Diff Sandboxing** | Suggested fixes broadcast to UI; explicit user approval required |