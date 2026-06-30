#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment 'venv' not found."
    echo "Please set up the project first or run 'python3 -m venv venv' and install requirements."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if required packages are installed
if ! python3 -c "import questionary, kokoro_onnx, soundfile" &>/dev/null; then
    echo "Installing missing dependencies..."
    pip install -r requirements.txt
fi

# Run the CLI
python3 cli.py
