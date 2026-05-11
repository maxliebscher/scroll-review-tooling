from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import sys
from pathlib import Path
from urllib.parse import urlparse
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scroll_review_tooling.operator_server import ALLOWED_REPORTS, read_status, render_home, run_operator, run_setup


def _json_response(handler: BaseHTTPRequestHandler, payload: dict[str, object], status: int = 200) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, text: str, status: int = 200) -> None:
    body = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _file_response(handler: BaseHTTPRequestHandler, path: Path) -> None:
    if not path.exists() or not path.is_file():
        _html_response(
            handler,
            "<!doctype html><title>Not ready</title><p>This report has not been generated yet. Return to the app and click Build dashboard.</p>",
            status=404,
        )
        return
    body = path.read_bytes()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() == ".md":
        content_type = "text/plain; charset=utf-8"
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class OperatorHandler(BaseHTTPRequestHandler):
    server_version = "ScrollReviewLocalOperator/1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            _html_response(self, render_home(read_status(ROOT)))
            return
        if parsed.path == "/status":
            _json_response(self, read_status(ROOT))
            return
        if parsed.path.startswith("/report/"):
            key = parsed.path.rsplit("/", 1)[-1]
            rel = ALLOWED_REPORTS.get(key)
            if not rel:
                _html_response(self, "<!doctype html><title>Blocked</title><p>Unknown report.</p>", status=404)
                return
            _file_response(self, ROOT / rel)
            return
        _html_response(self, "<!doctype html><title>Not found</title><p>Unknown local route.</p>", status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/action/run-setup":
            _json_response(self, run_setup(ROOT))
            return
        if parsed.path == "/action/run-operator":
            _json_response(self, run_operator(ROOT))
            return
        _json_response(self, {"ok": False, "error": "unknown local action"}, status=404)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the interactive local no-claim operator app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--once", action="store_true", help="Render the app HTML once and exit without starting the server.")
    args = parser.parse_args()

    if args.host != "127.0.0.1":
        raise SystemExit("operator-server-host-must-be-127.0.0.1")
    if args.once:
        print(render_home(read_status(ROOT)))
        return

    server = ThreadingHTTPServer((args.host, args.port), OperatorHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Scroll Review Local App running at {url}")
    print("Local-only controls: setup check, dashboard build, and generated report links.")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
