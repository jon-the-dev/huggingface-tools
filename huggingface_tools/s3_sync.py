"""
S3 sync functionality for huggingface-tools.

Uploads (syncs) locally downloaded models and datasets to an Amazon S3
bucket so they can be consumed from AWS (e.g. SageMaker, EC2, EKS).

Uses the standard boto3 credential resolution chain (environment
variables, shared credentials file, IAM role, etc.). Credentials are
never read from or written to the package itself.
"""

from pathlib import Path
from typing import Dict, Optional

try:
    import boto3
    from boto3.s3.transfer import TransferConfig
    from botocore.exceptions import BotoCoreError, ClientError
    _BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without boto3 installed
    _BOTO3_AVAILABLE = False
    boto3 = None  # type: ignore[assignment]
    TransferConfig = None  # type: ignore[assignment,misc]
    BotoCoreError = ClientError = Exception  # type: ignore[assignment,misc]

from huggingface_tools.logging_config import get_logger
from huggingface_tools.security import (
    validate_path,
    validate_s3_bucket_name,
    sanitize_s3_prefix,
    get_secure_env_var,
)

logger = get_logger(__name__)

# Multipart threshold/chunk size tuned for large model/dataset files.
_MULTIPART_THRESHOLD = 64 * 1024**2  # 64 MB
_MULTIPART_CHUNKSIZE = 64 * 1024**2  # 64 MB


class S3SyncError(Exception):
    """Raised when an S3 sync operation fails."""
    pass


def _require_boto3() -> None:
    """Raise a helpful error if boto3 is not installed."""
    if not _BOTO3_AVAILABLE:
        raise S3SyncError(
            "boto3 is required for S3 sync. Install it with: "
            "pip install 'huggingface-tools[s3]' or pip install boto3"
        )


def _build_s3_key(prefix: str, relative_path: Path) -> str:
    """
    Build an S3 object key from a prefix and a relative file path.

    Uses forward slashes regardless of host OS so keys are consistent.
    """
    rel = '/'.join(relative_path.parts)
    return f"{prefix}{rel}"


def _should_upload(
    s3_client,
    bucket: str,
    key: str,
    local_size: int,
    force: bool,
) -> bool:
    """
    Decide whether a local file needs uploading.

    Skips upload when an object with a matching size already exists in the
    bucket (unless force=True). Size is a cheap, deterministic check; HF
    files are content-addressed so a size match is a strong signal.
    """
    if force:
        return True

    try:
        head = s3_client.head_object(Bucket=bucket, Key=key)
        if head.get('ContentLength') == local_size:
            return False
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code in ('404', 'NoSuchKey', 'NotFound'):
            return True
        # Any other error (e.g. 403) should surface to the caller.
        raise


def sync_directory_to_s3(
    local_dir: Path,
    bucket: str,
    prefix: str = '',
    region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    force: bool = False,
) -> Dict[str, int]:
    """
    Sync (upload) the contents of a local directory to an S3 bucket.

    Args:
        local_dir: Local directory to upload
        bucket: Target S3 bucket name
        prefix: Key prefix within the bucket (acts as a "folder")
        region: AWS region for the S3 client (default: from env/AWS config)
        endpoint_url: Custom S3 endpoint (for S3-compatible stores)
        force: If True, re-upload files even if they already exist

    Returns:
        Dictionary with sync statistics (total, uploaded, skipped, failed)

    Raises:
        S3SyncError: If the bucket name is invalid or the directory is missing
    """
    _require_boto3()

    if not validate_s3_bucket_name(bucket):
        raise S3SyncError(f"Invalid S3 bucket name: {bucket}")

    local_dir = validate_path(local_dir, must_exist=True)
    if not local_dir.is_dir():
        raise S3SyncError(f"Local path is not a directory: {local_dir}")

    prefix = sanitize_s3_prefix(prefix)

    s3_client = boto3.client(
        's3',
        region_name=region or get_secure_env_var('AWS_REGION'),
        endpoint_url=endpoint_url or get_secure_env_var('S3_ENDPOINT_URL'),
    )

    transfer_config = TransferConfig(
        multipart_threshold=_MULTIPART_THRESHOLD,
        multipart_chunksize=_MULTIPART_CHUNKSIZE,
        use_threads=True,
    )

    stats = {'total': 0, 'uploaded': 0, 'skipped': 0, 'failed': 0}

    logger.info(
        f"Syncing '{local_dir}' to s3://{bucket}/{prefix} "
        f"(force={force})"
    )

    for file_path in sorted(local_dir.rglob('*')):
        if not file_path.is_file():
            continue

        stats['total'] += 1
        relative_path = file_path.relative_to(local_dir)
        key = _build_s3_key(prefix, relative_path)
        local_size = file_path.stat().st_size

        try:
            if not _should_upload(s3_client, bucket, key, local_size, force):
                logger.info(f"Skipping (already in sync): s3://{bucket}/{key}")
                stats['skipped'] += 1
                continue

            logger.info(f"Uploading {file_path} -> s3://{bucket}/{key}")
            s3_client.upload_file(
                Filename=str(file_path),
                Bucket=bucket,
                Key=key,
                Config=transfer_config,
            )
            stats['uploaded'] += 1

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload {file_path} to s3://{bucket}/{key}: {e}")
            stats['failed'] += 1
            # Continue with remaining files.

    logger.info(
        f"S3 sync complete. Total: {stats['total']}, "
        f"Uploaded: {stats['uploaded']}, "
        f"Skipped: {stats['skipped']}, "
        f"Failed: {stats['failed']}"
    )

    return stats


def sync_to_s3(
    local_dir: Optional[Path] = None,
    bucket: Optional[str] = None,
    prefix: Optional[str] = None,
    region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
    force: bool = False,
) -> Dict[str, int]:
    """
    Sync a local directory to S3, resolving defaults from environment.

    Falls back to these environment variables when arguments are omitted:
      - local_dir : MODEL_HOME
      - bucket    : S3_BUCKET
      - prefix    : S3_PREFIX
      - region    : AWS_REGION

    Args:
        local_dir: Local directory to upload (default: from MODEL_HOME)
        bucket: Target S3 bucket (default: from S3_BUCKET)
        prefix: Key prefix (default: from S3_PREFIX)
        region: AWS region (default: from AWS_REGION)
        endpoint_url: Custom S3 endpoint (default: from S3_ENDPOINT_URL)
        force: If True, re-upload files even if they already exist

    Returns:
        Dictionary with sync statistics

    Raises:
        S3SyncError: If required configuration is missing
    """
    _require_boto3()

    if local_dir is None:
        local_dir = Path(str(get_secure_env_var('MODEL_HOME', required=True)))

    if bucket is None:
        bucket = str(get_secure_env_var('S3_BUCKET', required=True))

    if prefix is None:
        prefix = get_secure_env_var('S3_PREFIX', default='') or ''

    return sync_directory_to_s3(
        local_dir=local_dir,
        bucket=bucket,
        prefix=prefix,
        region=region,
        endpoint_url=endpoint_url,
        force=force,
    )
