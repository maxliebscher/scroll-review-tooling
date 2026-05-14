from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib import request


ROOT = Path(__file__).resolve().parents[1]


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get(base_url: str, path: str) -> tuple[int, str]:
    with request.urlopen(base_url + path, timeout=20) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def _post(base_url: str, action: str, nonce: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = b""
    headers = {"X-Scroll-Review-Action": nonce}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(base_url + "/action/" + action, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def run_operator_flow_check(repo_root: Path = ROOT, workspace: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    workspace_context = tempfile.TemporaryDirectory(prefix="scroll-review-flow-") if workspace is None else None
    workspace_path = Path(workspace_context.name if workspace_context else workspace).resolve()
    port = _free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            str(repo_root / "scripts" / "operator_server.py"),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-open",
        ],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        html = ""
        last_error: Exception | None = None
        for _ in range(60):
            try:
                status, html = _get(base_url, "/")
                if status == 200:
                    break
            except Exception as exc:  # pragma: no cover - diagnostic path
                last_error = exc
                time.sleep(0.25)
        else:
            return {
                "decision": "operator-flow-check-blocked",
                "status_ok": False,
                "readiness_blockers": ["server-start"],
                "error": str(last_error or "server did not start"),
            }

        nonce_match = re.search(r'name="scroll-review-action" content="([^"]*)"', html)
        if not nonce_match:
            return {
                "decision": "operator-flow-check-blocked",
                "status_ok": False,
                "readiness_blockers": ["missing-action-nonce"],
            }
        nonce = nonce_match.group(1)
        action_results = [
            ("run-setup", _post(base_url, "run-setup", nonce)),
            ("check-workspace", _post(base_url, "check-workspace", nonce, {"workspace": str(workspace_path)})),
            ("source-catalog", _post(base_url, "source-catalog", nonce, {"source": "public-demo"})),
            (
                "plan-chunk",
                _post(
                    base_url,
                    "plan-chunk",
                    nonce,
                    {
                        "workspace": str(workspace_path),
                        "source": "public-demo",
                        "scan": "synthetic-public-scroll",
                        "preset": "tiny-preview",
                    },
                ),
            ),
            ("fetch-chunk", _post(base_url, "fetch-chunk", nonce)),
            ("scan-readiness", _post(base_url, "scan-readiness", nonce)),
        ]
        _, final_html = _get(base_url, "/")
        report_statuses: dict[str, dict[str, Any]] = {}
        for key in ["setup", "source-catalog", "chunk-fetch", "scan-readiness"]:
            status, body = _get(base_url, "/report/" + key)
            report_statuses[key] = {
                "status": status,
                "byte_count": len(body.encode("utf-8")),
                "claim_safe_copy": ("no-claim" in body.lower()) or ("No OCR" in body),
            }
        expected_outputs = {
            rel: (repo_root / rel).exists()
            for rel in [
                "demo/out/operator_doctor.json",
                "demo/out/source_catalog.json",
                "demo/out/local_data_workspace.json",
                "demo/out/chunk_download_plan.json",
                "demo/out/chunk_fetch_status.json",
                "demo/out/scan_data_readiness.json",
            ]
        }
        marker = workspace_path / ".scroll-review-workspace.json"
        chunk = workspace_path / "chunks/public-demo/synthetic-public-scroll/tiny-preview/chunk.bin"
        action_rows = [
            {
                "action": name,
                "ok": bool(payload.get("ok")),
                "decision": payload.get("decision") or (payload.get("payload") or {}).get("decision"),
            }
            for name, payload in action_results
        ]
        failed: list[str] = []
        if "Functional operator wizard" not in html or "data-primary-next" not in html:
            failed.append("home-page")
        failed.extend(row["action"] for row in action_rows if not row["ok"])
        failed.extend(rel for rel, exists in expected_outputs.items() if not exists)
        failed.extend(key for key, row in report_statuses.items() if row["status"] != 200 or not row["claim_safe_copy"])
        if "Open review reports" not in final_html or "Review ready" not in final_html:
            failed.append("final-page-ready")
        if not marker.exists():
            failed.append("workspace-marker")
        if not chunk.exists() or chunk.stat().st_size <= 0:
            failed.append("chunk-file")
        status_ok = not failed
        return {
            "decision": "operator-flow-check-pass" if status_ok else "operator-flow-check-blocked",
            "status_ok": status_ok,
            "readiness_stage": "operator-flow-ready" if status_ok else "blocked",
            "readiness_blockers": failed,
            "server_scope": "127.0.0.1-only",
            "claim_status": "no-claim",
            "public_claim_allowed": False,
            "target_inference_allowed": False,
            "claim_safety": "Operator flow check only; no OCR, no transcription, no reading, no public or prize claim.",
            "actions": action_rows,
            "reports": report_statuses,
            "expected_outputs": expected_outputs,
            "workspace_marker_exists": marker.exists(),
            "chunk_exists": chunk.exists(),
            "chunk_byte_count": chunk.stat().st_size if chunk.exists() else 0,
            "workspace_label": "temporary-local-workspace" if workspace_context else "provided-local-workspace",
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
            proc.kill()
            proc.wait(timeout=5)
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        if workspace_context is not None:
            workspace_context.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Operator app through its no-claim HTTP action flow.")
    parser.add_argument("--workspace", help="Optional local workspace for raw chunk test output.")
    parser.add_argument("--out-json", help="Optional JSON output path.")
    args = parser.parse_args()
    payload = run_operator_flow_check(ROOT, Path(args.workspace) if args.workspace else None)
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, indent=2))
    if not payload.get("status_ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
