"""
Command-line interface for huggingface-tools.

Provides subcommands for downloading models and datasets from HuggingFace Hub.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from huggingface_tools import __version__
from huggingface_tools.logging_config import setup_logging, get_logger
from huggingface_tools.models import download_models, ModelDownloadError
from huggingface_tools.datasets import download_datasets, DatasetDownloadError


def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='huggingface-tools',
        description='Utilities for managing HuggingFace models and datasets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download models from default config
  huggingface-tools download-models

  # Download models with custom config
  huggingface-tools download-models --config my-models.json --model-home /data/models

  # Download datasets
  huggingface-tools download-datasets --verbose

  # Force re-download all datasets
  huggingface-tools download-datasets --force

For more information, visit: https://github.com/yourusername/huggingface-tools
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )

    parser.add_argument(
        '--log-file',
        type=Path,
        help='Write logs to specified file'
    )

    parser.add_argument(
        '--env-file',
        type=Path,
        default=Path('.env'),
        help='Path to .env file (default: .env)'
    )

    # Create subparsers for subcommands
    subparsers = parser.add_subparsers(
        title='subcommands',
        description='Available commands',
        dest='command',
        required=True
    )

    # Subcommand: download-models
    models_parser = subparsers.add_parser(
        'download-models',
        help='Download models from HuggingFace Hub',
        description='Download GGUF and other models from HuggingFace Hub based on a JSON configuration file'
    )

    models_parser.add_argument(
        '--config',
        type=Path,
        help='Path to models JSON config file (default: from MODEL_FILE_LIST env var or models.json)'
    )

    models_parser.add_argument(
        '--model-home',
        type=Path,
        help='Base directory for storing models (default: from MODEL_HOME env var)'
    )

    models_parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-download even if files already exist'
    )

    # Subcommand: download-datasets
    datasets_parser = subparsers.add_parser(
        'download-datasets',
        help='Download datasets from HuggingFace Hub',
        description='Download datasets from HuggingFace Hub based on a JSON configuration file'
    )

    datasets_parser.add_argument(
        '--config',
        type=Path,
        help='Path to datasets JSON config file (default: from DATASET_FILE_LIST env var or datasets.json)'
    )

    datasets_parser.add_argument(
        '--dataset-home',
        type=Path,
        help='Base directory for storing datasets (default: from MODEL_HOME env var)'
    )

    datasets_parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-download even if datasets already exist'
    )

    datasets_parser.add_argument(
        '--max-workers',
        type=int,
        default=8,
        help='Number of concurrent download threads (default: 8)'
    )

    return parser


def handle_download_models(args: argparse.Namespace, logger) -> int:
    """
    Handle the download-models subcommand.

    Args:
        args: Parsed command-line arguments
        logger: Logger instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info("Starting model download process")

        stats = download_models(
            config_file=args.config,
            model_home=args.model_home,
            force_download=args.force
        )

        # Print summary
        print("\n" + "="*50)
        print("MODEL DOWNLOAD SUMMARY")
        print("="*50)
        print(f"Total models:      {stats['total']}")
        print(f"Downloaded:        {stats['downloaded']}")
        print(f"Skipped:           {stats['skipped']}")
        print(f"Failed:            {stats['failed']}")
        print("="*50)

        if stats['failed'] > 0:
            logger.warning("Some models failed to download. Check logs for details.")
            return 1

        logger.info("Model download completed successfully")
        return 0

    except ModelDownloadError as e:
        logger.error(f"Model download failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def handle_download_datasets(args: argparse.Namespace, logger) -> int:
    """
    Handle the download-datasets subcommand.

    Args:
        args: Parsed command-line arguments
        logger: Logger instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info("Starting dataset download process")

        stats = download_datasets(
            config_file=args.config,
            dataset_home=args.dataset_home,
            force_download=args.force,
            max_workers=args.max_workers
        )

        # Print summary
        print("\n" + "="*50)
        print("DATASET DOWNLOAD SUMMARY")
        print("="*50)
        print(f"Total datasets:    {stats['total']}")
        print(f"Downloaded:        {stats['downloaded']}")
        print(f"Skipped:           {stats['skipped']}")
        print(f"Failed:            {stats['failed']}")
        print("="*50)

        if stats['failed'] > 0:
            logger.warning("Some datasets failed to download. Check logs for details.")
            return 1

        logger.info("Dataset download completed successfully")
        return 0

    except DatasetDownloadError as e:
        logger.error(f"Dataset download failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command-line arguments (default: sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Load environment variables from .env file
    if args.env_file.exists():
        load_dotenv(args.env_file)
    else:
        # Try to load from scripts/.env as fallback
        scripts_env = Path(__file__).parent.parent / 'scripts' / '.env'
        if scripts_env.exists():
            load_dotenv(scripts_env)

    # Setup logging
    logger = setup_logging(
        level='DEBUG' if args.verbose else 'INFO',
        log_file=args.log_file,
        verbose=args.verbose
    )

    logger.debug(f"Command-line arguments: {args}")

    # Dispatch to appropriate subcommand handler
    if args.command == 'download-models':
        return handle_download_models(args, logger)
    elif args.command == 'download-datasets':
        return handle_download_datasets(args, logger)
    else:
        logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
