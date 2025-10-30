"""
Model management functionality for downloading HuggingFace models.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from huggingface_hub import hf_hub_download
from huggingface_hub.utils import HfHubHTTPError

from huggingface_tools.logging_config import get_logger
from huggingface_tools.security import (
    validate_path,
    get_secure_env_var,
    validate_huggingface_repo_id,
    check_disk_space,
    mask_token_in_url
)

logger = get_logger(__name__)


class ModelDownloadError(Exception):
    """Raised when model download fails."""
    pass


def load_model_config(config_file: Path) -> List[Dict]:
    """
    Load model configuration from JSON file.

    Args:
        config_file: Path to JSON configuration file

    Returns:
        List of model configurations

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    try:
        config_path = validate_path(config_file, must_exist=True)
        logger.info(f"Loading model configuration from {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        models = data.get('models', [])
        logger.info(f"Loaded {len(models)} model configurations")

        return models

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file {config_file}: {e}")
        raise
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_file}")
        raise


def download_model_file(
    model_id: str,
    filename: str,
    model_home: Path,
    force_download: bool = False
) -> Optional[str]:
    """
    Download a single model file from HuggingFace Hub.

    Args:
        model_id: HuggingFace model repository ID
        filename: Specific file to download from the model
        model_home: Base directory for storing models
        force_download: If True, re-download even if file exists

    Returns:
        Path to downloaded file, or None if skipped

    Raises:
        ModelDownloadError: If download fails
    """
    # Validate repository ID
    if not validate_huggingface_repo_id(model_id):
        raise ModelDownloadError(f"Invalid repository ID: {model_id}")

    # Construct local file path
    model_dir = model_home / model_id
    local_file_path = model_dir / filename

    # Check if file already exists
    if local_file_path.exists() and not force_download:
        logger.info(f"File '{filename}' for model '{model_id}' already exists. Skipping...")
        return None

    try:
        # Create model directory if it doesn't exist
        model_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {model_dir}")

        # Estimate required space (rough estimate: 10GB for models)
        # In production, you might want to check file size via API first
        if not check_disk_space(model_home, 10 * 1024**3):  # 10 GB minimum
            logger.warning("Low disk space, but proceeding with download...")

        logger.info(f"Downloading '{filename}' for model '{model_id}'...")

        # Download the file
        downloaded_path = hf_hub_download(
            repo_id=model_id,
            filename=filename,
            cache_dir=str(model_dir)
        )

        logger.info(f"Successfully downloaded '{filename}' to {downloaded_path}")
        return downloaded_path

    except HfHubHTTPError as e:
        if e.response.status_code == 401:
            logger.error(
                f"Authentication failed for model '{model_id}'. "
                "This may be a gated model. Please set HF_TOKEN environment variable."
            )
        elif e.response.status_code == 404:
            logger.error(
                f"Model '{model_id}' or file '{filename}' not found. "
                "Please check the repository ID and filename."
            )
        else:
            logger.error(f"HTTP error downloading '{filename}': {e}")
        raise ModelDownloadError(f"Failed to download {filename}: {e}") from e

    except Exception as e:
        logger.error(f"Unexpected error downloading '{filename}': {e}")
        raise ModelDownloadError(f"Failed to download {filename}: {e}") from e


def download_models(
    config_file: Optional[Path] = None,
    model_home: Optional[Path] = None,
    force_download: bool = False
) -> Dict[str, int]:
    """
    Download multiple models based on configuration file.

    Args:
        config_file: Path to JSON config file (default: models.json)
        model_home: Base directory for models (default: from MODEL_HOME env var)
        force_download: If True, re-download existing files

    Returns:
        Dictionary with download statistics

    Raises:
        ModelDownloadError: If required configuration is missing
    """
    # Get model home directory
    if model_home is None:
        model_home_str = get_secure_env_var('MODEL_HOME', required=True)
        model_home = Path(model_home_str)

    model_home = validate_path(model_home)

    # Create model home directory if it doesn't exist
    model_home.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using model home directory: {model_home}")

    # Determine config file path
    if config_file is None:
        config_file_str = get_secure_env_var('MODEL_FILE_LIST', default='models.json')
        config_file = Path(config_file_str)

        # If relative path, look in scripts directory first, then current directory
        if not config_file.is_absolute():
            scripts_config = Path(__file__).parent.parent / 'scripts' / config_file
            if scripts_config.exists():
                config_file = scripts_config
            elif not config_file.exists():
                # Try current directory
                config_file = Path.cwd() / config_file

    # Load models configuration
    models = load_model_config(config_file)

    # Track statistics
    stats = {
        'total': 0,
        'downloaded': 0,
        'skipped': 0,
        'failed': 0
    }

    # Download each model
    for model in models:
        model_id = model.get('id')
        files = model.get('files', [])
        description = model.get('description', '')

        if not model_id:
            logger.warning("Model entry missing 'id' field, skipping")
            continue

        logger.info(f"Processing model: {model_id}")
        if description:
            logger.info(f"Description: {description}")

        for filename in files:
            stats['total'] += 1

            try:
                result = download_model_file(
                    model_id=model_id,
                    filename=filename,
                    model_home=model_home,
                    force_download=force_download
                )

                if result:
                    stats['downloaded'] += 1
                else:
                    stats['skipped'] += 1

            except ModelDownloadError as e:
                logger.error(f"Failed to download {filename}: {e}")
                stats['failed'] += 1
                # Continue with other files

    # Log summary
    logger.info(
        f"Download complete. Total: {stats['total']}, "
        f"Downloaded: {stats['downloaded']}, "
        f"Skipped: {stats['skipped']}, "
        f"Failed: {stats['failed']}"
    )

    return stats
