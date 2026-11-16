"""Start the actual production entrypoint on an isolated database directory."""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory() as directory:
        env = {**os.environ, "PORT": str(port), "RESTAURANTE_DATA_DIR": directory,
               "RENDER": "true"}
        with tempfile.TemporaryFile(mode="w+") as logs:
            process = subprocess.Popen([sys.executable, str(root / "scripts/start.py")],
                                       cwd=root, env=env, stdout=logs, stderr=logs)
            try:
                for _ in range(60):
                    if process.poll() is not None:
                        break
                    try:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/_stcore/health", timeout=1
                        ) as response:
                            if response.status == 200:
                                print("Servidor de producción: health check correcto.")
                                return
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.5)
                logs.seek(0)
                raise RuntimeError("El servidor no arrancó:\n" + logs.read()[-4000:])
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    main()
