#!/usr/bin/env python3
"""Detach and launch the backend uvicorn server."""
import os
import signal
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
backend_dir = root / "backend"
venv_python = backend_dir / ".venv" / "bin" / "python"

# Kill existing backend on port 8002
try:
    result = subprocess.run(
        ["lsof", "-ti:8002"],
        capture_output=True,
        text=True,
    )
    for pid in result.stdout.strip().split():
        try:
            os.kill(int(pid), signal.SIGKILL)
        except Exception:
            pass
except Exception:
    pass

log_path = backend_dir / "backend.log"
with open(log_path, "a") as log:
    log.write("\n--- Starting backend ---\n")

env = os.environ.copy()
env["PATH"] = str(backend_dir / ".venv" / "bin") + ":" + env.get("PATH", "")

proc = subprocess.Popen(
    [str(venv_python), "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8002"],
    cwd=str(backend_dir),
    env=env,
    start_new_session=True,
    stdout=open(log_path, "a"),
    stderr=subprocess.STDOUT,
)

pid_file = backend_dir / "backend.pid"
pid_file.write_text(str(proc.pid))
print(f"Backend started with PID {proc.pid}")
