import sys
import subprocess
import os
import time
import webbrowser
import threading
import signal
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

processes = []

def run_backend():
    print("[RUNNER] Starting backend server...")
    # Check if uv is used
    try:
        # Check if we can run uv
        subprocess.run(["uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cmd = ["uv", "run", "uvicorn", "app.main:app", "--port", "8000", "--reload"]
    except FileNotFoundError:
        print("[RUNNER] WARNING: 'uv' command not found. Falling back to default 'python -m uvicorn'...")
        cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000", "--reload"]

    p = subprocess.Popen(cmd, cwd=str(BACKEND_DIR))
    processes.append(p)
    p.wait()

def run_frontend():
    print("[RUNNER] Checking frontend dependencies...")
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("[RUNNER] Node modules not found. Installing frontend dependencies (npm install)...")
        subprocess.run(["npm", "install"], cwd=str(FRONTEND_DIR), shell=True)

    print("[RUNNER] Starting frontend Vite server...")
    p = subprocess.Popen(["npm", "run", "dev"], cwd=str(FRONTEND_DIR), shell=True)
    processes.append(p)
    p.wait()

def open_browser():
    # Wait for servers to spin up
    time.sleep(3)
    print("[RUNNER] Opening application in browser: http://localhost:5173")
    webbrowser.open("http://localhost:5173")

def signal_handler(sig, frame):
    print("\n[RUNNER] Shutting down all processes...")
    for p in processes:
        try:
            # On windows, we send CTRL_C_EVENT or kill
            if os.name == 'nt':
                p.terminate()
            else:
                p.send_signal(signal.SIGINT)
        except Exception:
            pass
    print("[RUNNER] Exited cleanly.")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    # 1. Setup backend environment dependencies
    print("[RUNNER] Checking backend environment...")
    try:
        # Check if uv is present
        subprocess.run(["uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[RUNNER] Syncing backend dependencies using uv...")
        subprocess.run(["uv", "pip", "compile", "pyproject.toml", "-o", "requirements.txt"], cwd=str(BACKEND_DIR))
        subprocess.run(["uv", "pip", "install", "-r", "requirements.txt"], cwd=str(BACKEND_DIR))
    except FileNotFoundError:
        print("[RUNNER] 'uv' not found. Installing dependencies via standard pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], cwd=str(BACKEND_DIR))

    # 2. Start services concurrently
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    browser_thread = threading.Thread(target=open_browser, daemon=True)

    backend_thread.start()
    frontend_thread.start()
    browser_thread.start()

    # Keep the main thread alive
    while True:
        time.sleep(1)
