"""
Security utilities for huggingface-tools.

Provides functions for secure environment variable handling,
path validation, and other security best practices.
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict
from huggingface_tools.logging_config import get_logger

logger = get_logger(__name__)


class SecurityError(Exception):
    """Raised when a security violation is detected."""
    pass


def validate_path(path: Path, must_exist: bool = False) -> Path:
    """
    Validate and sanitize a file path.

    Args:
        path: Path to validate
        must_exist: If True, raise error if path doesn't exist

    Returns:
        Resolved absolute path

    Raises:
        SecurityError: If path validation fails
        FileNotFoundError: If must_exist=True and path doesn't exist
    """
    try:
        # Resolve to absolute path and resolve any symlinks
        resolved_path = path.resolve()

        # Check for path traversal attempts
        if ".." in path.parts:
            logger.warning(f"Path traversal attempt detected: {path}")
            raise SecurityError(f"Path traversal not allowed: {path}")

        # Verify the path is within allowed boundaries
        # (This is a basic check; adjust based on your security requirements)
        if must_exist and not resolved_path.exists():
            raise FileNotFoundError(f"Path does not exist: {resolved_path}")

        return resolved_path

    except (OSError, RuntimeError) as e:
        logger.error(f"Path validation failed for {path}: {e}")
        raise SecurityError(f"Invalid path: {path}") from e


def get_secure_env_var(
    var_name: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
    """
    Securely retrieve an environment variable.

    Args:
        var_name: Name of the environment variable
        default: Default value if not set
        required: If True, raise error if not set

    Returns:
        Environment variable value or default

    Raises:
        SecurityError: If required variable is not set
    """
    value = os.environ.get(var_name, default)

    if required and value is None:
        logger.error(f"Required environment variable {var_name} is not set")
        raise SecurityError(f"Required environment variable {var_name} is not set")

    if value:
        logger.debug(f"Retrieved environment variable {var_name}")

    return value


def validate_huggingface_repo_id(repo_id: str) -> bool:
    """
    Validate a HuggingFace repository ID format.

    Args:
        repo_id: Repository ID to validate (e.g., "username/model-name")

    Returns:
        True if valid, False otherwise
    """
    # HuggingFace repo IDs should follow the pattern: username/repo-name
    # Allow alphanumeric, hyphens, underscores, and dots
    pattern = r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9._-]+$'

    if not re.match(pattern, repo_id):
        logger.warning(f"Invalid repository ID format: {repo_id}")
        return False

    return True


def validate_s3_bucket_name(bucket: str) -> bool:
    """
    Validate an S3 bucket name against AWS naming rules.

    Args:
        bucket: Bucket name to validate

    Returns:
        True if valid, False otherwise
    """
    # AWS rules: 3-63 chars, lowercase letters/digits/hyphens/dots,
    # must start and end with a letter or digit, no consecutive dots,
    # not formatted as an IP address.
    if not (3 <= len(bucket) <= 63):
        logger.warning(f"Invalid S3 bucket name length: {bucket}")
        return False

    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', bucket):
        logger.warning(f"Invalid S3 bucket name format: {bucket}")
        return False

    if '..' in bucket:
        logger.warning(f"Invalid S3 bucket name (consecutive dots): {bucket}")
        return False

    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', bucket):
        logger.warning(f"S3 bucket name must not be an IP address: {bucket}")
        return False

    return True


def sanitize_s3_prefix(prefix: str) -> str:
    """
    Normalize an S3 key prefix.

    Strips leading slashes and collapses path traversal markers so the
    prefix cannot escape its intended location in the bucket.

    Args:
        prefix: Raw prefix string

    Returns:
        Normalized prefix (no leading slash, single trailing slash if non-empty)
    """
    # Drop null bytes and leading slashes; reject traversal segments.
    prefix = prefix.replace('\x00', '').lstrip('/')

    parts = [p for p in prefix.split('/') if p not in ('', '.', '..')]
    normalized = '/'.join(parts)

    if normalized:
        normalized += '/'

    return normalized


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent directory traversal and other attacks.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename
    """
    # Remove any directory components
    filename = os.path.basename(filename)

    # Remove null bytes
    filename = filename.replace('\x00', '')

    # Remove or replace dangerous characters
    # Allow alphanumeric, dots, hyphens, and underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Prevent hidden files (starting with dot)
    if filename.startswith('.'):
        filename = '_' + filename[1:]

    # Prevent empty filename
    if not filename:
        filename = 'unnamed_file'

    return filename


def check_disk_space(path: Path, required_bytes: int) -> bool:
    """
    Check if sufficient disk space is available.

    Args:
        path: Path to check disk space for
        required_bytes: Required space in bytes

    Returns:
        True if sufficient space available, False otherwise
    """
    try:
        stat = os.statvfs(path)
        available_bytes = stat.f_bavail * stat.f_frsize

        if available_bytes < required_bytes:
            logger.warning(
                f"Insufficient disk space. Required: {required_bytes / (1024**3):.2f} GB, "
                f"Available: {available_bytes / (1024**3):.2f} GB"
            )
            return False

        return True
    except (OSError, AttributeError) as e:
        logger.error(f"Could not check disk space: {e}")
        return True  # Proceed with caution if we can't check


def mask_token_in_url(url: str) -> str:
    """
    Mask authentication tokens in URLs for safe logging.

    Args:
        url: URL that may contain authentication tokens

    Returns:
        URL with masked tokens
    """
    # Mask HuggingFace tokens
    url = re.sub(r'hf_[a-zA-Z0-9]{20,}', '[REDACTED_TOKEN]', url)

    # Mask tokens in query parameters
    url = re.sub(r'([?&]token=)[^&]+', r'\1[REDACTED]', url)
    url = re.sub(r'([?&]api_key=)[^&]+', r'\1[REDACTED]', url)

    return url


def get_safe_env_display() -> Dict[str, str]:
    """
    Get environment variables safe for display (with sensitive data masked).

    Returns:
        Dictionary of environment variables with sensitive values masked
    """
    safe_vars = {}
    sensitive_keywords = ['token', 'key', 'secret', 'password', 'auth']

    for key, value in os.environ.items():
        # Check if key contains sensitive keywords
        is_sensitive = any(keyword in key.lower() for keyword in sensitive_keywords)

        if is_sensitive:
            safe_vars[key] = '[REDACTED]'
        else:
            safe_vars[key] = value

    return safe_vars
