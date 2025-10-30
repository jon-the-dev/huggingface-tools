# huggingface-tools

A Python package for managing HuggingFace models and datasets with built-in security and logging best practices.

## Features

- **Easy Model Management**: Download GGUF and other models from HuggingFace Hub
- **Dataset Management**: Batch download datasets from HuggingFace Hub
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
```

### Using pip (once published)

```bash
pip install huggingface-tools
```

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
```

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
