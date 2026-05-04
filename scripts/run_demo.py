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
    print(json.dumps({"decision": "demo-complete", "out_dir": "demo/out"}, indent=2))


if __name__ == "__main__":
    main()
