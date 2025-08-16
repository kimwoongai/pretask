#!/usr/bin/env bash
# Render build script

set -o errexit  # exit on error

echo "Starting build process..."
echo "Python version: $(python --version)"

# Check Python version and fail if it's not 3.11
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Detected Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" != "3.11" ]]; then
    echo "ERROR: Python 3.11 is required, but Python $PYTHON_VERSION is being used"
    echo "Please check runtime.txt and render.yaml configuration"
    exit 1
fi

# Update pip to latest version
pip install --upgrade pip setuptools wheel

# Set environment variables for better compatibility
export PIP_NO_CACHE_DIR=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

# Install dependencies
pip install --no-cache-dir -r requirements.txt

# Create necessary directories
mkdir -p logs

echo "Build completed successfully with Python $PYTHON_VERSION"
