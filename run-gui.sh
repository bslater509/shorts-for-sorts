#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Handle graceful shutdown
cleanup() {
    info "Shutting down..."
}
trap cleanup EXIT INT TERM

# Change to the project root directory
cd "$(dirname "$0")" || error "Failed to change directory"

# Set up or activate virtual environment
if [ -d "$HOME/miniconda3/envs/shorts" ]; then
    info "Activating conda shorts environment..."
    source "$HOME/miniconda3/bin/activate" shorts
elif [ -d "venv" ]; then
    info "Activating virtual environment (venv)..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    info "Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    info "No virtual environment found. Creating 'venv'..."
    if command -v uv &> /dev/null; then
        uv venv --python 3.11 venv
    elif [ -f "$HOME/.local/bin/uv" ]; then
        "$HOME/.local/bin/uv" venv --python 3.11 venv
    else
        python3 -m venv venv
    fi
    source venv/bin/activate
fi

if [ -f "requirements.txt" ]; then
    info "Checking and installing Python dependencies..."
    if command -v uv &> /dev/null; then
        uv pip install -r requirements.txt
    elif [ -f "$HOME/.local/bin/uv" ]; then
        "$HOME/.local/bin/uv" pip install -r requirements.txt
    else
        pip install -r requirements.txt
    fi
fi

# Install playwright browsers
info "Ensuring Playwright browsers are installed..."
python3 -m playwright install --with-deps

# Ensure NLTK punkt_tab is available
info "Ensuring NLTK punkt_tab is downloaded..."
python3 -m nltk.downloader punkt_tab

# Build frontend if package.json exists
if [ -d "gui/frontend" ]; then
    info "Installing frontend dependencies and building UI..."
    (cd gui/frontend && npm install && npm run build)
fi

# Keep yt-dlp and ffmpeg-python up to date
info "Updating yt-dlp and ffmpeg-python..."
if command -v uv &> /dev/null; then
    uv pip install --upgrade yt-dlp ffmpeg-python
elif [ -f "$HOME/.local/bin/uv" ]; then
    "$HOME/.local/bin/uv" pip install --upgrade yt-dlp ffmpeg-python
else
    pip install --upgrade yt-dlp ffmpeg-python
fi

if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    info "Generating self-signed certificate for HTTPS..."
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/CN=localhost" 2>/dev/null
fi

# Use an array to properly handle arguments with spaces
ARGS=("--https")
for arg in "$@"; do
    if [ "$arg" != "--https" ]; then
        ARGS+=("$arg")
    fi
done

info "Starting the server..."
exec python3 gui/server.py "${ARGS[@]}"
