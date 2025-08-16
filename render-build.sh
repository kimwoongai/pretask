#!/usr/bin/env bash
# Render build script

set -o errexit  # exit on error

echo "Starting build process..."

# Update pip to latest version
pip install --upgrade pip setuptools wheel

# Set environment variables for better compatibility
export PIP_NO_CACHE_DIR=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

# Install dependencies with more specific options
pip install --no-cache-dir --upgrade -r requirements.txt

# Create necessary directories
mkdir -p logs

echo "Build completed successfully"
