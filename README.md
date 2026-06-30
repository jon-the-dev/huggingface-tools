# huggingface-tools

A Python package for managing HuggingFace models and datasets with built-in security and logging best practices.

## Features

- **Easy Model Management**: Download GGUF and other models from HuggingFace Hub
- **Dataset Management**: Batch download datasets from HuggingFace Hub
- **S3 Sync**: Upload downloaded models and datasets to Amazon S3 for use in AWS (SageMaker, EC2, EKS)
- **Configuration-Based**: Use JSON files to define what to download
- **Security First**: Built-in security features including path validation, token masking, and sensitive data filtering
- **Comprehensive Logging**: Structured logging with sensitive data redaction
- **CLI Interface**: Simple command-line interface with subcommands
- **Error Handling**: Robust error handling with detailed error messages

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/huggingface-tools.git
cd huggingface-tools

# Install in development mode
pip install -e .

# Or install normally
pip install .

# Include S3 sync support (installs boto3)
pip install ".[s3]"
```

### Using pip (once published)

```bash
pip install huggingface-tools

# With S3 sync support
pip install "huggingface-tools[s3]"
```

> **Note:** S3 sync requires `boto3`. It is an optional dependency installed
> via the `[s3]` extra. The download commands work without it; only the
> `sync-s3` subcommand and `--sync-s3` flags need it.

## Configuration

Create a `.env` file in your project directory or in the `scripts/` folder:

```bash
# Required: Base directory for storing models and datasets
MODEL_HOME=/path/to/your/models

# Optional: Custom config file paths
MODEL_FILE_LIST=models.json
DATASET_FILE_LIST=datasets.json

# Optional: HuggingFace token for gated/private models
HF_TOKEN=your_huggingface_token_here

# Optional: S3 sync defaults (used by sync-s3 and --sync-s3)
S3_BUCKET=my-models-bucket
S3_PREFIX=huggingface/
AWS_REGION=us-east-1
# S3_ENDPOINT_URL=https://s3.us-east-1.amazonaws.com  # only for S3-compatible stores
```

> **AWS credentials are never read from this package.** S3 sync uses the
> standard boto3 credential chain: environment variables
> (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`), the
> shared credentials file (`~/.aws/credentials`), or an attached IAM role.
> Do not put AWS secret keys in `.env`; prefer an IAM role or named profile.

### Models Configuration (`models.json`)

```json
{
  "models": [
    {
      "id": "TheBloke/Mixtral-8x7B-Instruct-v0.1-GGUF",
      "description": "Mixtral 8x7B Instruct GGUF",
      "files": [
        "mixtral-8x7b-instruct-v0.1.Q4_K_M.gguf"
      ]
    },
    {
      "id": "google/gemma-7b",
      "description": "Gemma 7B base model",
      "files": [
        "model.safetensors"
      ]
    }
  ]
}
```

### Datasets Configuration (`datasets.json`)

```json
{
  "datasets": [
    {
      "id": "tiiuae/falcon-refinedweb",
      "description": "Falcon RefinedWeb dataset"
    },
    {
      "id": "wikipedia",
      "description": "Wikipedia dataset"
    }
  ]
}
```

## Usage

### Command Line Interface

```bash
# Download models
huggingface-tools download-models

# Download models with custom config
huggingface-tools download-models --config my-models.json --model-home /data/models

# Download models with verbose logging
huggingface-tools download-models --verbose

# Force re-download existing models
huggingface-tools download-models --force

# Download datasets
huggingface-tools download-datasets

# Download datasets with custom settings
huggingface-tools download-datasets --config my-datasets.json --dataset-home /data/datasets

# Download datasets with more workers
huggingface-tools download-datasets --max-workers 16

# Get help
huggingface-tools --help
huggingface-tools download-models --help
huggingface-tools download-datasets --help
huggingface-tools sync-s3 --help
```

### Syncing to S3

Push locally downloaded models and datasets to an S3 bucket so they can be
consumed from AWS. The sync skips files that already exist with a matching
size, so re-running is cheap and incremental.

```bash
# Sync the local MODEL_HOME directory to S3 (bucket/prefix from env)
huggingface-tools sync-s3

# Sync an explicit directory to a specific bucket and prefix
huggingface-tools sync-s3 --local-dir /data/models --s3-bucket my-models-bucket --s3-prefix huggingface/

# Force re-upload of everything
huggingface-tools sync-s3 --s3-force

# Sync to an S3-compatible store in a specific region
huggingface-tools sync-s3 --s3-bucket my-bucket --s3-region us-west-2 --s3-endpoint-url https://s3.us-west-2.amazonaws.com
```

#### Download and sync in one step

Both download commands accept the same S3 options. Add `--sync-s3` to upload
the results to S3 immediately after a successful download:

```bash
# Download models, then sync them to S3
huggingface-tools download-models --sync-s3 --s3-bucket my-models-bucket --s3-prefix models/

# Download datasets, then sync them to S3 (using env defaults for bucket/prefix)
huggingface-tools download-datasets --sync-s3
```

**S3 options** (available on `sync-s3`, `download-models`, and `download-datasets`):

| Option | Env var | Description |
| --- | --- | --- |
| `--s3-bucket` | `S3_BUCKET` | Target S3 bucket name |
| `--s3-prefix` | `S3_PREFIX` | Key prefix within the bucket |
| `--s3-region` | `AWS_REGION` | AWS region for the S3 client |
| `--s3-endpoint-url` | `S3_ENDPOINT_URL` | Custom endpoint for S3-compatible stores |
| `--s3-force` | - | Re-upload files even if they already exist |
| `--sync-s3` | - | (download commands only) Sync after download |
| `--local-dir` | `MODEL_HOME` | (`sync-s3` only) Directory to upload |

#### Required IAM permissions

The principal running the sync needs write access to the target bucket/prefix:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::my-models-bucket/huggingface/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::my-models-bucket"
    }
  ]
}
```

### As a Python Module

```bash
python -m huggingface_tools download-models
python -m huggingface_tools download-datasets
```

### Programmatic Usage

```python
from pathlib import Path
from huggingface_tools.models import download_models
from huggingface_tools.datasets import download_datasets
from huggingface_tools.logging_config import setup_logging

# Setup logging
setup_logging(level="INFO")

# Download models
stats = download_models(
    config_file=Path("models.json"),
    model_home=Path("/data/models"),
    force_download=False
)

print(f"Downloaded: {stats['downloaded']}, Skipped: {stats['skipped']}")

# Download datasets
stats = download_datasets(
    config_file=Path("datasets.json"),
    dataset_home=Path("/data/datasets"),
    force_download=False,
    max_workers=8
)

print(f"Downloaded: {stats['downloaded']}, Skipped: {stats['skipped']}")

# Sync a local directory to S3
from huggingface_tools.s3_sync import sync_to_s3

stats = sync_to_s3(
    local_dir=Path("/data/models"),
    bucket="my-models-bucket",
    prefix="huggingface/",
    region="us-east-1",
    force=False,
)

print(f"Uploaded: {stats['uploaded']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")
```

## Security Best Practices

This package implements several security best practices:

### 1. Sensitive Data Protection
- Automatic token and API key redaction in logs
- HuggingFace tokens are masked in all log output
- Environment variables with sensitive keywords are protected

### 2. Path Validation
- All file paths are validated and sanitized
- Path traversal attempts are detected and blocked
- Symlinks are resolved to prevent security issues

### 3. Input Validation
- Repository IDs are validated against expected patterns
- Filenames are sanitized to prevent directory traversal
- Configuration files are validated before processing

### 4. Disk Space Checking
- Warns when disk space is low before downloads
- Prevents system instability from full disks

### 5. Error Handling
- Comprehensive error handling for network issues
- Authentication errors are clearly reported
- Unexpected errors are logged with full context

### 6. S3 Sync Safety
- Bucket names are validated against AWS naming rules
- Key prefixes are sanitized to prevent path traversal in object keys
- AWS credentials are resolved via the boto3 chain (env, profile, IAM role) and never stored by the package

## Logging

The package provides structured logging with the following features:

- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Console Output**: Colored, formatted output to console
- **File Logging**: Optional rotating file logs (10MB max, 5 backups)
- **Sensitive Data Filtering**: Automatic redaction of tokens, passwords, and API keys

### Logging Examples

```bash
# Enable verbose logging
huggingface-tools download-models --verbose

# Write logs to file
huggingface-tools download-models --log-file /var/log/hf-tools.log

# Both verbose and file logging
huggingface-tools download-models --verbose --log-file ./download.log
```

## Authentication

For gated or private models/datasets, you need to authenticate with HuggingFace:

### Option 1: Environment Variable

```bash
export HF_TOKEN=hf_your_token_here
huggingface-tools download-models
```

### Option 2: .env File

```bash
echo "HF_TOKEN=hf_your_token_here" >> .env
huggingface-tools download-models
```

### Option 3: HuggingFace CLI

```bash
huggingface-cli login
huggingface-tools download-models
```

## Development

### Running from Source

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests (when available)
pytest

# Format code
black huggingface_tools/

# Type checking
mypy huggingface_tools/
```

### Project Structure

```
huggingface-tools/
├── huggingface_tools/         # Main package
│   ├── __init__.py           # Package initialization
│   ├── __main__.py           # Module entry point
│   ├── cli.py                # CLI implementation
│   ├── models.py             # Model download functionality
│   ├── datasets.py           # Dataset download functionality
│   ├── s3_sync.py            # S3 sync/upload functionality
│   ├── logging_config.py     # Logging configuration
│   └── security.py           # Security utilities
├── scripts/                  # Legacy scripts (kept for reference)
│   ├── .env.example
│   ├── models.json
│   ├── datasets.json
│   ├── model_manager.py
│   └── get_datasets.py
├── pyproject.toml           # Package configuration
├── setup.py                 # Backward compatibility
├── README.md
└── LICENSE
```

## Legacy Scripts

The original scripts are still available in the `scripts/` directory for reference:

- `scripts/model_manager.py` - Original model download script
- `scripts/get_datasets.py` - Original dataset download script

These scripts are now superseded by the package CLI, but are kept for backward compatibility.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built on top of [huggingface_hub](https://github.com/huggingface/huggingface_hub)
- Uses [python-dotenv](https://github.com/theskumar/python-dotenv) for environment management
