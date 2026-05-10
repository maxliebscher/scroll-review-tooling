from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .common import no_claim_payload, write_json

OPERATOR_APP_PROTOCOL_VERSION = "local-operator-app-v1"


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


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def render_operator_app(
    *,
    out_html: Path,
    out_json: Path,
    repo_root: Path,
    session_payload: dict[str, Any],
    release_payload: dict[str, Any],
    dashboard_payload: dict[str, Any],
    dashboard_html: Path,
) -> dict[str, Any]:
    release_ok = release_payload.get("decision") == "release-check-pass"
    session_ok = session_payload.get("status_ok") is True
    dashboard_ok = dashboard_payload.get("status_ok") is True and dashboard_html.exists()
    blockers: list[str] = []
    if not release_ok:
        blockers.append("release-check")
    if not session_ok:
        blockers.append("session")
    if not dashboard_ok:
        blockers.append("dashboard")
    status_ok = not blockers
    payload = no_claim_payload(
        "local-operator-ready" if status_ok else "local-operator-blocked",
        status_ok,
        protocol_version=OPERATOR_APP_PROTOCOL_VERSION,
        readiness_stage="operator-ready" if status_ok else "blocked",
        readiness_blockers=blockers,
        session_name=session_payload.get("session_name"),
        session_decision=session_payload.get("decision"),
        release_check_decision=release_payload.get("decision"),
        dashboard_decision=dashboard_payload.get("decision"),
        dashboard_html=_safe_relative(dashboard_html, repo_root),
        operator_html=_safe_relative(out_html, repo_root),
        allowed_data_flow="session-json-only",
        local_only=True,
    )
    write_json(out_json, payload)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(_operator_html(payload), encoding="utf-8", newline="\n")
    return payload


def _operator_html(payload: dict[str, Any]) -> str:
    status_class = "ok" if payload.get("status_ok") else "bad"
    rows = [
        ("1", "Start demo or session", "Use the synthetic demo session or a local session manifest that references existing JSON summaries only."),
        ("2", "Run checks", "Validate manifests, release safety, leak scan, and dashboard readiness before review handoff."),
        ("3", "Open dashboard", f"Review status, blockers, readiness, and priority in {_display(payload.get('dashboard_html'))}."),
        ("4", "Share report", "Share only generated no-claim summaries with reviewers; keep real private material outside this public repository."),
    ]
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <title>Scroll Review Local Operator</title>",
        "  <style>",
        "    :root { color-scheme: light; --ink: #15202b; --muted: #5f6b76; --line: #d8dee4; --ok: #0b6b3a; --bad: #9f1d20; --bg: #f6f8fa; --panel: #ffffff; --accent: #1f6feb; }",
        "    body { margin: 0; font-family: Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--ink); }",
        "    main { max-width: 1040px; margin: 0 auto; padding: 30px; }",
        "    h1 { margin: 0 0 10px; font-size: 30px; }",
        "    h2 { margin: 28px 0 12px; font-size: 19px; }",
        "    p { color: var(--muted); line-height: 1.5; }",
        "    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }",
        "    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 15px; }",
        "    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0; }",
        "    .value { font-size: 18px; font-weight: 650; overflow-wrap: anywhere; }",
        "    .ok { color: var(--ok); } .bad { color: var(--bad); }",
        "    .badge { display: inline-block; border: 1px solid #88c4a2; color: var(--ok); border-radius: 999px; padding: 7px 10px; margin: 3px 5px 3px 0; font-size: 13px; font-weight: 650; background: #ffffff; }",
        "    table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }",
        "    th, td { padding: 11px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 14px; }",
        "    th { background: #edf2f7; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0; }",
        "    tr:last-child td { border-bottom: 0; }",
        "    code { font-family: Consolas, monospace; overflow-wrap: anywhere; }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        "  <h1>Scroll Review Local Operator</h1>",
        "  <p>This is a local guide surface for review readiness. It does not read scroll material, run OCR, run transcription, run inference, upload data, or authorize public or prize claims.</p>",
        '  <div aria-label="Safety badges">',
        '    <span class="badge">local only</span>',
        '    <span class="badge">no upload</span>',
        '    <span class="badge">no OCR</span>',
        '    <span class="badge">no reading-result claim</span>',
        '    <span class="badge">manifest guided</span>',
        "  </div>",
        '  <section class="grid" aria-label="Summary">',
        f'    <div class="card"><div class="label">Decision</div><div class="value">{_html(payload.get("decision"))}</div></div>',
        f'    <div class="card"><div class="label">Status OK</div><div class="value {status_class}">{_html(payload.get("status_ok"))}</div></div>',
        f'    <div class="card"><div class="label">Readiness</div><div class="value">{_html(payload.get("readiness_stage"))}</div></div>',
        f'    <div class="card"><div class="label">Session</div><div class="value">{_html(payload.get("session_name"))}</div></div>',
        "  </section>",
        "  <h2>What To Do</h2>",
        "  <table>",
        "    <thead><tr><th>Step</th><th>Operator action</th><th>Plain-language result</th></tr></thead>",
        "    <tbody>",
    ]
    for step, action, result in rows:
        lines.append(f"      <tr><td>{_html(step)}</td><td>{_html(action)}</td><td>{_html(result)}</td></tr>")
    lines.extend(
        [
            "    </tbody>",
            "  </table>",
            "  <h2>Current Outputs</h2>",
            "  <table>",
            "    <thead><tr><th>Output</th><th>Status</th></tr></thead>",
            "    <tbody>",
            f"      <tr><td>Release check</td><td><code>{_html(payload.get('release_check_decision'))}</code></td></tr>",
            f"      <tr><td>Session validation</td><td><code>{_html(payload.get('session_decision'))}</code></td></tr>",
            f"      <tr><td>Dashboard</td><td><code>{_html(payload.get('dashboard_decision'))}</code></td></tr>",
            f"      <tr><td>Dashboard file</td><td><code>{_html(payload.get('dashboard_html'))}</code></td></tr>",
            f"      <tr><td>Blockers</td><td><code>{_html(payload.get('readiness_blockers'))}</code></td></tr>",
            "    </tbody>",
            "  </table>",
            "  <h2>Data Boundary</h2>",
            "  <p>The operator surface loads existing JSON summaries through a session manifest. Real private evidence, raw scans, model artifacts, collaboration exports, and reviewer notes stay outside the public repository unless a separate private workflow explicitly prepares sanitized summaries.</p>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(lines) + "\n"
