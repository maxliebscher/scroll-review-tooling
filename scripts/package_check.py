from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_release import package_candidate_files, package_findings

PACKAGE_CHECK_PROTOCOL_VERSION = "package-check-v1"


def build_package_check_payload(root: Path = ROOT) -> dict[str, object]:
    candidates = package_candidate_files(root)
    findings = package_findings(root, candidates)
    status_ok = not findings
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": "package-check-pass" if status_ok else "package-check-blocked",
        "status_ok": status_ok,
        "protocol_version": PACKAGE_CHECK_PROTOCOL_VERSION,
        "readiness_stage": "package-ready" if status_ok else "blocked",
        "readiness_blockers": findings,
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
        "claim_safety": "Packaging dry-run only; no OCR, no transcription, no reading, no public or prize claim.",
        "package_scope": "Tracked and unignored untracked files only. No archive is written by this check.",
        "archive_written": False,
        "candidate_count": len(candidates),
        "finding_count": len(findings),
        "findings": findings,
    }


def write_json(path: str | None, payload: dict[str, object]) -> None:
    if not path:
        return
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run whether the current checkout is safe to place in a local ZIP-style package.")
    parser.add_argument("--root", default=str(ROOT), help="Repository root to inspect.")
    parser.add_argument("--out-json", help="Optional JSON output path.")
    args = parser.parse_args(argv)

    payload = build_package_check_payload(Path(args.root).resolve())
    write_json(args.out_json, payload)

    if payload["status_ok"]:
        print(f"package-check: ok ({payload['candidate_count']} files inspected; no archive written)")
        return 0
    print("package-check: blocked")
    for finding in payload["findings"]:
        print(f"- {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
