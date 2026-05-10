from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scroll_review_tooling.common import load_json, no_claim_payload, write_json
from scroll_review_tooling.release_audit import audit
from scroll_review_tooling.review_workflow import attention_delta, make_template, second_check, validate_inbox

SESSION_RUN_PROTOCOL_VERSION = "local-review-session-run-v1"


def slugify(value: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean or "local-review-session"


def default_session_dir(name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return ROOT / "sessions" / f"{stamp}-{slugify(name)}"


def copy_json_inputs(inputs: list[str], inbox: Path) -> list[str]:
    copied: list[str] = []
    for item in inputs:
        source = Path(item)
        if not source.exists() or not source.is_file() or source.suffix.lower() != ".json":
            raise SystemExit(f"session-input-blocked: expected an existing JSON file, got {item}")
        target = inbox / source.name
        shutil.copy2(source, target)
        copied.append(str(target))
    return copied


def write_summary(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Local Review Session",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Status OK: `{payload.get('status_ok')}`",
        f"- Session directory: `{payload.get('session_dir')}`",
        f"- Review decision: `{payload.get('review_decision')}`",
        f"- Second check: `{payload.get('second_check_decision')}`",
        f"- Attention: `{payload.get('attention_decision')}`",
        f"- Release audit: `{payload.get('release_audit_decision')}`",
        f"- Copied inputs: `{payload.get('copied_input_count')}`",
        "",
        "No OCR, no transcription, no reading, no public or prize claim.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build_session(args: argparse.Namespace) -> dict[str, object]:
    session_dir = Path(args.session_dir) if args.session_dir else default_session_dir(args.name)
    if not session_dir.is_absolute():
        session_dir = ROOT / session_dir
    inbox = session_dir / "inbox"
    out = session_dir / "out"
    inbox.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    bundle_path = ROOT / args.bundle
    bundle = load_json(bundle_path)
    template_path = inbox / "response_template.json"
    write_json(template_path, make_template(bundle))

    copied_inputs: list[str] = []
    if args.demo:
        for source in sorted((ROOT / "demo" / "inbox").glob("*.json")):
            if source.name != "response_template.json":
                copied_inputs.extend(copy_json_inputs([str(source)], inbox))
    copied_inputs.extend(copy_json_inputs(args.inputs, inbox))

    review_status = validate_inbox(template_path, inbox, out / "review_status.json", out / "review_status.tsv")
    second = second_check(out / "review_status.json", out / "second_check.json")
    attention = attention_delta(out / "second_check.json", out / "attention_state.json", out / "attention.json")
    release = {"decision": "release-audit-skipped"}
    if not args.no_audit:
        release = audit(ROOT)
        write_json(out / "release_audit.json", release)
    status_ok = release.get("decision") in {"release-audit-pass", "release-audit-skipped"}
    payload = no_claim_payload(
        "local-review-session-ready" if status_ok else "local-review-session-blocked",
        bool(status_ok),
        protocol_version=SESSION_RUN_PROTOCOL_VERSION,
        readiness_stage="session-ready" if status_ok else "blocked",
        readiness_blockers=[] if status_ok else ["release-audit"],
        session_dir=str(session_dir),
        inbox=str(inbox),
        out_dir=str(out),
        bundle=str(bundle_path),
        copied_inputs=copied_inputs,
        copied_input_count=len(copied_inputs),
        review_decision=review_status.get("decision"),
        second_check_decision=second.get("decision"),
        attention_decision=attention.get("decision"),
        release_audit_decision=release.get("decision"),
    )
    write_json(out / "session_status.json", payload)
    write_summary(out / "session_summary.md", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local no-claim review session folder.")
    parser.add_argument("inputs", nargs="*", help="Optional JSON reviewer responses to copy into the session inbox.")
    parser.add_argument("--name", default="local-review-session")
    parser.add_argument("--session-dir")
    parser.add_argument("--bundle", default="demo/bundle_manifest.json")
    parser.add_argument("--demo", action="store_true", help="Seed the session with synthetic demo reviewer input.")
    parser.add_argument("--no-audit", action="store_true", help="Skip release audit for local experimentation.")
    args = parser.parse_args()
    result = build_session(args)
    print(json.dumps(result, indent=2))
    if not result.get("status_ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
