"""
Centralized Configuration Module for Trivox AI Models

This module provides centralized configuration management with validation,
type safety, and environment variable support.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
import json


@dataclass(frozen=True)
class ProcessingConfig:
    """Configuration for image processing pipeline."""

    min_images: int = 3
    max_images: int = 5
    target_resolution: tuple = (1024, 1024)
    confidence_threshold: float = 0.6
    fusion_method: str = "weighted_average"
    align_cameras: bool = True
    quality_boost_factor: float = 2.5
    local_min_ram_gb: float = 2.5
    default_quality: str = "standard"
    available_qualities: tuple = ("draft", "standard", "high", "production")


@dataclass(frozen=True)
class APIConfig:
    """Configuration for Hitem3D API integration."""

    base_url: str = "https://api.hitem3d.com/v1"
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Credit costs per model and resolution
    credit_costs: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {
            "hitem3dv1.5": {"512": 15, "1024": 20, "1536": 50, "1536pro": 70},
            "hitem3dv2.0": {"1536": 75, "1536pro": 90},
            "scene-portraitv1.5": {"1536": 70},
            "scene-portraitv2.0": {"1536pro": 70},
            "scene-portraitv2.1": {"1536pro": 70},
        }
    )


@dataclass(frozen=True)
class UIConfig:
    """Configuration for UI behavior and appearance."""

    app_name: str = "Trivox AI Models"
    app_version: str = "1.0.0"
    min_window_size: tuple = (720, 560)
    system_refresh_interval_ms: int = 3000
    balance_check_delay_ms: int = 600
    update_check_delay_ms: int = 800

    # Supported image formats
    supported_image_formats: tuple = (".png", ".jpg", ".jpeg", ".bmp", ".webp")

    # Output formats
    output_formats: tuple = ("obj", "stl", "glb", "fbx", "usdz")


@dataclass(frozen=True)
class SecurityConfig:
    """Configuration for security settings."""

    min_password_length: int = 8
    bcrypt_rounds: int = 12
    token_min_length: int = 10


class ConfigManager:
    """
    Centralized configuration manager with environment variable support.

    Usage:
        from config.settings import config

        # Access configuration
        min_ram = config.processing.local_min_ram_gb
        api_timeout = config.api.timeout_seconds
    """

    def __init__(self):
        self._processing = ProcessingConfig()
        self._api = APIConfig()
        self._ui = UIConfig()
        self._security = SecurityConfig()
        self._load_from_environment()

    def _load_from_environment(self):
        """Load configuration overrides from environment variables."""
        # API Configuration
        if os.getenv("HITEM3D_API_URL"):
            object.__setattr__(self._api, "base_url", os.getenv("HITEM3D_API_URL"))

        if os.getenv("HITEM3D_TIMEOUT"):
            try:
                timeout = int(os.getenv("HITEM3D_TIMEOUT"))
                object.__setattr__(self._api, "timeout_seconds", timeout)
            except ValueError:
                pass

        # UI Configuration
        if os.getenv("TRIVOXAI_UPDATE_URL"):
            object.__setattr__(
                self._ui, "update_url", os.getenv("TRIVOXAI_UPDATE_URL")
            )

        # Processing Configuration
        if os.getenv("TRIVOXAI_MIN_RAM"):
            try:
                min_ram = float(os.getenv("TRIVOXAI_MIN_RAM"))
                object.__setattr__(self._processing, "local_min_ram_gb", min_ram)
            except ValueError:
                pass

    @property
    def processing(self) -> ProcessingConfig:
        """Get processing configuration."""
        return self._processing

    @property
    def api(self) -> APIConfig:
        """Get API configuration."""
        return self._api

    @property
    def ui(self) -> UIConfig:
        """Get UI configuration."""
        return self._ui

    @property
    def security(self) -> SecurityConfig:
        """Get security configuration."""
        return self._security

    def get_required_credits(self, model: str, resolution: str) -> Optional[int]:
        """
        Get required credits for a specific model and resolution.

        Args:
            model: Model identifier (e.g., "hitem3dv1.5")
            resolution: Resolution identifier (e.g., "1024")

        Returns:
            Credit cost or None if not found
        """
        model_costs = self._api.credit_costs.get(model, {})
        return model_costs.get(resolution)

    def is_valid_quality(self, quality: str) -> bool:
        """Check if quality level is valid."""
        return quality in self._processing.available_qualities

    def is_supported_image_format(self, filepath: str) -> bool:
        """Check if file extension is a supported image format."""
        return any(
            filepath.lower().endswith(ext) for ext in self._ui.supported_image_formats
        )


# Global configuration instance
config = ConfigManager()


def get_output_dir() -> Path:
    """
    Get the user-writable output directory for 3D models.

    Returns a path in the user's Documents folder to avoid permission issues
    when the app is installed in restricted locations (Program Files).

    Returns:
        Path to the output directory (created if it doesn't exist)
    """
    env_dir = os.getenv("TRIVOXAI_OUTPUT_DIR") or os.getenv("IMAGETO3D_OUTPUT_DIR")
    if env_dir:
        output_dir = Path(env_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    # Use user's Local AppData folder for secure, hidden storage
    if os.name == "nt":  # Windows
        secure_path = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "VoxelCraft" / "SecureStorage"
    else:  # macOS/Linux
        secure_path = Path.home() / ".VoxelCraft" / "secure_storage"

    output_dir = secure_path

    # Create the directory if it doesn't exist
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fallback to a temp directory if AppData is not writable
        import tempfile

        output_dir = Path(tempfile.gettempdir()) / "TrivoxAI_Secure_Output"
        output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir


# Convenience exports
__all__ = [
    "config",
    "ConfigManager",
    "ProcessingConfig",
    "APIConfig",
    "UIConfig",
    "SecurityConfig",
    "get_output_dir",
    "get_settings",
]


def get_settings() -> ConfigManager:
    """
    Get the global configuration manager instance.

    Returns:
        The ConfigManager singleton instance
    """
    return config
