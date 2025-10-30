"""
Dataset management functionality for downloading HuggingFace datasets.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from huggingface_hub import snapshot_download
from huggingface_hub.utils import HfHubHTTPError

from huggingface_tools.logging_config import get_logger
from huggingface_tools.security import (
    validate_path,
    get_secure_env_var,
    validate_huggingface_repo_id,
    check_disk_space
)

logger = get_logger(__name__)


class DatasetDownloadError(Exception):
    """Raised when dataset download fails."""
    pass


def load_dataset_config(config_file: Path) -> List[Dict]:
    """
    Load dataset configuration from JSON file.

    Args:
        config_file: Path to JSON configuration file

    Returns:
        List of dataset configurations

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    try:
        config_path = validate_path(config_file, must_exist=True)
        logger.info(f"Loading dataset configuration from {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        datasets = data.get('datasets', [])
        logger.info(f"Loaded {len(datasets)} dataset configurations")

        return datasets

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file {config_file}: {e}")
        raise
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_file}")
        raise


def download_dataset(
    dataset_id: str,
    dataset_home: Path,
    force_download: bool = False,
    max_workers: int = 8
) -> Optional[str]:
    """
    Download a dataset from HuggingFace Hub.

    Args:
        dataset_id: HuggingFace dataset repository ID
        dataset_home: Base directory for storing datasets
        force_download: If True, re-download even if dataset exists
        max_workers: Number of concurrent download threads

    Returns:
        Path to downloaded dataset, or None if skipped

    Raises:
        DatasetDownloadError: If download fails
    """
    # Validate repository ID
    if not validate_huggingface_repo_id(dataset_id):
        raise DatasetDownloadError(f"Invalid repository ID: {dataset_id}")

    # Construct local dataset path
    dataset_dir = dataset_home / dataset_id

    # Check if dataset already exists
    if dataset_dir.exists() and not force_download:
        # Check if directory is not empty
        if any(dataset_dir.iterdir()):
            logger.info(f"Dataset '{dataset_id}' already exists. Skipping...")
            return None

    try:
        # Create dataset directory if it doesn't exist
        dataset_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {dataset_dir}")

        # Check disk space (datasets can be very large, check for 50GB minimum)
        if not check_disk_space(dataset_home, 50 * 1024**3):  # 50 GB minimum
            logger.warning("Low disk space, but proceeding with download...")

        logger.info(f"Downloading dataset '{dataset_id}'...")

        # Download the dataset using snapshot_download
        downloaded_path = snapshot_download(
            repo_id=dataset_id,
            cache_dir=str(dataset_dir),
            repo_type='dataset',
            max_workers=max_workers
        )

        logger.info(f"Successfully downloaded dataset '{dataset_id}' to {downloaded_path}")
        return downloaded_path

    except HfHubHTTPError as e:
        if e.response.status_code == 401:
            logger.error(
                f"Authentication failed for dataset '{dataset_id}'. "
                "This may be a gated dataset. Please set HF_TOKEN environment variable."
            )
        elif e.response.status_code == 404:
            logger.error(
                f"Dataset '{dataset_id}' not found. "
                "Please check the repository ID."
            )
        else:
            logger.error(f"HTTP error downloading dataset '{dataset_id}': {e}")
        raise DatasetDownloadError(f"Failed to download {dataset_id}: {e}") from e

    except Exception as e:
        logger.error(f"Unexpected error downloading dataset '{dataset_id}': {e}")
        raise DatasetDownloadError(f"Failed to download {dataset_id}: {e}") from e


def download_datasets(
    config_file: Optional[Path] = None,
    dataset_home: Optional[Path] = None,
    force_download: bool = False,
    max_workers: int = 8
) -> Dict[str, int]:
    """
    Download multiple datasets based on configuration file.

    Args:
        config_file: Path to JSON config file (default: datasets.json)
        dataset_home: Base directory for datasets (default: from MODEL_HOME env var)
        force_download: If True, re-download existing datasets
        max_workers: Number of concurrent download threads

    Returns:
        Dictionary with download statistics

    Raises:
        DatasetDownloadError: If required configuration is missing
    """
    # Get dataset home directory (uses MODEL_HOME for compatibility)
    if dataset_home is None:
        dataset_home_str = get_secure_env_var('MODEL_HOME', required=True)
        dataset_home = Path(dataset_home_str)

    dataset_home = validate_path(dataset_home)

    # Create dataset home directory if it doesn't exist
    dataset_home.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using dataset home directory: {dataset_home}")

    # Determine config file path
    if config_file is None:
        config_file_str = get_secure_env_var('DATASET_FILE_LIST', default='datasets.json')
        config_file = Path(config_file_str)

        # If relative path, look in scripts directory first, then current directory
        if not config_file.is_absolute():
            scripts_config = Path(__file__).parent.parent / 'scripts' / config_file
            if scripts_config.exists():
                config_file = scripts_config
            elif not config_file.exists():
                # Try current directory
                config_file = Path.cwd() / config_file

    # Load datasets configuration
    datasets = load_dataset_config(config_file)

    # Track statistics
    stats = {
        'total': 0,
        'downloaded': 0,
        'skipped': 0,
        'failed': 0
    }

    # Download each dataset
    for dataset in datasets:
        dataset_id = dataset.get('id')
        description = dataset.get('description', '')

        if not dataset_id:
            logger.warning("Dataset entry missing 'id' field, skipping")
            continue

        logger.info(f"Processing dataset: {dataset_id}")
        if description:
            logger.info(f"Description: {description}")

        stats['total'] += 1

        try:
            result = download_dataset(
                dataset_id=dataset_id,
                dataset_home=dataset_home,
                force_download=force_download,
                max_workers=max_workers
            )

            if result:
                stats['downloaded'] += 1
            else:
                stats['skipped'] += 1

        except DatasetDownloadError as e:
            logger.error(f"Failed to download {dataset_id}: {e}")
            stats['failed'] += 1
            # Continue with other datasets

    # Log summary
    logger.info(
        f"Download complete. Total: {stats['total']}, "
        f"Downloaded: {stats['downloaded']}, "
        f"Skipped: {stats['skipped']}, "
        f"Failed: {stats['failed']}"
    )

    return stats
