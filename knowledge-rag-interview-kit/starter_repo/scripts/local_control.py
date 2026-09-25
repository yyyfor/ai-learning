"""Local-only launcher and control API for the FastAPI development server.

Run with scripts/start_local.sh. This controller stays on port 8001 when the
API on port 8000 is stopped, so the browser can start it again.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONTROL_PORT = int(os.getenv("CONTROL_PORT", "8001"))
API_PORT = int(os.getenv("API_PORT", "8000"))
LOOPBACK = "127.0.0.1"


class Controller:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.lock = threading.Lock()

    def api_health(self) -> dict | None:
        try:
            with urllib.request.urlopen(
                f"http://{LOOPBACK}:{API_PORT}/health", timeout=1
            ) as response:
                return json.load(response)
        except (OSError, ValueError, urllib.error.URLError):
            return None

    def port_in_use(self) -> bool:
        with socket.socket() as sock:
            return sock.connect_ex((LOOPBACK, API_PORT)) == 0

    def status(self) -> dict:
        with self.lock:
            owned = self.process is not None and self.process.poll() is None
        health = self.api_health()
        listening = self.port_in_use()
        state = ("running" if health else "starting") if owned else (
            "external" if listening else "stopped"
        )
        return {
            "backend": state,
            "frontend": "available" if health else "unavailable",
            "health": health,
            "managed": owned,
            "api_url": f"http://{LOOPBACK}:{API_PORT}/",
            "control_url": f"http://{LOOPBACK}:{CONTROL_PORT}/",
        }

    def start(self) -> tuple[int, str]:
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return 200, "API is already starting or running."
            if self.port_in_use():
                return 409, "Port 8000 is in use by another process. Stop it before using this controller."
            environment = os.environ.copy()
            environment.setdefault("RAG_ENABLED", "true")
            self.process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", LOOPBACK,
                 "--port", str(API_PORT)],
                cwd=PROJECT_DIR,
                env=environment,
            )
            return 202, "API is starting. Initial indexing may take a few minutes."

    def stop(self) -> tuple[int, str]:
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                return 409, "No API started by this controller. An external API must be stopped in its own terminal."
            process = self.process
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        with self.lock:
            if self.process is process:
                self.process = None
        return 200, "API stopped. The control page remains available."


controller = Controller()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # The status page polls often; keep the launcher terminal readable.
        if getattr(self, "path", None) != "/api/status":
            super().log_message(format, *args)

    def _allowed_hosts(self) -> set[str]:
        return {f"{host}:{CONTROL_PORT}" for host in ("127.0.0.1", "localhost")}

    def _allowed_origins(self) -> set[str]:
        return {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")
                for port in (API_PORT, CONTROL_PORT)}

    def _check_host(self) -> bool:
        if self.headers.get("Host") not in self._allowed_hosts():
            self.send_error(403, "Local host only")
            return False
        return True

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "")
                         if self.headers.get("Origin") in self._allowed_origins() else "null")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, data: dict) -> None:
        self._send(code, json.dumps(data).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if not self._check_host():
            return
        if self.path == "/api/status":
            self._json(200, controller.status())
        elif self.path in ("/", "/index.html"):
            self._send(200, (PROJECT_DIR / "scripts" / "control.html").read_bytes(),
                       "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if not self._check_host():
            return
        if self.headers.get("Origin") not in self._allowed_origins():
            self._json(403, {"message": "Requests must come from the local control or app page."})
            return
        if self.path == "/api/start":
            code, message = controller.start()
        elif self.path == "/api/stop":
            code, message = controller.stop()
        else:
            self.send_error(404)
            return
        self._json(code, {"message": message, **controller.status()})


def main() -> None:
    server = ThreadingHTTPServer((LOOPBACK, CONTROL_PORT), Handler)
    print(f"Control page: http://{LOOPBACK}:{CONTROL_PORT}/", flush=True)
    code, message = controller.start()
    print(message, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if controller.process is not None and controller.process.poll() is None:
            controller.stop()


if __name__ == "__main__":
    main()
