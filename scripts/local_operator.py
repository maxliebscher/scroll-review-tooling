from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_release import build_release_check_payload, write_outputs
from scroll_review_tooling.operator_app import render_operator_app
from scroll_review_tooling.reports import render_dashboard
from scroll_review_tooling.sessions import session_input_paths, session_output_path, validate_session_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local no-claim operator start page and dashboard.")
    parser.add_argument("--session", default="demo/session_manifest.json")
    parser.add_argument("--operator-html", default="demo/out/operator.html")
    parser.add_argument("--out-json", default="demo/out/local_operator.json")
    parser.add_argument("--out-md", default="demo/out/operator_summary.md")
    parser.add_argument("--release-json", default="demo/out/release_check.json")
    parser.add_argument("--release-md", default="demo/out/release_check.md")
    args = parser.parse_args()

    release_payload = build_release_check_payload()
    write_outputs(release_payload, args.release_json, args.release_md)
    session_payload = validate_session_manifest(ROOT / args.session)
    dashboard_html = session_output_path(session_payload) if session_payload.get("status_ok") else ROOT / "demo/out/dashboard.html"
    if session_payload.get("status_ok"):
        dashboard_payload = render_dashboard(
            session_input_paths(session_payload),
            dashboard_html,
            session_name=str(session_payload.get("session_name") or ""),
        )
    else:
        dashboard_payload = {
            "decision": "dashboard-blocked-no-claim",
            "status_ok": False,
            "readiness_stage": "blocked",
            "readiness_blockers": ["session"],
            "claim_status": "no-claim",
            "public_claim_allowed": False,
            "target_inference_allowed": False,
        }
    result = render_operator_app(
        out_html=ROOT / args.operator_html,
        out_json=ROOT / args.out_json,
        out_md=ROOT / args.out_md,
        repo_root=ROOT,
        session_payload=session_payload,
        release_payload=release_payload,
        dashboard_payload=dashboard_payload,
        dashboard_html=dashboard_html,
    )
    print(json.dumps(result, indent=2))
    if not result.get("status_ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
