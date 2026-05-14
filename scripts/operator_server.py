from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import secrets
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_POST_BYTES = 16_384
LOCAL_ACTION_NONCE = secrets.token_urlsafe(24)
ACTION_LOCK = threading.Lock()

from scroll_review_tooling.operator_server import (
    ALLOWED_REPORTS,
    read_status,
    render_home,
    run_chunk_fetch,
    run_chunk_plan,
    run_guided_chunk_flow,
    run_operator,
    run_scan_readiness,
    run_setup,
    run_source_catalog,
    run_workspace_check,
)


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


def _host_allowed(handler: BaseHTTPRequestHandler) -> bool:
    host = (handler.headers.get("Host") or "").split(":", 1)[0].strip().lower()
    return host in {"127.0.0.1", "localhost"}


def _origin_allowed(handler: BaseHTTPRequestHandler) -> bool:
    origin = handler.headers.get("Origin") or handler.headers.get("Referer") or ""
    if not origin:
        return True
    parsed = urlparse(origin)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}


def _local_action_allowed(handler: BaseHTTPRequestHandler) -> tuple[bool, str, int]:
    if not _host_allowed(handler):
        return False, "local-host-required", 403
    if not _origin_allowed(handler):
        return False, "local-origin-required", 403
    if handler.headers.get("X-Scroll-Review-Action") != LOCAL_ACTION_NONCE:
        return False, "local-action-nonce-required", 403
    return True, "", 200


def _read_json_payload(handler: BaseHTTPRequestHandler) -> tuple[dict[str, object] | None, str, int]:
    try:
        length = int(handler.headers.get("Content-Length") or "0")
    except ValueError:
        return None, "invalid-content-length", 400
    if length > MAX_POST_BYTES:
        return None, "request-body-too-large", 413
    if length == 0:
        return {}, "", 200
    content_type = handler.headers.get("Content-Type") or ""
    if "application/json" not in content_type.lower():
        return None, "json-body-required", 415
    try:
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "invalid-json-body", 400
    if not isinstance(payload, dict):
        return None, "json-object-required", 400
    return payload, "", 200


def _run_locked(action: Callable[[], dict[str, object]]) -> tuple[dict[str, object], int]:
    if not ACTION_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "local-action-already-running"}, 409
    try:
        return action(), 200
    finally:
        ACTION_LOCK.release()


class OperatorHandler(BaseHTTPRequestHandler):
    server_version = "ScrollReviewLocalOperator/1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if not _host_allowed(self):
            _html_response(self, "<!doctype html><title>Blocked</title><p>Local host required.</p>", status=403)
            return
        if parsed.path == "/":
            status = read_status(ROOT)
            status["local_action_nonce"] = LOCAL_ACTION_NONCE
            _html_response(self, render_home(status))
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
        allowed, error, status = _local_action_allowed(self)
        if not allowed:
            _json_response(self, {"ok": False, "error": error}, status=status)
            return
        payload, error, status = _read_json_payload(self)
        if payload is None:
            _json_response(self, {"ok": False, "error": error}, status=status)
            return
        response: tuple[dict[str, object], int] | None = None
        if parsed.path == "/action/run-setup":
            response = _run_locked(lambda: run_setup(ROOT))
        if parsed.path == "/action/run-operator":
            response = _run_locked(lambda: run_operator(ROOT))
        if parsed.path == "/action/source-catalog":
            response = _run_locked(lambda: run_source_catalog(ROOT))
        if parsed.path == "/action/check-workspace":
            response = _run_locked(lambda: run_workspace_check(ROOT, str(payload.get("workspace") or "")))
        if parsed.path == "/action/plan-chunk":
            response = _run_locked(lambda:
                run_chunk_plan(
                    ROOT,
                    str(payload.get("workspace") or ""),
                    str(payload.get("source") or "public-demo"),
                    str(payload.get("scan") or "synthetic-public-scroll"),
                    str(payload.get("preset") or "tiny-preview"),
                )
            )
        if parsed.path == "/action/guided-chunk-flow":
            response = _run_locked(lambda:
                run_guided_chunk_flow(
                    ROOT,
                    str(payload.get("workspace") or ""),
                    str(payload.get("source") or "public-demo"),
                    str(payload.get("scan") or "synthetic-public-scroll"),
                    str(payload.get("preset") or "tiny-preview"),
                )
            )
        if parsed.path == "/action/fetch-chunk":
            response = _run_locked(lambda: run_chunk_fetch(ROOT))
        if parsed.path == "/action/scan-readiness":
            response = _run_locked(lambda: run_scan_readiness(ROOT))
        if response is not None:
            payload_out, status_out = response
            _json_response(self, payload_out, status=status_out)
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

    try:
        server = ThreadingHTTPServer((args.host, args.port), OperatorHandler)
    except OSError as exc:
        raise SystemExit(
            f"operator-server-port-unavailable: 127.0.0.1:{args.port} could not be opened. "
            "Close the existing local app or choose another --port."
        ) from exc
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
