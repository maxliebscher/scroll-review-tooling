from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NO_CLAIM_SAFETY = "Review tooling only; no OCR, no transcription, no reading, no public or prize claim."


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def sha256_text(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def missing_required(data: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if data.get(field) in (None, "", [])]


def is_nonempty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def claim_safety_violations(value: Any) -> list[str]:
    text = str(value).lower()
    checks = {
        "missing-no-ocr": "no ocr",
        "missing-no-transcription": "no transcription",
        "missing-no-reading": "no reading",
        "missing-no-public-claim": "no public claim",
    }
    return [violation for violation, phrase in checks.items() if phrase not in text]


def no_claim_payload(decision: str, status_ok: bool, **extra: Any) -> dict[str, Any]:
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "status_ok": status_ok,
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
        "claim_safety": NO_CLAIM_SAFETY,
    }
    payload.update(extra)
    return payload


def write_status_markdown(path: Path, title: str, payload: dict[str, Any]) -> None:
    lines = [
        f"# {title}",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Status OK: `{payload.get('status_ok')}`",
        f"- Public claim allowed: `{payload.get('public_claim_allowed')}`",
        f"- Target inference allowed: `{payload.get('target_inference_allowed')}`",
    ]
    violations = payload.get("violations") or []
    blockers = payload.get("blockers") or []
    if violations:
        lines.append(f"- Violations: `{';'.join(violations)}`")
    if blockers:
        lines.append(f"- Blockers: `{';'.join(blockers)}`")
    lines.extend(["", "No OCR, no transcription, no reading, no public or prize claim."])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
