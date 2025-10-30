"""
Entry point for running huggingface-tools as a module.

Usage:
    python -m huggingface_tools download-models
    python -m huggingface_tools download-datasets
"""

import sys
from huggingface_tools.cli import main

if __name__ == '__main__':
    sys.exit(main())
