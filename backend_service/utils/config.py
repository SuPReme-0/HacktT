"""
HackT Sovereign Core - Configuration Module
============================================
Provides mode-aware configuration loading with:
- Environment variable overrides
- Active/Passive mode thresholds
- VRAM-based feature gating
- Automatic directory generation
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, Union
from dataclasses import dataclass, field, asdict

from .logger import get_logger

logger = get_logger("hackt.utils.config")


@dataclass
class ModelConfig:
    """Configuration for AI models."""
    # Qwen 3.5 LLM
    llm_path: str = "models/qwen-3.5-4b-q4_k_m.gguf"
    llm_n_ctx: int = 4096  # Context window
    llm_n_batch: int = 512  # Batch size for inference
    llm_temperature: float = 0.1  # Low for factual accuracy
    llm_top_p: float = 0.9
    
    # Florence-2 Vision
    vision_model_id: str = "microsoft/Florence-2-base"
    vision_max_tokens: int = 512
    vision_beam_size: int = 3
    
    # Embedding model
    embedder_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedder_max_seq_length: int = 512
    
    # STT/TTS (CPU-only to save VRAM)
    # FIXED: Upgraded to base.en to match the audio service
    stt_model: str = "base.en"  # Faster-Whisper model size 
    stt_device: str = "cpu"
    tts_model: str = "en_US-lessac-medium"  # Piper model


@dataclass
class VRAMConfig:
    """VRAM safety configuration."""
    limit_gb: float = 6.0  # Max VRAM for models
    buffer_gb: float = 1.0  # Safety buffer for OS
    llm_estimate_gb: float = 2.5  # Qwen 3.5 4-bit estimate
    vision_estimate_gb: float = 1.2  # Florence-2 estimate
    enable_heuristics: bool = True  # Use heuristics for unknown GPUs


@dataclass
class ModeConfig:
    """Active vs Passive mode configuration."""
    # Active Mode (Chat-only, low VRAM)
    active_enabled_features: list = field(default_factory=lambda: [
        "chat", "rag", "stt", "tts"
    ])
    
    # Passive Mode (Full Sentinel, higher VRAM)
    passive_enabled_features: list = field(default_factory=lambda: [
        "chat", "rag", "stt", "tts", "vision", "ide_monitor", "browser_monitor", "screen_scan"
    ])
    
    # VRAM threshold for Passive Mode
    passive_min_vram_gb: float = 6.0
    
    # Scan intervals (seconds)
    screen_scan_interval: float = 5.0
    telemetry_push_interval: float = 2.0


@dataclass
class PathsConfig:
    """File and directory paths."""
    # This sets base_dir to backend_service/
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    models_dir: Path = field(init=False)
    vault_dir: Path = field(init=False)
    data_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    
    def __post_init__(self):
        self.models_dir = self.base_dir / "models"
        self.vault_dir = self.base_dir / "vault"
        self.data_dir = self.base_dir / "data"
        self.logs_dir = self.base_dir / "logs"
        
        # FIXED: Changed are_ok to exist_ok
        for dir_path in [self.models_dir, self.vault_dir, self.data_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    """Master configuration container."""
    mode: str = "active"  # "active" or "passive"
    model: ModelConfig = field(default_factory=ModelConfig)
    vram: VRAMConfig = field(default_factory=VRAMConfig)
    modes: ModeConfig = field(default_factory=ModeConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    
    # Backend server
    host: str = "127.0.0.1"
    port: int = 8080
    reload: bool = False
    
    # CORS for Tauri frontend
    cors_origins: list = field(default_factory=lambda: ["*"])  # Restrict in production
    
    # Feature flags
    enable_telemetry: bool = True
    enable_cloud_sync: bool = False  # Supabase sync
    enable_ide_extension: bool = True
    enable_browser_extension: bool = True
    
    @classmethod
    def from_env(cls, env_prefix: str = "HACKT_") -> "Config":
        """Load configuration from environment variables."""
        config = cls()
        
        # Override mode
        if mode := os.environ.get(f"{env_prefix}MODE"):
            config.mode = mode.lower()
        
        # Override server settings
        if host := os.environ.get(f"{env_prefix}HOST"):
            config.host = host
        if port := os.environ.get(f"{env_prefix}PORT"):
            config.port = int(port)
        
        # Override VRAM limits
        if vram_limit := os.environ.get(f"{env_prefix}VRAM_LIMIT_GB"):
            config.vram.limit_gb = float(vram_limit)
        
        # Override CORS
        if cors := os.environ.get(f"{env_prefix}CORS_ORIGINS"):
            config.cors_origins = cors.split(",")
        
        logger.info(f"Config loaded: mode={config.mode}, port={config.port}")
        return config
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Config":
        """Load configuration from JSON file."""
        path = Path(path)
        
        if not path.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return cls()
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Simple flat override
            config = cls()
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            logger.info(f"Config loaded from file: {path}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
            return cls()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return asdict(self)
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled for current mode."""
        if self.mode == "passive":
            return feature in self.modes.passive_enabled_features
        return feature in self.modes.active_enabled_features
    
    def can_enable_passive_mode(self, available_vram_gb: float) -> bool:
        """Check if Passive Mode can be enabled with available VRAM."""
        return available_vram_gb >= self.modes.passive_min_vram_gb
    
    def get_model_path(self, model_name: str) -> Path:
        """Get full path for a model file."""
        return self.paths.models_dir / model_name


# Singleton instance
config = Config.from_env()