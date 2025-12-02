"""
Logging configuration for huggingface-tools.

Provides centralized logging setup with security-aware practices.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """
    Filter to redact sensitive information from logs.

    This filter searches for common patterns of sensitive data
    (API keys, tokens, passwords) and redacts them.
    """

    SENSITIVE_PATTERNS = [
        'token=',
        'api_key=',
        'password=',
        'secret=',
        'authorization:',
        'hf_',  # HuggingFace token prefix
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive information from log messages."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            msg_lower = record.msg.lower()
            for pattern in self.SENSITIVE_PATTERNS:
                if pattern.lower() in msg_lower:
                    # Redact the sensitive information
                    record.msg = self._redact_sensitive(record.msg)
        return True

    def _redact_sensitive(self, message: str) -> str:
        """Replace sensitive data with [REDACTED]."""
        import re
        # Redact HuggingFace tokens (hf_...)
        message = re.sub(r'hf_[a-zA-Z0-9]{20,}', '[REDACTED_TOKEN]', message)
        # Redact other potential secrets (anything after sensitive keywords)
        for pattern in ['token=', 'api_key=', 'password=', 'secret=']:
            message = re.sub(
                f'{pattern}[^\\s]+',
                f'{pattern}[REDACTED]',
                message,
                flags=re.IGNORECASE
            )
        return message


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    verbose: bool = False
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        verbose: If True, set level to DEBUG

    Returns:
        Configured logger instance
    """
    # Determine logging level
    if verbose:
        level = "DEBUG"

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger("huggingface_tools")
    logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            # Ensure log directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Use RotatingFileHandler to prevent log files from growing indefinitely
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(SensitiveDataFilter())
            logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not create log file {log_file}: {e}")

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str = "huggingface_tools") -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (default: "huggingface_tools")

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
