"""Run OpScope: `uv run opscope` serves the web app and its API on http://127.0.0.1:8000 and opens a browser.

It listens on 127.0.0.1 only, so the match data it reads from the local cache never leaves this machine.
"""
from __future__ import annotations

import argparse
import threading
import webbrowser

from opscope.ingest.build import PROJECT_ROOT

WEB_DIR = PROJECT_ROOT / "web"
HOST = "127.0.0.1"


def app():
    from opscope.api import create_app
    return create_app(WEB_DIR)


def main() -> None:
    ap = argparse.ArgumentParser(description="OpScope web app")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = ap.parse_args()
    import uvicorn
    url = f"http://{HOST}:{args.port}"
    print(f"OpScope running at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app(), host=HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
