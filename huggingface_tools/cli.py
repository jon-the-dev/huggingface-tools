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
from huggingface_tools.s3_sync import sync_to_s3, S3SyncError


def add_s3_sync_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add S3 sync options to a download subparser.

    These options let a download command upload its results to S3 in the
    same invocation. The sync runs only when --sync-s3 is provided.

    Args:
        parser: Subparser to attach the arguments to
    """
    group = parser.add_argument_group('S3 sync options')

    group.add_argument(
        '--sync-s3',
        action='store_true',
        help='After downloading, sync the local directory to an S3 bucket'
    )

    group.add_argument(
        '--s3-bucket',
        help='Target S3 bucket name (default: from S3_BUCKET env var)'
    )

    group.add_argument(
        '--s3-prefix',
        help='Key prefix within the bucket (default: from S3_PREFIX env var)'
    )

    group.add_argument(
        '--s3-region',
        help='AWS region for the S3 client (default: from AWS_REGION env var)'
    )

    group.add_argument(
        '--s3-endpoint-url',
        help='Custom S3 endpoint URL for S3-compatible stores'
    )

    group.add_argument(
        '--s3-force',
        action='store_true',
        help='Re-upload files to S3 even if they already exist'
    )


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

    add_s3_sync_arguments(models_parser)

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

    add_s3_sync_arguments(datasets_parser)

    # Subcommand: sync-s3
    sync_parser = subparsers.add_parser(
        'sync-s3',
        help='Sync a local directory of models/datasets to S3',
        description=(
            'Upload the contents of a local directory to an S3 bucket so '
            'the models and datasets can be consumed from AWS. Uses the '
            'standard boto3 credential chain (env vars, shared credentials '
            'file, or IAM role).'
        )
    )

    sync_parser.add_argument(
        '--local-dir',
        type=Path,
        help='Local directory to upload (default: from MODEL_HOME env var)'
    )

    sync_parser.add_argument(
        '--s3-bucket',
        help='Target S3 bucket name (default: from S3_BUCKET env var)'
    )

    sync_parser.add_argument(
        '--s3-prefix',
        help='Key prefix within the bucket (default: from S3_PREFIX env var)'
    )

    sync_parser.add_argument(
        '--s3-region',
        help='AWS region for the S3 client (default: from AWS_REGION env var)'
    )

    sync_parser.add_argument(
        '--s3-endpoint-url',
        help='Custom S3 endpoint URL for S3-compatible stores'
    )

    sync_parser.add_argument(
        '--s3-force',
        action='store_true',
        help='Re-upload files even if they already exist in the bucket'
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

        download_rc = 0
        if stats['failed'] > 0:
            logger.warning("Some models failed to download. Check logs for details.")
            download_rc = 1
        else:
            logger.info("Model download completed successfully")

        if getattr(args, 'sync_s3', False):
            sync_rc = run_s3_sync(args, logger, local_dir=args.model_home)
            return download_rc or sync_rc

        return download_rc

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

        download_rc = 0
        if stats['failed'] > 0:
            logger.warning("Some datasets failed to download. Check logs for details.")
            download_rc = 1
        else:
            logger.info("Dataset download completed successfully")

        if getattr(args, 'sync_s3', False):
            sync_rc = run_s3_sync(args, logger, local_dir=args.dataset_home)
            return download_rc or sync_rc

        return download_rc

    except DatasetDownloadError as e:
        logger.error(f"Dataset download failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def run_s3_sync(args: argparse.Namespace, logger, local_dir: Optional[Path] = None) -> int:
    """
    Run an S3 sync using the S3 options on the parsed args.

    Args:
        args: Parsed command-line arguments (must have s3_* attributes)
        logger: Logger instance
        local_dir: Directory to upload (overrides args/env when provided)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        logger.info("Starting S3 sync")

        stats = sync_to_s3(
            local_dir=local_dir or getattr(args, 'local_dir', None),
            bucket=args.s3_bucket,
            prefix=args.s3_prefix,
            region=args.s3_region,
            endpoint_url=args.s3_endpoint_url,
            force=args.s3_force,
        )

        print("\n" + "="*50)
        print("S3 SYNC SUMMARY")
        print("="*50)
        print(f"Total files:       {stats['total']}")
        print(f"Uploaded:          {stats['uploaded']}")
        print(f"Skipped:           {stats['skipped']}")
        print(f"Failed:            {stats['failed']}")
        print("="*50)

        if stats['failed'] > 0:
            logger.warning("Some files failed to sync. Check logs for details.")
            return 1

        logger.info("S3 sync completed successfully")
        return 0

    except S3SyncError as e:
        logger.error(f"S3 sync failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during S3 sync: {e}", exc_info=True)
        return 1


def handle_sync_s3(args: argparse.Namespace, logger) -> int:
    """
    Handle the sync-s3 subcommand.

    Args:
        args: Parsed command-line arguments
        logger: Logger instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    return run_s3_sync(args, logger)


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
    elif args.command == 'sync-s3':
        return handle_sync_s3(args, logger)
    else:
        logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
