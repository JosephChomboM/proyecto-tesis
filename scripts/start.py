"""Render entrypoint. Use the platform's port, retain Streamlit's security defaults."""

import os
import runpy
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    # Use the checked-out commit even if a platform reuses an installed package cache.
    sys.path.insert(0, str(root / "src"))
    print(f"Mise: código {os.environ.get('RENDER_GIT_COMMIT', 'local')}", flush=True)
    port = int(os.environ.get("PORT", "8501"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT debe ser un puerto válido.")
    sys.argv = [
        "streamlit", "run", "app.py",
        "--server.address", "0.0.0.0", "--server.port", str(port),
        "--server.headless", "true", "--server.fileWatcherType", "none",
        "--browser.gatherUsageStats", "false",
    ]
    runpy.run_module("streamlit", run_name="__main__")


if __name__ == "__main__":
    main()
