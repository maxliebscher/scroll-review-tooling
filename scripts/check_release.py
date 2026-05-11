from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scroll_review_tooling.release_audit import FORBIDDEN_TEXT_PATTERNS, is_ignored_generated, is_text

RELEASE_CHECK_PROTOCOL_VERSION = "release-check-v1"
LEAK_SCAN_EXEMPT_FILES = {
    "scroll_review_tooling/release_audit.py",
    "tests/test_check_release.py",
    "tests/test_release_audit.py",
}


def run(check_id: str, label: str, args: list[str]) -> dict[str, str]:
    command = [sys.executable, *args]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        return {"check_id": check_id, "label": label, "command": " ".join(args), "status": "failed", "returncode": str(completed.returncode)}
    return {"check_id": check_id, "label": label, "command": " ".join(args), "status": "ok", "returncode": "0"}


def leak_scan(root: Path = ROOT) -> dict[str, str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in LEAK_SCAN_EXEMPT_FILES or is_ignored_generated(rel) or not is_text(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in FORBIDDEN_TEXT_PATTERNS):
            findings.append(rel)
    if findings:
        raise SystemExit(f"leak-scan-failed: {', '.join(sorted(findings))}")
    return {"check_id": "leak-scan", "label": "leak-scan", "command": "internal release-audit pattern scan", "status": "ok", "returncode": "0"}


def release_check_payload(rows: list[dict[str, str]]) -> dict[str, object]:
    decision = "release-check-pass" if all(row.get("status") == "ok" for row in rows) else "release-check-fail"
    status_ok = decision == "release-check-pass"
    failed_check_ids = [row.get("check_id", "unknown") for row in rows if row.get("status") != "ok"]
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "status_ok": status_ok,
        "release_check_protocol_version": RELEASE_CHECK_PROTOCOL_VERSION,
        "protocol_version": RELEASE_CHECK_PROTOCOL_VERSION,
        "readiness_stage": "release-ready" if status_ok else "blocked",
        "readiness_blockers": failed_check_ids,
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
        "claim_safety": "Release check only; no OCR, no transcription, no reading, no public or prize claim.",
        "checks": rows,
    }


def release_check_markdown(payload: dict[str, object]) -> str:
    rows = payload.get("checks") or []
    lines = [
        "# Release Check",
        "",
        f"- Created: `{payload.get('created')}`",
        f"- Decision: `{payload.get('decision')}`",
        f"- Status OK: `{payload.get('status_ok')}`",
        f"- Protocol: `{payload.get('protocol_version')}`",
        f"- Readiness: `{payload.get('readiness_stage')}`",
        f"- Readiness blockers: `{', '.join(payload.get('readiness_blockers') or []) or 'none'}`",
        f"- Public claim allowed: `{payload.get('public_claim_allowed')}`",
        "",
        "| Check ID | Check | Status | Return Code |",
        "| --- | --- | --- | ---: |",
    ]
    for row in rows:
        if isinstance(row, dict):
            lines.append(f"| `{row.get('check_id')}` | `{row.get('label')}` | `{row.get('status')}` | `{row.get('returncode')}` |")
    lines.extend(["", "No OCR, no transcription, no reading, no public or prize claim."])
    return "\n".join(lines) + "\n"


def build_release_check_payload() -> dict[str, object]:
    rows: list[dict[str, str]] = []
    for row in [
        run("demo", "demo", ["scripts/run_demo.py"]),
        run("operator-doctor", "operator-doctor", ["scripts/operator_doctor.py"]),
        run("operator-server", "operator-server", ["scripts/operator_server.py", "--once"]),
        run(
            "inspect-release-gate",
            "inspect-release-gate",
            [
                "-m",
                "scroll_review_tooling.review_workflow",
                "inspect",
                "--input-json",
                "demo/out/review_pack_status.json",
                "demo/out/surface_review_status.json",
                "demo/out/full_volume_preflight_status.json",
                "demo/out/dossier.json",
                "--out-json",
                "demo/out/inspect_gate_release.json",
                "--out-md",
                "demo/out/inspect_gate_release.md",
                "--require-status-ok",
            ],
        ),
        run("unit-tests", "unit-tests", ["-m", "unittest", "discover", "-s", "tests"]),
        run(
            "release-audit",
            "release-audit",
            [
                "-m",
                "scroll_review_tooling.release_audit",
                "--root",
                ".",
                "--out-json",
                "demo/out/release_audit.json",
            ],
        ),
    ]:
        rows.append(row)
        if row.get("status") != "ok":
            return release_check_payload(rows)
    try:
        rows.append(leak_scan())
    except SystemExit as exc:
        rows.append({"check_id": "leak-scan", "label": "leak-scan", "command": "internal release-audit pattern scan", "status": "failed", "returncode": str(exc.code or 1)})
    return release_check_payload(rows)


def write_outputs(payload: dict[str, object], out_json: str | None = None, out_md: str | None = None) -> None:
    if out_json:
        json_path = Path(out_json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    if out_md:
        md_path = Path(out_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(release_check_markdown(payload), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    args = parser.parse_args()
    payload = build_release_check_payload()
    write_outputs(payload, args.out_json, args.out_md)
    print(json.dumps(payload, indent=2))
    if payload.get("decision") != "release-check-pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
