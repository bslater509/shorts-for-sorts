#!/bin/bash

# Change to the project root directory
cd "$(dirname "$0")/.."

# Set up or activate virtual environment
if [ -d "$HOME/miniconda3/envs/shorts" ]; then
    echo "Activating conda shorts environment..."
    source $HOME/miniconda3/bin/activate shorts
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "No virtual environment found. Creating 'venv'..."
    if command -v uv &> /dev/null; then
        uv venv --python 3.11 venv
    elif [ -f "$HOME/.local/bin/uv" ]; then
        $HOME/.local/bin/uv venv --python 3.11 venv
    else
        python3 -m venv venv
    fi
    source venv/bin/activate
fi

if [ -f "requirements.txt" ]; then
    echo "Checking and installing dependencies..."
    if command -v uv &> /dev/null; then
        uv pip install -r requirements.txt
    elif [ -f "$HOME/.local/bin/uv" ]; then
        $HOME/.local/bin/uv pip install -r requirements.txt
    else
        pip install -r requirements.txt
    fi
fi

if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    echo "Generating self-signed certificate for HTTPS..."
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -sha256 -days 365 -nodes -subj "/CN=localhost"
fi

ARGS="--https"
for arg in "$@"; do
    if [ "$arg" != "--https" ]; then
        ARGS="$ARGS $arg"
    fi
done

echo "Starting the server..."
python3 gui/server.py $ARGS
