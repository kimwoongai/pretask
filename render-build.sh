#!/usr/bin/env bash
# Render build script

set -o errexit  # exit on error

echo "Starting build process..."
echo "Python version: $(python --version)"

# Check Python version and try to use python3.11 if available
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Detected Python version: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" != "3.11" ]]; then
    echo "Current Python version is $PYTHON_VERSION, trying to find Python 3.11..."
    
    # Try to find python3.11
    if command -v python3.11 &> /dev/null; then
        echo "Found python3.11, using it instead"
        export PYTHON_CMD=python3.11
        export PIP_CMD=python3.11
        
        # Verify python3.11 version
        PYTHON311_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        echo "python3.11 version: $PYTHON311_VERSION"
        
        if [[ "$PYTHON311_VERSION" != "3.11" ]]; then
            echo "ERROR: python3.11 command exists but reports version $PYTHON311_VERSION"
            exit 1
        fi
    else
        echo "ERROR: Python 3.11 is required, but Python $PYTHON_VERSION is being used"
        echo "python3.11 command not found"
        echo "Please check runtime.txt and render.yaml configuration"
        exit 1
    fi
else
    export PYTHON_CMD=python
    export PIP_CMD=pip
fi

echo "Using Python command: $PYTHON_CMD"
echo "Python version: $($PYTHON_CMD --version)"

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
