from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_release import build_release_check_payload, write_outputs
from scroll_review_tooling.reports import render_dashboard
from scroll_review_tooling.sessions import session_input_paths, session_output_path, validate_session_manifest

LOCAL_DASHBOARD_PROTOCOL_VERSION = "local-dashboard-launch-v1"


def local_dashboard_payload(release_payload: dict[str, Any], dashboard_path: Path, session_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    release_ok = release_payload.get("decision") == "release-check-pass"
    session_ok = session_payload is None or session_payload.get("status_ok") is True
    dashboard_exists = dashboard_path.exists()
    blockers: list[str] = []
    if not release_ok:
        blockers.append("release-check")
    if not session_ok:
        blockers.append("session")
    if not dashboard_exists:
        blockers.append("missing-dashboard")
    status_ok = not blockers
    try:
        dashboard_display = dashboard_path.relative_to(ROOT).as_posix()
    except ValueError:
        dashboard_display = dashboard_path.as_posix()
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": "local-dashboard-ready" if status_ok else "local-dashboard-blocked",
        "status_ok": status_ok,
        "protocol_version": LOCAL_DASHBOARD_PROTOCOL_VERSION,
        "readiness_stage": "dashboard-ready" if status_ok else "blocked",
        "readiness_blockers": blockers,
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
        "claim_safety": "Local dashboard launcher only; no OCR, no transcription, no reading, no public or prize claim.",
        "dashboard_html": dashboard_display,
        "release_check_decision": release_payload.get("decision"),
        "session_decision": session_payload.get("decision") if session_payload else None,
        "session_name": session_payload.get("session_name") if session_payload else None,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local no-claim checks and report the generated dashboard path.")
    parser.add_argument("--out-json", default="demo/out/local_dashboard.json")
    parser.add_argument("--release-json", default="demo/out/release_check.json")
    parser.add_argument("--release-md", default="demo/out/release_check.md")
    parser.add_argument("--dashboard-html", default="demo/out/dashboard.html")
    parser.add_argument("--session", default="demo/session_manifest.json")
    args = parser.parse_args()

    release_payload = build_release_check_payload()
    write_outputs(release_payload, args.release_json, args.release_md)
    session_payload = validate_session_manifest(ROOT / args.session) if args.session else None
    dashboard_path = ROOT / args.dashboard_html
    if session_payload and session_payload.get("status_ok"):
        dashboard_path = session_output_path(session_payload)
        render_dashboard(session_input_paths(session_payload), dashboard_path, session_name=str(session_payload.get("session_name") or ""))
    result = local_dashboard_payload(release_payload, dashboard_path, session_payload)
    write_json(ROOT / args.out_json, result)
    print(json.dumps(result, indent=2))
    if not result.get("status_ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
