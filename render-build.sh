#!/usr/bin/env bash
# Render build script

set -o errexit  # exit on error

echo "Starting build process..."
echo "Python version: $(python --version)"

# Check Python version - now accepting both 3.11 and 3.13
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Detected Python version: $PYTHON_VERSION"

# Accept Python 3.11 or 3.13
if [[ "$PYTHON_VERSION" == "3.11" ]] || [[ "$PYTHON_VERSION" == "3.13" ]]; then
    echo "Using Python $PYTHON_VERSION (compatible version)"
    export PYTHON_CMD=python
elif command -v python3.11 &> /dev/null; then
    echo "Found python3.11, using it instead of Python $PYTHON_VERSION"
    export PYTHON_CMD=python3.11
else
    echo "Using default Python $PYTHON_VERSION (hoping for the best)"
    export PYTHON_CMD=python
fi



echo "Using Python command: $PYTHON_CMD"
echo "Python version: $($PYTHON_CMD --version)"

# Update pip and install dependencies
echo "Installing Python packages..."

# Update pip to latest version
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel

# Set environment variables for better compatibility
export PIP_NO_CACHE_DIR=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

# Install dependencies
$PYTHON_CMD -m pip install --no-cache-dir -r requirements.txt

# Create necessary directories
mkdir -p logs

echo "Build completed successfully with Python $($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")"
