import os
import queue
import sys
import threading
from typing import List

from fastapi import WebSocket

from gui.config import CONFIG_DIR

__all__ = [
    "ConnectionManager",
    "manager",
    "GUI_STATE_FILE",
    "compilation_in_progress",
    "compilation_success",
    "compilation_logs",
    "compilation_thread",
    "compilation_queue",
    "original_stdout",
    "original_stderr",
    "WebStdoutRedirector",
    "batch_state",
    "notify_clients",
    "_main_loop",
    "_compile_log_lock",
    "_compile_thread_lock",
    "_state_file_lock",
    "_batch_lock",
    "_compile_status_lock",
    "_batch_state_lock",
]

# Main loop and manager
_main_loop = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Persistence path for GUI Session State
GUI_STATE_FILE = os.path.join(CONFIG_DIR, "gui_state.json")

# Locks for thread-safe access to shared mutable state
_compile_log_lock = threading.Lock()  # Guards compilation_logs list
_compile_thread_lock = threading.Lock()  # Guards compilation_thread spawn
_state_file_lock = threading.Lock()  # Guards GUI_STATE_FILE writes
_batch_lock = threading.Lock()  # Guards batch_state["in_progress"] TOCTOU

# Server-side compilation tracking
compilation_in_progress = False
compilation_success = False
compilation_logs = []
compilation_thread = None
compilation_queue = queue.Queue()
_compile_status_lock = threading.RLock()

# Custom Stdout redirector to capture compilation logs
original_stdout = sys.stdout
original_stderr = sys.stderr

class WebStdoutRedirector:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, text):
        self.original_stream.write(text)
        with _compile_log_lock:
            global compilation_in_progress
            if compilation_in_progress:
                compilation_logs.append(text)

    def flush(self):
        self.original_stream.flush()

    def __getattr__(self, name):
        return getattr(self.original_stream, name)

sys.stdout = WebStdoutRedirector(original_stdout)
sys.stderr = WebStdoutRedirector(original_stderr)


batch_state = {
    "in_progress": False,
    "num_shorts": 0,
    "should_cancel": False,
    "futures": [],
    "progress_dict": {},
    "job_details": {},
    "failed_job_configs": [],
    "batch_results": [],
    "manager": None,
    "shared_progress": None,
    "executor": None,
    "llm_executor": None,
    "job_configs": [],
    "_retry_configs": None,
}

_batch_state_lock = threading.RLock()

def notify_clients(event_type: str, status: str, message: str, level: str = "info", metadata: dict = None):
    if _main_loop is None or _main_loop.is_closed():
        return
    payload = {
        "event_type": event_type,
        "status": status,
        "message": message,
        "level": level,
        "metadata": metadata or {}
    }
    import asyncio
    asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _main_loop)
