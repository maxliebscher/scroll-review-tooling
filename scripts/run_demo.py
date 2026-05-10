from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    completed = subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> None:
    out = ROOT / "demo" / "out"
    out.mkdir(parents=True, exist_ok=True)
    run(["scroll_review_tooling.review_workflow", "init-template", "--bundle", "demo/bundle_manifest.json", "--out", "demo/inbox/response_template.json"])
    run(["scroll_review_tooling.review_workflow", "validate", "--template", "demo/inbox/response_template.json", "--inbox", "demo/inbox", "--out-json", "demo/out/review_status.json", "--out-tsv", "demo/out/review_status.tsv"])
    run(["scroll_review_tooling.review_workflow", "second-check", "--review-status", "demo/out/review_status.json", "--out-json", "demo/out/second_check.json"])
    run(["scroll_review_tooling.review_workflow", "attention", "--second-check", "demo/out/second_check.json", "--state", "demo/out/attention_state.json", "--out-json", "demo/out/attention.json"])
    run(["scroll_review_tooling.release_audit", "--root", ".", "--out-json", "demo/out/release_audit.json"])
    run(["scroll_review_tooling.review_workflow", "validate-pack", "--manifest", "demo/review_pack_manifest.json", "--out-json", "demo/out/review_pack_status.json", "--out-md", "demo/out/review_pack_status.md"])
    run(["scroll_review_tooling.review_workflow", "surface-review", "--manifest", "demo/surface_review_manifest.json", "--out-json", "demo/out/surface_review_status.json", "--out-md", "demo/out/surface_review_status.md"])
    run(["scroll_review_tooling.review_workflow", "preflight-manifest", "--manifest", "demo/full_volume_preflight_manifest.json", "--out-json", "demo/out/full_volume_preflight_status.json", "--out-md", "demo/out/full_volume_preflight_status.md"])
    run(["scroll_review_tooling.review_workflow", "dossier", "--bundle", "demo/bundle_manifest.json", "--review-status", "demo/out/review_status.json", "--second-check", "demo/out/second_check.json", "--release-audit", "demo/out/release_audit.json", "--out-json", "demo/out/dossier.json", "--out-md", "demo/out/dossier.md"])
    run(["scroll_review_tooling.review_workflow", "handoff", "--manifest", "demo/handoff_manifest.json", "--out-json", "demo/out/handoff_status.json", "--out-md", "demo/out/handoff_status.md"])
    run(["scroll_review_tooling.review_workflow", "inspect", "--input-json", "demo/out/review_status.json", "demo/out/review_pack_status.json", "demo/out/surface_review_status.json", "demo/out/full_volume_preflight_status.json", "demo/out/dossier.json", "--out-json", "demo/out/inspect_summary.json", "--out-md", "demo/out/inspect_summary.md"])
    run(["scroll_review_tooling.review_workflow", "inspect", "--input-json", "demo/out/review_pack_status.json", "demo/out/surface_review_status.json", "demo/out/full_volume_preflight_status.json", "demo/out/dossier.json", "--out-json", "demo/out/inspect_gate.json", "--out-md", "demo/out/inspect_gate.md", "--require-status-ok"])
    run(["scroll_review_tooling.review_workflow", "prioritize", "--input-json", "demo/out/handoff_status.json", "demo/out/inspect_gate.json", "--out-json", "demo/out/path_priority.json", "--out-md", "demo/out/path_priority.md"])
    run(["scroll_review_tooling.review_workflow", "dashboard", "--session", "demo/session_manifest.json"])
    print(json.dumps({"decision": "demo-complete", "out_dir": "demo/out"}, indent=2))


if __name__ == "__main__":
    main()
