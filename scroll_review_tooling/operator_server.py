from __future__ import annotations

from html import escape
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .common import load_json

OPERATOR_SERVER_PROTOCOL_VERSION = "local-operator-server-v1"
ALLOWED_REPORTS = {
    "operator": "demo/out/operator.html",
    "dashboard": "demo/out/dashboard.html",
    "setup": "demo/out/operator_doctor.html",
    "summary": "demo/out/operator_summary.md",
    "status": "demo/out/local_operator.json",
    "release": "demo/out/release_check.json",
}


def _html(value: Any) -> str:
    if value is None or value == "":
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_html(item) for item in value) or "none"
    return escape(str(value), quote=True)


def _run_python(repo_root: Path, args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_setup(repo_root: Path) -> dict[str, Any]:
    result = _run_python(repo_root, ["scripts/operator_doctor.py"])
    return {"action": "setup", **result, "status": read_status(repo_root)}


def run_operator(repo_root: Path) -> dict[str, Any]:
    result = _run_python(repo_root, ["scripts/local_operator.py"])
    return {"action": "operator", **result, "status": read_status(repo_root)}


def read_status(repo_root: Path) -> dict[str, Any]:
    status_path = repo_root / "demo/out/local_operator.json"
    doctor_path = repo_root / "demo/out/operator_doctor.json"
    release_path = repo_root / "demo/out/release_check.json"
    payload: dict[str, Any] = {
        "protocol_version": OPERATOR_SERVER_PROTOCOL_VERSION,
        "server_scope": "127.0.0.1-only",
        "allowed_actions": ["run-setup", "run-operator", "open-generated-report"],
        "allowed_reports": ALLOWED_REPORTS,
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
    }
    if status_path.exists():
        operator = load_json(status_path)
        payload.update(
            {
                "decision": operator.get("decision"),
                "status_ok": operator.get("status_ok"),
                "readiness_stage": operator.get("readiness_stage"),
                "readiness_blockers": operator.get("readiness_blockers"),
                "operator_headline_status": operator.get("operator_headline_status"),
                "operator_next_step": operator.get("operator_next_step"),
                "operator_tasks": operator.get("operator_tasks") or [],
                "operator_shareable_outputs": operator.get("operator_shareable_outputs") or [],
            }
        )
    else:
        payload.update(
            {
                "decision": "operator-not-run",
                "status_ok": False,
                "readiness_stage": "not-started",
                "readiness_blockers": ["operator-not-run"],
                "operator_headline_status": "Start by checking setup",
                "operator_next_step": "Click Check setup, then Build dashboard.",
                "operator_tasks": [],
                "operator_shareable_outputs": [],
            }
        )
    if doctor_path.exists():
        payload["doctor_decision"] = load_json(doctor_path).get("decision")
    if release_path.exists():
        payload["release_check_decision"] = load_json(release_path).get("decision")
    return payload


def render_home(status: dict[str, Any]) -> str:
    tasks = status.get("operator_tasks") or []
    report_cards = [
        ("Setup report", "setup", "Checks Python, files, output folder, and session shape."),
        ("Operator report", "operator", "Plain-language status page."),
        ("Dashboard", "dashboard", "Readiness, blockers, handoff, and priority queue."),
        ("Share summary", "summary", "Short no-claim summary for reviewers."),
    ]
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <title>Scroll Review Local App</title>",
        "  <style>",
        "    * { box-sizing:border-box; }",
        "    :root { color-scheme: light; --ink:#16202a; --muted:#5e6b78; --line:#d8dee4; --bg:#f6f8fa; --panel:#ffffff; --accent:#1f6feb; --ok:#0b6b3a; --bad:#9f1d20; }",
        "    body { margin:0; font-family: Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--ink); overflow-x:hidden; }",
        "    main { width:100%; max-width:min(1120px, 100vw); margin:0 auto; padding:28px; overflow-x:hidden; }",
        "    h1 { margin:0 0 8px; font-size:32px; overflow-wrap:anywhere; }",
        "    h2 { margin:28px 0 12px; font-size:20px; }",
        "    p { color:var(--muted); line-height:1.5; overflow-wrap:anywhere; }",
        "    .hero { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; min-width:0; max-width:100%; overflow-wrap:anywhere; }",
        "    .grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; min-width:0; }",
        "    .card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:15px; min-width:0; max-width:100%; overflow-wrap:anywhere; }",
        "    .label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:0; }",
        "    .value { font-size:18px; font-weight:650; overflow-wrap:anywhere; }",
        "    .ok { color:var(--ok); } .bad { color:var(--bad); }",
        "    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }",
        "    button, .button { border:1px solid #8ab6f0; background:#fff; color:var(--accent); border-radius:8px; padding:10px 12px; font-weight:650; cursor:pointer; text-decoration:none; white-space:normal; max-width:100%; }",
        "    button.primary { background:var(--accent); color:#fff; }",
        "    button:disabled { color:#7d8790; border-color:var(--line); cursor:wait; }",
        "    table { display:block; width:100%; overflow-x:auto; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:8px; }",
        "    th, td { padding:11px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:14px; }",
        "    th { background:#edf2f7; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:0; }",
        "    tr:last-child td { border-bottom:0; }",
        "    pre { white-space:pre-wrap; overflow:auto; max-height:260px; background:#0f1720; color:#d8e2ec; border-radius:8px; padding:12px; }",
        "    code { font-family:Consolas, monospace; overflow-wrap:anywhere; }",
        "    @media (max-width: 520px) { main { width:100vw; max-width:100vw; padding:16px; } h1 { font-size:28px; } .hero, .card, table, pre { width:calc(100vw - 32px); max-width:calc(100vw - 32px); } .hero { padding:16px; } .grid { grid-template-columns:minmax(0, 1fr); width:calc(100vw - 32px); max-width:calc(100vw - 32px); } .actions { display:grid; grid-template-columns:minmax(0, 1fr); width:100%; } .button, button { width:100%; min-width:0; } }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        '  <section class="hero">',
        "    <h1>Scroll Review Local App</h1>",
        "    <p>Run the safe local review checks, build the dashboard, and open the generated reports from one screen. This app does not upload data, inspect raw evidence, run OCR, run transcription, run inference, or approve claims.</p>",
        '    <div class="actions">',
        '      <button class="primary" data-action="run-operator">Build dashboard</button>',
        '      <button data-action="run-setup">Check setup</button>',
        '      <a class="button" href="/report/dashboard" target="_blank" rel="noreferrer">Open dashboard</a>',
        '      <a class="button" href="/report/summary" target="_blank" rel="noreferrer">Open share summary</a>',
        "    </div>",
        "  </section>",
        '  <section class="grid" aria-label="Current status">',
        f'    <div class="card"><div class="label">Decision</div><div class="value">{_html(status.get("decision"))}</div></div>',
        f'    <div class="card"><div class="label">Ready</div><div class="value {"ok" if status.get("status_ok") else "bad"}">{_html(status.get("status_ok"))}</div></div>',
        f'    <div class="card"><div class="label">Stage</div><div class="value">{_html(status.get("readiness_stage"))}</div></div>',
        f'    <div class="card"><div class="label">Next step</div><div class="value">{_html(status.get("operator_headline_status"))}</div></div>',
        "  </section>",
        "  <h2>Workflow</h2>",
        "  <table>",
        "    <thead><tr><th>Step</th><th>Status</th><th>Action</th><th>Output</th></tr></thead>",
        "    <tbody>",
    ]
    if tasks:
        for task in tasks:
            if isinstance(task, dict):
                lines.append(
                    f"      <tr><td>{_html(task.get('label'))}</td><td><code>{_html(task.get('status'))}</code></td><td>{_html(task.get('action'))}</td><td><code>{_html(task.get('output'))}</code></td></tr>"
                )
    else:
        lines.append("      <tr><td>Start</td><td><code>not run</code></td><td>Click Check setup, then Build dashboard.</td><td><code>demo/out/</code></td></tr>")
    lines.extend(
        [
            "    </tbody>",
            "  </table>",
            "  <h2>Reports</h2>",
            '  <section class="grid">',
        ]
    )
    for label, key, detail in report_cards:
        lines.append(
            f'    <div class="card"><div class="value">{_html(label)}</div><p>{_html(detail)}</p><a class="button" href="/report/{_html(key)}" target="_blank" rel="noreferrer">Open</a></div>'
        )
    lines.extend(
        [
            "  </section>",
            "  <h2>Run Log</h2>",
            '  <pre id="log">Ready.</pre>',
            "  <script>",
            "    async function runAction(action) {",
            "      const log = document.getElementById('log');",
            "      const buttons = Array.from(document.querySelectorAll('button'));",
            "      buttons.forEach((button) => button.disabled = true);",
            "      log.textContent = 'Running ' + action + '...';",
            "      try {",
            "        const response = await fetch('/action/' + action, { method: 'POST' });",
            "        const data = await response.json();",
            "        log.textContent = JSON.stringify(data, null, 2);",
            "        if (data.ok) window.location.reload();",
            "      } catch (error) {",
            "        log.textContent = String(error);",
            "      } finally {",
            "        buttons.forEach((button) => button.disabled = false);",
            "      }",
            "    }",
            "    document.querySelectorAll('button[data-action]').forEach((button) => {",
            "      button.addEventListener('click', () => runAction(button.getAttribute('data-action')));",
            "    });",
            "  </script>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(lines) + "\n"
