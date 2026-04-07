"""
HackT Sovereign Core - Configuration Module (v3.0)
===================================================
The Single Source of Truth for the entire backend.
Features:
- Pydantic Validation (Type safety & Range checking)
- PyInstaller/Frozen-state path resolution
- Environment Variable Overrides
- Centralized Service Ports & Vault Definitions
- VRAM-based Feature Gating
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Prevent circular imports: Config must be standalone
logger = logging.getLogger("hackt.utils.config")

# ==============================================================================
# OS-Level Path Resolution (PyInstaller Safe)
# ==============================================================================
def get_app_root() -> Path:
    """
    Dynamically resolves the application root directory.
    Critical for PyInstaller .exe compatibility.
    """
    if getattr(sys, 'frozen', False):
        # Production: sys.executable is the .exe location
        return Path(sys.executable).parent
    else:
        # Development: Parent of utils/ directory
        return Path(__file__).resolve().parent.parent

# ==============================================================================
# Domain Configurations (Pydantic Models)
# ==============================================================================

class ModelConfig(BaseSettings):
    """Configuration for AI Models (LLM, Vision, Audio, Embedder)."""
    model_config = SettingsConfigDict(extra='ignore')

    # Qwen 3.5 LLM
    llm_filename: str = "Qwen3.5-4b-Q4_K_M.gguf"
    llm_n_ctx: int = Field(default=4096, gt=512)
    llm_n_batch: int = Field(default=512, gt=64)
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    # 🚀 Synced with engine.py stop tokens
    llm_stop_tokens: List[str] = ["<|im_end|>", "<|im_start|>", "\nuser\n", "user:"]
    
    # Florence-2 Vision
    vision_model_id: str = "microsoft/Florence-2-base"
    vision_max_tokens: int = Field(default=512, gt=1)
    vision_beam_size: int = Field(default=3, gt=0)
    
    # Embedder (Nomic)
    embedder_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedder_max_seq_length: int = 512
    embedder_dimensionality: int = 256  # Matryoshka truncation
    
    # Audio Models (CPU)
    stt_model: str = "base.en"
    stt_device: str = "cpu"
    tts_model: str = "en_US-lessac-medium"
    audio_model_dir: str = "audio"  # Subdir inside models_dir

class VRAMConfig(BaseSettings):
    """VRAM safety configuration & Hardware Limits."""
    model_config = SettingsConfigDict(extra='ignore')

    limit_gb: float = Field(default=6.0, gt=0.0)
    buffer_gb: float = Field(default=1.0, ge=0.0)
    llm_estimate_gb: float = Field(default=2.5, gt=0.0)
    vision_estimate_gb: float = Field(default=1.2, gt=0.0)
    enable_heuristics: bool = True

class VaultConfig(BaseSettings):
    """
    Explicit Vault Definitions.
    Syncs with rag.py vault_map and orchestrator.py intent classification.
    """
    model_config = SettingsConfigDict(extra='ignore')

    library_id: int = 1
    library_name: str = "Library"      # Standards, Docs, ISO
    
    laboratory_id: int = 2
    laboratory_name: str = "Laboratory" # Code, Exploits, Vulns
    
    showroom_id: int = 3
    showroom_name: str = "Showroom"    # Demos, UI Snippets

class ModeConfig(BaseSettings):
    """Active vs Passive mode logic and thresholds."""
    model_config = SettingsConfigDict(extra='ignore')

    active_enabled_features: List[str] = ["chat", "rag", "stt", "tts"]
    
    passive_enabled_features: List[str] = [
        "chat", "rag", "stt", "tts", "vision", 
        "ide_monitor", "browser_monitor", "screen_scan"
    ]
    
    passive_min_vram_gb: float = 6.0
    screen_scan_interval: float = 5.0
    telemetry_push_interval: float = 2.0
    passive_scan_interval: float = 10.0  # Syncs with threat_scanner.py

class RAGConfig(BaseSettings):
    """Retrieval Augmented Generation Tuning."""
    model_config = SettingsConfigDict(extra='ignore')

    semantic_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    max_context_chars: int = Field(default=6000, gt=100)
    hybrid_search_limit: int = 15
    voice_bypass_limit: int = 3

class ServiceConfig(BaseSettings):
    """Network Ports & Service Endpoints."""
    model_config = SettingsConfigDict(extra='ignore')

    api_port: int = 8000
    ide_listener_port: int = 8081
    browser_listener_port: int = 8082
    host: str = "127.0.0.1"

class PathsConfig(BaseSettings):
    """Strict absolute pathing utilizing the PyInstaller-safe root."""
    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    base_dir: Path = Field(default_factory=get_app_root)
    models_dir: Optional[Path] = None
    vault_dir: Optional[Path] = None
    data_dir: Optional[Path] = None
    logs_dir: Optional[Path] = None
    
    def model_post_init(self, __context: Any) -> None:
        """Initialize paths relative to base_dir."""
        self.models_dir = self.base_dir / "models"
        self.vault_dir = self.base_dir / "vault"
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        
        # Ensure critical directories exist
        for dir_path in [self.models_dir, self.vault_dir, self.data_dir, self.logs_dir]:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create directory {dir_path}: {e}")

# ==============================================================================
# Master Configuration Container
# ==============================================================================
# ==============================================================================
# Master Configuration Container
# ==============================================================================

class Config(BaseSettings):
    """
    Master Configuration Container.
    Loads from config.json first, then overrides with Environment Variables.
    """
    model_config = SettingsConfigDict(
        env_prefix="HACKT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra='ignore'
    )

    # General
    mode: str = Field(default="active", pattern="^(active|passive)$")
    app_name: str = "HackT Sovereign Core"
    version: str = "1.0.0"
    debug: bool = False
    
    # Security
    cors_origins: List[str] = ["*"]  # Restrict in production
    enable_telemetry: bool = True
    enable_cloud_sync: bool = False
    
    # Nested Configs
    model: ModelConfig = Field(default_factory=ModelConfig)
    vram: VRAMConfig = Field(default_factory=VRAMConfig)
    vaults: VaultConfig = Field(default_factory=VaultConfig)
    modes: ModeConfig = Field(default_factory=ModeConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    services: ServiceConfig = Field(default_factory=ServiceConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    # ---------------------------------------------------------
    # Root Accessors (Bridging root calls to nested configs)
    # ---------------------------------------------------------
    @property
    def host(self) -> str:
        """Alias for the Service Host."""
        return self.services.host

    @property
    def port(self) -> int:
        """Alias for the Service API Port."""
        return self.services.api_port

    # ---------------------------------------------------------
    # Path Resolvers (Safe Accessors)
    # ---------------------------------------------------------
    @property
    def absolute_llm_path(self) -> Path:
        """Returns the absolute Path object to the LLM."""
        return self.paths.models_dir / self.model.llm_filename

    @property
    def absolute_audio_dir(self) -> Path:
        """Returns the absolute Path to the audio models."""
        return self.paths.models_dir / self.model.audio_model_dir

    # ---------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is allowed in the current mode."""
        if self.mode == "passive":
            return feature in self.modes.passive_enabled_features
        return feature in self.modes.active_enabled_features

    def get_vault_id(self, vault_name: str) -> Optional[int]:
        """Helper to get vault ID by name (e.g., 'library' -> 1)."""
        name = vault_name.lower()
        if name == "library": return self.vaults.library_id
        if name == "laboratory": return self.vaults.laboratory_id
        if name == "showroom": return self.vaults.showroom_id
        return None

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------
    @validator('cors_origins')
    def validate_cors(cls, v):
        if "*" in v and len(v) > 1:
            logger.warning("Config: CORS is set to '*' along with specific origins. This is redundant.")
        return v
    
# ==============================================================================
# Global Singleton Initialization
# ==============================================================================

def load_config() -> Config:
    """
    Loads configuration with fallback hierarchy:
    1. Environment Variables (HACKT_*)
    2. config.json (in app root)
    3. Default Values
    """
    config_path = get_app_root() / "config.json"
    
    # Pydantic Settings automatically handles env vars.
    # We manually inject the json file path if it exists.
    env_file = ".env" if Path(".env").exists() else None
    
    try:
        if config_path.exists():
            logger.info(f"Loading config from: {config_path}")
            return Config(_env_file=env_file, _secrets_dir=None) # Pydantic v2 style
        else:
            logger.warning("config.json not found. Using defaults + env vars.")
            return Config(_env_file=env_file, _secrets_dir=None)
    except Exception as e:
        logger.critical(f"Failed to initialize configuration: {e}")
        # Return a safe default config to prevent immediate crash
        return Config()

# Initialize Global Singleton
config = load_config()