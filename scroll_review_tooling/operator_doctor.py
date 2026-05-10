from __future__ import annotations

from html import escape
import os
import platform
import sys
from pathlib import Path
from typing import Any

from .common import no_claim_payload, write_json
from .sessions import validate_session_manifest

OPERATOR_DOCTOR_PROTOCOL_VERSION = "local-operator-doctor-v1"


def _check(check_id: str, label: str, status: str, detail: str, next_step: str = "none") -> dict[str, str]:
    return {
        "check_id": check_id,
        "label": label,
        "status": status,
        "detail": detail,
        "next_step": next_step,
    }


def _display(value: Any) -> str:
    if value is None or value == "":
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_display(item) for item in value) or "none"
    return str(value)


def _html(value: Any) -> str:
    return escape(_display(value), quote=True)


def build_doctor_payload(repo_root: Path, session_manifest: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    session_manifest = session_manifest if session_manifest.is_absolute() else repo_root / session_manifest
    checks: list[dict[str, str]] = []

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        _check(
            "python-version",
            "Python version",
            "ok" if python_ok else "blocked",
            platform.python_version(),
            "Install Python 3.10 or newer, then rerun CHECK_LOCAL_SETUP.cmd." if not python_ok else "none",
        )
    )

    required_files = [
        "README.md",
        "OPEN_LOCAL_OPERATOR.cmd",
        "RUN_LOCAL_OPERATOR.cmd",
        "START_REVIEW_SESSION.cmd",
        "scripts/local_operator.py",
        "scripts/start_session.py",
        "demo/session_manifest.json",
    ]
    missing = [rel for rel in required_files if not (repo_root / rel).exists()]
    checks.append(
        _check(
            "required-files",
            "Required local files",
            "ok" if not missing else "blocked",
            "all present" if not missing else ", ".join(missing),
            "Restore the missing files from the repository before using the operator." if missing else "none",
        )
    )

    out_dir = repo_root / "demo" / "out"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        probe = out_dir / f"operator_doctor_write_check_{os.getpid()}.tmp"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
        output_ok = True
        output_detail = "demo/out is writable"
    except OSError as exc:
        output_ok = False
        output_detail = str(exc)
    checks.append(
        _check(
            "output-directory",
            "Generated output folder",
            "ok" if output_ok else "blocked",
            output_detail,
            "Check folder permissions, then rerun CHECK_LOCAL_SETUP.cmd." if not output_ok else "none",
        )
    )

    if session_manifest.exists():
        try:
            session_payload = validate_session_manifest(session_manifest)
            session_ok = session_payload.get("status_ok") is True
            session_detail = str(session_payload.get("decision"))
            session_next = "none" if session_ok else "Open the session JSON and fix the listed violations."
        except Exception as exc:  # pragma: no cover - defensive user-facing guard
            session_ok = False
            session_detail = f"could not read session manifest: {exc}"
            session_next = "Use a valid local-review-session-v1 JSON file."
    else:
        session_ok = False
        session_detail = f"missing session manifest: {session_manifest}"
        session_next = "Create or restore demo/session_manifest.json, or pass --session to the launcher."
    checks.append(
        _check(
            "session-manifest",
            "Session manifest",
            "ok" if session_ok else "blocked",
            session_detail,
            session_next,
        )
    )

    local_only = True
    checks.append(
        _check(
            "data-boundary",
            "Data boundary",
            "ok",
            "JSON summaries only; no server, upload, OCR, transcription, inference, or reading-result assertion.",
            "none",
        )
    )

    blockers = [check["check_id"] for check in checks if check["status"] == "blocked"]
    status_ok = not blockers
    return no_claim_payload(
        "operator-doctor-ready" if status_ok else "operator-doctor-blocked",
        status_ok,
        protocol_version=OPERATOR_DOCTOR_PROTOCOL_VERSION,
        readiness_stage="setup-ready" if status_ok else "blocked",
        readiness_blockers=blockers,
        python_version=platform.python_version(),
        platform=platform.platform(),
        session_manifest=str(session_manifest),
        local_only=local_only,
        checks=checks,
        operator_next_command="OPEN_LOCAL_OPERATOR.cmd" if status_ok else "CHECK_LOCAL_SETUP.cmd",
    )


def write_doctor_outputs(
    payload: dict[str, Any],
    *,
    out_json: Path,
    out_md: Path | None = None,
    out_html: Path | None = None,
) -> None:
    write_json(out_json, payload)
    if out_md:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_doctor_markdown(payload), encoding="utf-8", newline="\n")
    if out_html:
        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_html.write_text(render_doctor_html(payload), encoding="utf-8", newline="\n")


def render_doctor_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Local Setup Doctor",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Status OK: `{payload.get('status_ok')}`",
        f"- Next command: `{payload.get('operator_next_command')}`",
        f"- Claim status: `{payload.get('claim_status')}`",
        f"- Public claim allowed: `{payload.get('public_claim_allowed')}`",
        f"- Target inference allowed: `{payload.get('target_inference_allowed')}`",
        "",
        "## Checks",
        "",
    ]
    for check in payload.get("checks") or []:
        if isinstance(check, dict):
            lines.append(
                f"- `{check.get('check_id')}`: `{check.get('status')}` - {check.get('detail')} Next: {check.get('next_step')}"
            )
    lines.extend(["", "No OCR, no transcription, no reading, no public or prize claim."])
    return "\n".join(lines) + "\n"


def render_doctor_html(payload: dict[str, Any]) -> str:
    status_class = "ok" if payload.get("status_ok") else "bad"
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <title>Scroll Review Setup Doctor</title>",
        "  <style>",
        "    :root { color-scheme: light; --ink: #15202b; --muted: #5f6b76; --line: #d8dee4; --ok: #0b6b3a; --bad: #9f1d20; --bg: #f6f8fa; --panel: #ffffff; }",
        "    body { margin: 0; font-family: Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--ink); }",
        "    main { max-width: 960px; margin: 0 auto; padding: 30px; }",
        "    h1 { margin: 0 0 10px; font-size: 30px; }",
        "    p { color: var(--muted); line-height: 1.5; }",
        "    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 15px; margin: 14px 0; }",
        "    .ok { color: var(--ok); } .bad { color: var(--bad); }",
        "    table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }",
        "    th, td { padding: 11px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 14px; }",
        "    th { background: #edf2f7; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0; }",
        "    tr:last-child td { border-bottom: 0; }",
        "    code { font-family: Consolas, monospace; overflow-wrap: anywhere; }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        "  <h1>Scroll Review Setup Doctor</h1>",
        "  <p>This local check tells a non-expert whether the operator can run on this machine. It does not upload data, run OCR, run transcription, run inference, read scroll text, or authorize claims.</p>",
        f'  <div class="card"><strong>Status:</strong> <span class="{status_class}">{_html(payload.get("decision"))}</span><br><strong>Next command:</strong> <code>{_html(payload.get("operator_next_command"))}</code></div>',
        "  <table>",
        "    <thead><tr><th>Check</th><th>Status</th><th>Detail</th><th>Next step</th></tr></thead>",
        "    <tbody>",
    ]
    for check in payload.get("checks") or []:
        if isinstance(check, dict):
            lines.append(
                f"      <tr><td>{_html(check.get('label'))}</td><td><code>{_html(check.get('status'))}</code></td><td>{_html(check.get('detail'))}</td><td>{_html(check.get('next_step'))}</td></tr>"
            )
    lines.extend(
        [
            "    </tbody>",
            "  </table>",
            "  <p>Keep private evidence, raw scans, model artifacts, collaboration exports, and reading attempts outside this public repository.</p>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(lines) + "\n"
