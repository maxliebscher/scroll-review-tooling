from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .common import load_json, no_claim_payload, write_json

DOSSIER_PROTOCOL_VERSION = "review-dossier-v1"
INSPECT_PROTOCOL_VERSION = "inspect-summary-v1"
PRIORITY_PROTOCOL_VERSION = "path-priority-v1"
DASHBOARD_PROTOCOL_VERSION = "local-dashboard-html-v1"
RELEASE_READY_INPUT_STAGES = {"manifest-valid", "surface-ready", "preflight-ready", "review-ready"}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _claim_safety_blockers(row: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if row.get("public_claim_allowed") is True:
        blockers.append("claim-safety")
    if row.get("target_inference_allowed") is True:
        blockers.append("claim-safety")
    if row.get("claim_status") not in (None, "no-claim"):
        blockers.append("claim-safety")
    return sorted(set(blockers))


def make_dossier(bundle_path: Path, review_status_path: Path, second_check_path: Path, release_audit_path: Path, out_json: Path, out_md: Path | None = None) -> dict[str, Any]:
    bundle = load_json(bundle_path)
    review = load_json(review_status_path)
    second = load_json(second_check_path)
    release = load_json(release_audit_path)
    release_pass = release.get("decision") == "release-audit-pass"
    dossier_blockers = [] if release_pass else ["release-audit"]
    payload = no_claim_payload(
        "candidate-dossier-ready-no-claim",
        release_pass,
        protocol_version=DOSSIER_PROTOCOL_VERSION,
        readiness_stage="review-ready" if release_pass else "blocked",
        readiness_blockers=dossier_blockers,
        bundle_id=bundle.get("bundle_id"),
        blind_sheet_count=len(bundle.get("blind_sheets", [])),
        review_decision=review.get("decision"),
        valid_response_count=review.get("valid_response_count"),
        supportive_response_count=review.get("supportive_response_count"),
        second_check_decision=second.get("decision"),
        release_audit_decision=release.get("decision"),
    )
    write_json(out_json, payload)
    if out_md:
        lines = [
            "# Review Dossier",
            "",
            f"- Bundle: `{payload.get('bundle_id')}`",
            f"- Blind sheets: `{payload.get('blind_sheet_count')}`",
            f"- Review decision: `{payload.get('review_decision')}`",
            f"- Second check: `{payload.get('second_check_decision')}`",
            f"- Release audit: `{payload.get('release_audit_decision')}`",
            f"- Readiness: `{payload.get('readiness_stage')}`",
            f"- Readiness blockers: `{', '.join(payload.get('readiness_blockers') or []) or 'none'}`",
            f"- Public claim allowed: `{payload.get('public_claim_allowed')}`",
            "",
            "No OCR, no transcription, no reading, no public or prize claim.",
        ]
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return payload


def inspect_outputs(paths: list[Path], out_json: Path, out_md: Path | None = None, require_status_ok: bool = False) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_violation_categories: set[str] = set()
    all_blockers: set[str] = set()
    all_readiness_stages: set[str] = set()
    all_readiness_blockers: set[str] = set()
    for path in paths:
        data = load_json(path)
        categories = _string_list(data.get("violation_categories"))
        blockers = _string_list(data.get("blockers"))
        readiness_blockers = _string_list(data.get("readiness_blockers"))
        readiness_stage = data.get("readiness_stage")
        if isinstance(readiness_stage, str) and readiness_stage:
            all_readiness_stages.add(readiness_stage)
        all_violation_categories.update(categories)
        all_blockers.update(blockers)
        all_readiness_blockers.update(readiness_blockers)
        rows.append(
            {
                "path": str(path),
                "decision": data.get("decision"),
                "status_ok": data.get("status_ok"),
                "claim_status": data.get("claim_status"),
                "public_claim_allowed": data.get("public_claim_allowed", False),
                "target_inference_allowed": data.get("target_inference_allowed", False),
                "violation_count": len(data.get("violations") or []),
                "violation_categories": categories,
                "blocker_count": len(data.get("blockers") or []),
                "blockers": blockers,
                "readiness_stage": readiness_stage,
                "readiness_blockers": readiness_blockers,
            }
        )
    for row in rows:
        row_claim_blockers = _claim_safety_blockers(row)
        row["readiness_blockers"] = sorted(set(row["readiness_blockers"]) | set(row_claim_blockers))
        all_readiness_blockers.update(row_claim_blockers)
    unsafe = [
        row
        for row in rows
        if row["public_claim_allowed"] is True
        or row["target_inference_allowed"] is True
        or (row["claim_status"] not in (None, "no-claim"))
    ]
    blocked = [row for row in rows if row["status_ok"] is False]
    if unsafe:
        decision = "inspect-summary-risk-detected"
        status_ok = False
        readiness_stage = "blocked"
        all_readiness_blockers.add("claim-safety")
    elif require_status_ok and blocked:
        decision = "inspect-summary-blocked-no-claim"
        status_ok = False
        readiness_stage = "blocked"
        for row in blocked:
            all_readiness_blockers.update(row.get("readiness_blockers") or [])
            all_readiness_blockers.update(row.get("violation_categories") or [])
            all_readiness_blockers.update(row.get("blockers") or [])
    elif "handoff-ready" in all_readiness_stages:
        decision = "handoff-ready-no-claim"
        status_ok = True
        readiness_stage = "handoff-ready"
    elif RELEASE_READY_INPUT_STAGES.issubset(all_readiness_stages):
        decision = "release-ready-no-claim"
        status_ok = True
        readiness_stage = "release-ready"
    else:
        decision = "inspect-summary-ready-no-claim"
        status_ok = True
        readiness_stage = "summary-ready"
    payload = no_claim_payload(
        decision,
        status_ok,
        inspected_count=len(rows),
        protocol_version=INSPECT_PROTOCOL_VERSION,
        readiness_stage=readiness_stage,
        readiness_stages=sorted(all_readiness_stages),
        readiness_blockers=sorted(all_readiness_blockers),
        require_status_ok=require_status_ok,
        blocked_count=len(blocked),
        risk_count=len(unsafe),
        violation_categories=sorted(all_violation_categories),
        blockers=sorted(all_blockers),
        rows=rows,
    )
    write_json(out_json, payload)
    if out_md:
        lines = [
            "# Inspect Summary",
            "",
            f"- Decision: `{payload.get('decision')}`",
            f"- Status OK: `{payload.get('status_ok')}`",
            f"- Files inspected: `{payload.get('inspected_count')}`",
            f"- Require status OK: `{payload.get('require_status_ok')}`",
            f"- Blocked files: `{payload.get('blocked_count')}`",
            f"- Safety risks: `{payload.get('risk_count')}`",
            f"- Readiness: `{payload.get('readiness_stage')}`",
            f"- Readiness blockers: `{', '.join(payload.get('readiness_blockers') or []) or 'none'}`",
            f"- Violation categories: `{', '.join(payload.get('violation_categories') or []) or 'none'}`",
            f"- Blockers: `{', '.join(payload.get('blockers') or []) or 'none'}`",
            "",
            "| File | Decision | Status OK | Readiness | Categories | Blockers |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                f"| `{row['path']}` | `{row.get('decision')}` | `{row.get('status_ok')}` | `{row.get('readiness_stage') or 'none'}` | `{', '.join(row.get('violation_categories') or []) or 'none'}` | `{', '.join(row.get('blockers') or []) or 'none'}` |"
            )
        lines.extend(["", "No OCR, no transcription, no reading, no public or prize claim."])
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return payload


def prioritize_outputs(paths: list[Path], out_json: Path, out_md: Path | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_readiness_blockers: set[str] = set()
    for path in paths:
        data = load_json(path)
        blockers = _string_list(data.get("readiness_blockers"))
        claim_blockers = _claim_safety_blockers(data)
        all_readiness_blockers.update(blockers)
        all_readiness_blockers.update(claim_blockers)
        row = {
            "path": str(path),
            "decision": data.get("decision"),
            "status_ok": data.get("status_ok"),
            "claim_status": data.get("claim_status"),
            "public_claim_allowed": data.get("public_claim_allowed", False),
            "target_inference_allowed": data.get("target_inference_allowed", False),
            "readiness_stage": data.get("readiness_stage"),
            "readiness_blockers": sorted(set(blockers) | set(claim_blockers)),
            "next_private_step_type": data.get("next_private_step_type"),
            "surface_ready": data.get("surface_ready") is True,
            "controls_present": data.get("controls_present") is True,
        }
        rows.append(row)

    unsafe = [row for row in rows if _claim_safety_blockers(row)]
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            0 if row.get("readiness_stage") == "handoff-ready" and row.get("status_ok") is True else 1,
            len(row.get("readiness_blockers") or []),
            0 if row.get("surface_ready") is True else 1,
            0 if row.get("controls_present") is True else 1,
            str(row.get("path")),
        ),
    )
    ready_count = sum(1 for row in ranked_rows if row.get("readiness_stage") == "handoff-ready" and row.get("status_ok") is True)
    if unsafe:
        decision = "path-priority-risk-detected"
        status_ok = False
        readiness_stage = "blocked"
        all_readiness_blockers.add("claim-safety")
    elif ready_count:
        decision = "path-priority-ready-no-claim"
        status_ok = True
        readiness_stage = "handoff-ready"
    else:
        decision = "path-priority-blocked-no-claim"
        status_ok = False
        readiness_stage = "blocked"
    payload = no_claim_payload(
        decision,
        status_ok,
        protocol_version=PRIORITY_PROTOCOL_VERSION,
        readiness_stage=readiness_stage,
        readiness_blockers=sorted(all_readiness_blockers),
        input_count=len(rows),
        ready_count=ready_count,
        ranked_rows=ranked_rows,
    )
    write_json(out_json, payload)
    if out_md:
        lines = [
            "# Path Priority",
            "",
            f"- Decision: `{payload.get('decision')}`",
            f"- Status OK: `{payload.get('status_ok')}`",
            f"- Inputs: `{payload.get('input_count')}`",
            f"- Ready paths: `{payload.get('ready_count')}`",
            f"- Readiness: `{payload.get('readiness_stage')}`",
            f"- Readiness blockers: `{', '.join(payload.get('readiness_blockers') or []) or 'none'}`",
            "",
            "| Rank | File | Next step | Status OK | Readiness | Blockers |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
        for index, row in enumerate(ranked_rows, start=1):
            lines.append(
                f"| `{index}` | `{row.get('path')}` | `{row.get('next_private_step_type') or 'none'}` | `{row.get('status_ok')}` | `{row.get('readiness_stage') or 'none'}` | `{', '.join(row.get('readiness_blockers') or []) or 'none'}` |"
            )
        lines.extend(["", "No OCR, no transcription, no reading, no public or prize claim."])
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return payload


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


def _dashboard_input_row(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    blockers = sorted(
        set(_string_list(data.get("readiness_blockers")))
        | set(_string_list(data.get("blockers")))
        | set(_string_list(data.get("violation_categories")))
        | set(_claim_safety_blockers(data))
    )
    return {
        "path": str(path),
        "decision": data.get("decision"),
        "status_ok": data.get("status_ok"),
        "claim_status": data.get("claim_status"),
        "public_claim_allowed": data.get("public_claim_allowed", False),
        "target_inference_allowed": data.get("target_inference_allowed", False),
        "readiness_stage": data.get("readiness_stage"),
        "readiness_blockers": blockers,
        "next_private_step_type": data.get("next_private_step_type"),
        "ranked_rows": data.get("ranked_rows") if isinstance(data.get("ranked_rows"), list) else [],
    }


def render_dashboard(paths: list[Path], out_html: Path, session_name: str | None = None) -> dict[str, Any]:
    rows = [_dashboard_input_row(path, load_json(path)) for path in paths]
    all_blockers = sorted({blocker for row in rows for blocker in row.get("readiness_blockers", [])})
    unsafe = [
        row
        for row in rows
        if row["public_claim_allowed"] is True
        or row["target_inference_allowed"] is True
        or row["claim_status"] not in (None, "no-claim")
    ]
    blocked = [row for row in rows if row["status_ok"] is False]
    stages = sorted({str(row["readiness_stage"]) for row in rows if row.get("readiness_stage")})
    priority_rows = [priority_row for row in rows for priority_row in row.get("ranked_rows", []) if isinstance(priority_row, dict)]
    if unsafe:
        decision = "dashboard-risk-detected"
        status_ok = False
        readiness_stage = "blocked"
        if "claim-safety" not in all_blockers:
            all_blockers.append("claim-safety")
    elif blocked:
        decision = "dashboard-blocked-no-claim"
        status_ok = False
        readiness_stage = "blocked"
    elif "handoff-ready" in stages:
        decision = "dashboard-handoff-ready-no-claim"
        status_ok = True
        readiness_stage = "handoff-ready"
    elif "release-ready" in stages:
        decision = "dashboard-release-ready-no-claim"
        status_ok = True
        readiness_stage = "release-ready"
    else:
        decision = "dashboard-ready-no-claim"
        status_ok = True
        readiness_stage = "summary-ready"
    payload = no_claim_payload(
        decision,
        status_ok,
        protocol_version=DASHBOARD_PROTOCOL_VERSION,
        readiness_stage=readiness_stage,
        readiness_blockers=sorted(all_blockers),
        session_name=session_name,
        input_count=len(rows),
        risk_count=len(unsafe),
        blocked_count=len(blocked),
    )
    html = _dashboard_html(payload, rows, priority_rows)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(html, encoding="utf-8", newline="\n")
    return payload


def _dashboard_html(payload: dict[str, Any], rows: list[dict[str, Any]], priority_rows: list[dict[str, Any]]) -> str:
    ladder = ["manifest-valid", "surface-ready", "preflight-ready", "review-ready", "release-ready", "handoff-ready"]
    present_stages = {row.get("readiness_stage") for row in rows}
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        "  <title>Scroll Review Dashboard</title>",
        "  <style>",
        "    :root { color-scheme: light; --ink: #17202a; --muted: #5f6b76; --line: #d8dee4; --ok: #0b6b3a; --bad: #9f1d20; --bg: #f6f8fa; --panel: #ffffff; }",
        "    body { margin: 0; font-family: Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--ink); }",
        "    main { max-width: 1180px; margin: 0 auto; padding: 28px; }",
        "    h1, h2 { margin: 0 0 12px; }",
        "    h1 { font-size: 28px; }",
        "    h2 { font-size: 18px; margin-top: 26px; }",
        "    p { color: var(--muted); line-height: 1.45; }",
        "    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }",
        "    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }",
        "    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0; }",
        "    .value { font-size: 18px; font-weight: 650; overflow-wrap: anywhere; }",
        "    .ok { color: var(--ok); } .bad { color: var(--bad); }",
        "    table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }",
        "    th, td { padding: 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; font-size: 13px; }",
        "    th { background: #edf2f7; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0; }",
        "    tr:last-child td { border-bottom: 0; }",
        "    code { font-family: Consolas, monospace; overflow-wrap: anywhere; }",
        "    .ladder { display: flex; flex-wrap: wrap; gap: 8px; }",
        "    .pill { border: 1px solid var(--line); border-radius: 999px; padding: 7px 10px; background: var(--panel); font-size: 13px; }",
        "    .pill.present { border-color: #88c4a2; color: var(--ok); font-weight: 650; }",
        "  </style>",
        "</head>",
        "<body>",
        "<main>",
        "  <h1>Scroll Review Dashboard</h1>",
        f"  <p><strong>Session:</strong> {_html(payload.get('session_name') or 'none')}</p>",
        "  <p>Local static report from existing JSON outputs. Display-only: no upload, no server, no telemetry. No OCR, no transcription, no reading, no public or prize claim.</p>",
        '  <section class="grid" aria-label="Summary">',
        f'    <div class="card"><div class="label">Decision</div><div class="value">{_html(payload.get("decision"))}</div></div>',
        f'    <div class="card"><div class="label">Status OK</div><div class="value {"ok" if payload.get("status_ok") else "bad"}">{_html(payload.get("status_ok"))}</div></div>',
        f'    <div class="card"><div class="label">Readiness</div><div class="value">{_html(payload.get("readiness_stage"))}</div></div>',
        f'    <div class="card"><div class="label">Inputs</div><div class="value">{_html(payload.get("input_count"))}</div></div>',
        "  </section>",
        "  <h2>Readiness Ladder</h2>",
        '  <div class="ladder">',
    ]
    for stage in ladder:
        present = " present" if stage in present_stages else ""
        lines.append(f'    <span class="pill{present}">{_html(stage)}</span>')
    lines.extend(
        [
            "  </div>",
            "  <h2>Blockers</h2>",
            f"  <p><code>{_html(payload.get('readiness_blockers'))}</code></p>",
            "  <h2>Priority Queue</h2>",
            "  <table>",
            "    <thead><tr><th>Rank</th><th>File</th><th>Next Step</th><th>Status OK</th><th>Readiness</th><th>Blockers</th></tr></thead>",
            "    <tbody>",
        ]
    )
    if priority_rows:
        for index, row in enumerate(priority_rows, start=1):
            lines.append(
                f"      <tr><td>{index}</td><td><code>{_html(row.get('path'))}</code></td><td>{_html(row.get('next_private_step_type'))}</td><td>{_html(row.get('status_ok'))}</td><td>{_html(row.get('readiness_stage'))}</td><td><code>{_html(row.get('readiness_blockers'))}</code></td></tr>"
            )
    else:
        lines.append('      <tr><td colspan="6">none</td></tr>')
    lines.extend(
        [
            "    </tbody>",
            "  </table>",
            "  <h2>Input Files</h2>",
            "  <table>",
            "    <thead><tr><th>File</th><th>Decision</th><th>Status OK</th><th>Claim Status</th><th>Public Claim</th><th>Target Inference</th><th>Readiness</th><th>Next Step</th><th>Blockers</th></tr></thead>",
            "    <tbody>",
        ]
    )
    for row in rows:
        lines.append(
            f"      <tr><td><code>{_html(row.get('path'))}</code></td><td>{_html(row.get('decision'))}</td><td>{_html(row.get('status_ok'))}</td><td>{_html(row.get('claim_status'))}</td><td>{_html(row.get('public_claim_allowed'))}</td><td>{_html(row.get('target_inference_allowed'))}</td><td>{_html(row.get('readiness_stage'))}</td><td>{_html(row.get('next_private_step_type'))}</td><td><code>{_html(row.get('readiness_blockers'))}</code></td></tr>"
        )
    lines.extend(
        [
            "    </tbody>",
            "  </table>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(lines) + "\n"
