from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import claim_safety_violations, is_nonempty_string_list, load_json, missing_required, no_claim_payload

SESSION_PROTOCOL_VERSION = "local-review-session-v1"
SESSION_REQUIRED_FIELDS = [
    "session_protocol_version",
    "session_name",
    "dashboard_inputs",
    "claim_safety",
]
FORBIDDEN_SESSION_KEYS = {
    "candidate_id",
    "candidate_ids",
    "coordinate",
    "coordinates",
    "ct_path",
    "discord_export",
    "model_artifact",
    "model_path",
    "private_path",
    "raw_path",
    "reading_result",
    "token",
    "volume_path",
}
FORBIDDEN_DASHBOARD_INPUT_SUFFIXES = {
    ".ckpt",
    ".jpeg",
    ".jpg",
    ".npy",
    ".png",
    ".ppm",
    ".pt",
    ".pth",
    ".safetensors",
    ".tif",
    ".tiff",
    ".zarr",
}
EXTERNAL_URL_RE = re.compile(r"https?://|file://", re.I)
WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:\\")


def _resolve_reference(manifest_path: Path, reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute() or (path.parts and path.parts[0] in {"demo", "docs", "scripts", "scroll_review_tooling", "tests"}):
        return path
    if path.exists():
        return path
    return manifest_path.parent / path


def _scan_forbidden_fields(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            child_prefix = f"{prefix}.{key_text}" if prefix else key_text
            if key_lower in FORBIDDEN_SESSION_KEYS or "candidate" in key_lower:
                findings.append(child_prefix)
            findings.extend(_scan_forbidden_fields(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_scan_forbidden_fields(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        if EXTERNAL_URL_RE.search(value):
            findings.append(f"{prefix}:external-url")
        if WINDOWS_ABSOLUTE_PATH_RE.search(value) or value.startswith("/"):
            findings.append(f"{prefix}:absolute-path")
    return findings


def validate_session_manifest(manifest_path: Path) -> dict[str, Any]:
    data = load_json(manifest_path)
    violations = [f"missing-field:{field}" for field in missing_required(data, SESSION_REQUIRED_FIELDS)]
    if data.get("session_protocol_version") != SESSION_PROTOCOL_VERSION:
        violations.append("wrong-session-protocol-version")
    violations.extend(claim_safety_violations(data.get("claim_safety", "")))
    if data.get("public_claim_allowed") is True:
        violations.append("public-claim-not-allowed")
    if data.get("target_inference_allowed") is True:
        violations.append("target-inference-not-allowed")
    for field in _scan_forbidden_fields(data):
        violations.append(f"forbidden-session-field:{field}")

    dashboard_inputs = data.get("dashboard_inputs")
    resolved_inputs: list[Path] = []
    if not is_nonempty_string_list(dashboard_inputs):
        violations.append("missing-dashboard-inputs")
    else:
        for reference in dashboard_inputs:
            path = _resolve_reference(manifest_path, str(reference))
            resolved_inputs.append(path)
            if path.suffix.lower() != ".json":
                violations.append(f"dashboard-input-not-json:{reference}")
            if path.suffix.lower() in FORBIDDEN_DASHBOARD_INPUT_SUFFIXES:
                violations.append(f"dashboard-input-forbidden-suffix:{reference}")
            if not path.exists():
                violations.append(f"missing-dashboard-input:{reference}")

    dashboard_output = data.get("dashboard_output", "demo/out/dashboard.html")
    if not isinstance(dashboard_output, str) or not dashboard_output:
        violations.append("invalid-dashboard-output")
        dashboard_output = "demo/out/dashboard.html"
    elif Path(dashboard_output).suffix.lower() != ".html":
        violations.append("dashboard-output-not-html")

    status_ok = not violations
    return no_claim_payload(
        "local-review-session-valid" if status_ok else "local-review-session-blocked",
        status_ok,
        protocol_version=SESSION_PROTOCOL_VERSION,
        readiness_stage="session-ready" if status_ok else "blocked",
        readiness_blockers=sorted({session_blocker(violation) for violation in violations}),
        manifest_file=str(manifest_path),
        session_name=data.get("session_name"),
        dashboard_inputs=[path.as_posix() for path in resolved_inputs],
        dashboard_output=_resolve_reference(manifest_path, dashboard_output).as_posix(),
        violations=violations,
    )


def session_blocker(violation: str) -> str:
    if violation.startswith("missing-field:") or violation in {"wrong-session-protocol-version", "invalid-dashboard-output"}:
        return "session-schema"
    if violation.startswith("missing-no-") or violation in {"public-claim-not-allowed", "target-inference-not-allowed"}:
        return "claim-safety"
    if violation.startswith("forbidden-session-field:"):
        return "private-material"
    if violation.startswith("missing-dashboard-input") or violation.startswith("dashboard-input"):
        return "dashboard-inputs"
    if violation == "dashboard-output-not-html":
        return "dashboard-output"
    return "session"


def session_input_paths(session_payload: dict[str, Any]) -> list[Path]:
    return [Path(path) for path in session_payload.get("dashboard_inputs") or []]


def session_output_path(session_payload: dict[str, Any]) -> Path:
    return Path(str(session_payload.get("dashboard_output") or "demo/out/dashboard.html"))
