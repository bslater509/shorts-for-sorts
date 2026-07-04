#!/bin/bash
cd "$(dirname "$0")"

# Check venv
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment 'venv' not found."
    exit 1
fi
source venv/bin/activate

# Install Python deps if needed
if ! python3 -c "import fastapi, uvicorn, multipart, kokoro_onnx, soundfile" &>/dev/null; then
    echo "Installing missing Python dependencies..."
    pip install -r requirements.txt
fi

# Build frontend if node/npm available and gui/frontend exists
if [ -d "gui/frontend" ] && command -v npm &>/dev/null; then
    echo "Building frontend..."
    cd gui/frontend
    if [ ! -d "node_modules" ]; then
        npm install
    fi
    npm run build
    cd ../.. 
fi

echo "=========================================================="
echo " Starting Shorts Creator Web GUI Server..."
echo " Access the interface locally at: http://localhost:5000"
echo "=========================================================="
echo ""

# Ensure port 5000 is free
echo "Checking port 5000..."
if command -v lsof >/dev/null 2>&1; then
    PID=$(lsof -t -i:5000 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "Port 5000 is in use by PID $PID. Killing it..."
        kill -9 $PID 2>/dev/null || true
        sleep 1
    fi
fi

# Fallback: aggressively kill any python processes running the gui server
pkill -f "python3 gui/server.py" || true
sleep 1

python3 gui/server.py
