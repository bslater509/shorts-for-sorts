#!/bin/bash

# Change to the directory of the script
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
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
python gui/server.py $ARGS
