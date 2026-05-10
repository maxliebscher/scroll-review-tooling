from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    claim_safety_violations,
    is_nonempty_string_list,
    load_json,
    missing_required,
    no_claim_payload,
    write_json,
    write_status_markdown,
)

REVIEW_PACK_PROTOCOL_VERSION = "review-pack-v1"
SURFACE_REVIEW_PROTOCOL_VERSION = "surface-vc3d-review-v1"
PREFLIGHT_PROTOCOL_VERSION = "full-volume-preflight-v1"
HANDOFF_PROTOCOL_VERSION = "review-to-reading-handoff-v1"
VALID_REVIEW_TYPES = {"blind_signal", "surface_vc3d", "full_volume_preflight", "claim_safety"}
ALLOWED_PRIVATE_STEP_TYPES = {
    "surface-continuity-review",
    "vc3d-sheet-switch-review",
    "ink-model-eval",
    "high-res-rescan-priority",
    "private-reading-review",
}
PACK_REQUIRED_FIELDS = [
    "review_pack_protocol_version",
    "review_type",
    "scroll_id",
    "segment_id",
    "coordinate_frame",
    "source_control_split",
    "training_overlap_statement",
    "render_command",
    "claim_safety",
]
PREFLIGHT_REQUIRED_FIELDS = [
    "preflight_protocol_version",
    "volume_id",
    "chunk_source",
    "data_metadata",
    "coordinate_frame",
    "model_hash",
    "protocol_hash",
    "control_panel",
    "budget",
    "output_path_policy",
    "stop_rules",
    "claim_safety",
]
HANDOFF_REQUIRED_FIELDS = [
    "handoff_protocol_version",
    "source_readiness_files",
    "next_private_step_type",
    "surface_risk_summary",
    "control_requirements",
    "reviewer_requirements",
    "claim_safety",
]
SURFACE_REVIEW_FIELDS = [
    "sheet_switch_visible",
    "layer_continuity_blocker",
    "boundary_or_crop_bias",
    "compressed_region_risk",
    "needs_vc3d_surface_review",
]
FORBIDDEN_HANDOFF_KEYS = {
    "candidate_id",
    "candidate_ids",
    "coordinates",
    "coordinate",
    "ocr_text",
    "inferred_letters",
    "transcription",
    "reading_text",
    "private_path",
    "raw_path",
    "volume_path",
}


def validate_source_control_split(value: Any) -> bool:
    return isinstance(value, dict) and is_nonempty_string_list(value.get("source")) and is_nonempty_string_list(value.get("controls"))


def categorize_violation(violation: str) -> str:
    if violation.startswith("missing-field:"):
        return "missing-required-field"
    if "protocol-version" in violation:
        return "protocol-version"
    if violation.startswith("wrong-handoff-"):
        return "protocol-version"
    if violation in {"invalid-review-type", "wrong-review-type"}:
        return "review-type"
    if violation == "invalid-next-private-step-type":
        return "handoff-step-type"
    if violation in {"missing-scale", "invalid-source-control-split"}:
        return "manifest-shape"
    if violation.startswith("forbidden-handoff-field:"):
        return "claim-safety"
    if violation.startswith("unreadable-source-readiness-file:") or violation.startswith("blocked-source-readiness-file:") or violation == "missing-source-readiness-files":
        return "source-readiness"
    if violation in {"missing-surface-readiness", "sheet-switch-risk"}:
        return "surface-readiness"
    if violation == "missing-controls":
        return "missing-controls"
    if violation == "missing-preflight":
        return "missing-preflight"
    if violation == "review-insufficient":
        return "review-insufficient"
    if violation.startswith("missing-surface-"):
        return "surface-review-schema"
    if violation in {"public-claim-not-allowed", "target-inference-not-allowed", "ocr-language-risk"} or violation.startswith("missing-no-"):
        return "claim-safety"
    if violation == "execution-not-allowed-in-preflight":
        return "preflight-execution"
    if violation == "missing-output-allowlist":
        return "output-policy"
    return "other"


def violation_categories(violations: list[str]) -> list[str]:
    return sorted({categorize_violation(violation) for violation in violations})


def readiness_blockers(violations: list[str], blockers: list[str] | None = None) -> list[str]:
    blocker_values = set(violation_categories(violations))
    blocker_values.update(str(blocker) for blocker in blockers or [])
    return sorted(blocker_values)


def _resolve_reference(manifest_path: Path, reference: str) -> Path:
    path = Path(reference)
    if path.exists():
        return path
    return manifest_path.parent / path


def _forbidden_handoff_keys(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_prefix = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in FORBIDDEN_HANDOFF_KEYS:
                found.append(child_prefix)
            found.extend(_forbidden_handoff_keys(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_handoff_keys(child, f"{prefix}[{index}]"))
    return found


def _bool_field(value: Any, key: str) -> bool:
    return isinstance(value, dict) and value.get(key) is True


def _nonnegative_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def validate_pack(manifest_path: Path, out_json: Path, out_md: Path | None = None) -> dict[str, Any]:
    data = load_json(manifest_path)
    violations = [f"missing-field:{field}" for field in missing_required(data, PACK_REQUIRED_FIELDS)]
    review_type = data.get("review_type")
    if data.get("review_pack_protocol_version") != REVIEW_PACK_PROTOCOL_VERSION:
        violations.append("wrong-review-pack-protocol-version")
    if review_type not in VALID_REVIEW_TYPES:
        violations.append("invalid-review-type")
    if "scale_um_per_px" not in data and not data.get("scale_source"):
        violations.append("missing-scale")
    if not validate_source_control_split(data.get("source_control_split")):
        violations.append("invalid-source-control-split")
    violations.extend(claim_safety_violations(data.get("claim_safety", "")))
    if data.get("public_claim_allowed") is True:
        violations.append("public-claim-not-allowed")
    if data.get("target_inference_allowed") is True:
        violations.append("target-inference-not-allowed")
    if "ocr" in str(data).lower() and "no ocr" not in str(data).lower():
        violations.append("ocr-language-risk")
    decision = "review-pack-valid-no-claim" if not violations else "review-pack-invalid"
    payload = no_claim_payload(
        decision,
        not violations,
        manifest_file=str(manifest_path),
        review_type=review_type,
        protocol_version=data.get("review_pack_protocol_version"),
        readiness_stage="manifest-valid" if not violations else "blocked",
        readiness_blockers=readiness_blockers(violations),
        violations=violations,
        violation_categories=violation_categories(violations),
    )
    write_json(out_json, payload)
    if out_md:
        write_status_markdown(out_md, "Review Pack Status", payload)
    return payload


def validate_surface_review(manifest_path: Path, out_json: Path, out_md: Path | None = None) -> dict[str, Any]:
    data = load_json(manifest_path)
    violations = [f"missing-field:{field}" for field in missing_required(data, PACK_REQUIRED_FIELDS)]
    if data.get("review_pack_protocol_version") != REVIEW_PACK_PROTOCOL_VERSION:
        violations.append("wrong-review-pack-protocol-version")
    if data.get("surface_review_protocol_version") != SURFACE_REVIEW_PROTOCOL_VERSION:
        violations.append("wrong-surface-review-protocol-version")
    if data.get("review_type") != "surface_vc3d":
        violations.append("wrong-review-type")
    if not validate_source_control_split(data.get("source_control_split")):
        violations.append("invalid-source-control-split")
    violations.extend(claim_safety_violations(data.get("claim_safety", "")))
    metrics = data.get("surface_metrics")
    if not isinstance(metrics, dict):
        violations.append("missing-surface-metrics")
    else:
        for key in ["tifxyz_continuity", "valid_coverage", "neighbor_jump_p95", "layer_triplet_stability"]:
            if key not in metrics:
                violations.append(f"missing-surface-metric:{key}")
    reviewer = data.get("surface_review_fields")
    blockers: list[str] = []
    if not isinstance(reviewer, dict):
        violations.append("missing-surface-review-fields")
    else:
        for key in SURFACE_REVIEW_FIELDS:
            if key not in reviewer:
                violations.append(f"missing-surface-review-field:{key}")
            elif reviewer.get(key) is True:
                blockers.append(key)
    if blockers:
        decision = "surface-review-blocked-no-claim"
    elif violations:
        decision = "surface-review-invalid"
    else:
        decision = "surface-review-ready-no-claim"
    payload = no_claim_payload(
        decision,
        not violations and not blockers,
        manifest_file=str(manifest_path),
        protocol_version=data.get("surface_review_protocol_version"),
        readiness_stage="surface-ready" if not violations and not blockers else "blocked",
        readiness_blockers=readiness_blockers(violations, blockers),
        violations=violations,
        violation_categories=violation_categories(violations),
        blockers=blockers,
    )
    write_json(out_json, payload)
    if out_md:
        write_status_markdown(out_md, "Surface Review Status", payload)
    return payload


def validate_preflight_manifest(manifest_path: Path, out_json: Path, out_md: Path | None = None) -> dict[str, Any]:
    data = load_json(manifest_path)
    violations = [f"missing-field:{field}" for field in missing_required(data, PREFLIGHT_REQUIRED_FIELDS)]
    if data.get("preflight_protocol_version") != PREFLIGHT_PROTOCOL_VERSION:
        violations.append("wrong-preflight-protocol-version")
    violations.extend(claim_safety_violations(data.get("claim_safety", "")))
    if data.get("public_claim_allowed") is True:
        violations.append("public-claim-not-allowed")
    if data.get("execute") is True:
        violations.append("execution-not-allowed-in-preflight")
    output_policy = data.get("output_path_policy")
    if not isinstance(output_policy, dict) or not output_policy.get("allowlist"):
        violations.append("missing-output-allowlist")
    decision = "full-volume-preflight-ready-no-claim" if not violations else "full-volume-preflight-invalid"
    payload = no_claim_payload(
        decision,
        not violations,
        manifest_file=str(manifest_path),
        protocol_version=data.get("preflight_protocol_version"),
        readiness_stage="preflight-ready" if not violations else "blocked",
        readiness_blockers=readiness_blockers(violations),
        violations=violations,
        violation_categories=violation_categories(violations),
        execute_allowed=False,
    )
    write_json(out_json, payload)
    if out_md:
        write_status_markdown(out_md, "Full-Volume Preflight Status", payload)
    return payload


def validate_handoff_manifest(manifest_path: Path, out_json: Path, out_md: Path | None = None) -> dict[str, Any]:
    data = load_json(manifest_path)
    violations = [f"missing-field:{field}" for field in missing_required(data, HANDOFF_REQUIRED_FIELDS)]
    if data.get("handoff_protocol_version") != HANDOFF_PROTOCOL_VERSION:
        violations.append("wrong-handoff-protocol-version")
    next_step = data.get("next_private_step_type")
    if next_step not in ALLOWED_PRIVATE_STEP_TYPES:
        violations.append("invalid-next-private-step-type")
    violations.extend(claim_safety_violations(data.get("claim_safety", "")))
    if data.get("public_claim_allowed") is True:
        violations.append("public-claim-not-allowed")
    if data.get("target_inference_allowed") is True:
        violations.append("target-inference-not-allowed")
    for key_path in _forbidden_handoff_keys(data):
        violations.append(f"forbidden-handoff-field:{key_path}")

    source_files = data.get("source_readiness_files")
    source_rows: list[dict[str, Any]] = []
    source_stages: set[str] = set()
    source_blockers: set[str] = set()
    if not is_nonempty_string_list(source_files):
        violations.append("missing-source-readiness-files")
    else:
        for reference in source_files:
            path = _resolve_reference(manifest_path, str(reference))
            try:
                source = load_json(path)
            except Exception as exc:
                violations.append(f"unreadable-source-readiness-file:{reference}:{type(exc).__name__}")
                continue
            stage = source.get("readiness_stage")
            blockers = [str(blocker) for blocker in source.get("readiness_blockers") or []]
            if isinstance(stage, str):
                source_stages.add(stage)
            source_blockers.update(blockers)
            source_rows.append(
                {
                    "path": str(reference),
                    "decision": source.get("decision"),
                    "status_ok": source.get("status_ok"),
                    "readiness_stage": stage,
                    "readiness_blockers": blockers,
                }
            )
            if source.get("status_ok") is False:
                violations.append(f"blocked-source-readiness-file:{reference}")

    surface_summary = data.get("surface_risk_summary")
    if not isinstance(surface_summary, dict):
        violations.append("missing-surface-risk-summary")
    elif surface_summary.get("surface_ready") is not True:
        violations.append("missing-surface-readiness")
    if _bool_field(surface_summary, "sheet_switch_risk"):
        violations.append("sheet-switch-risk")
    if _bool_field(surface_summary, "compressed_region_risk"):
        source_blockers.add("compressed-region-risk")

    control_requirements = data.get("control_requirements")
    if not isinstance(control_requirements, dict) or control_requirements.get("controls_present") is not True or _nonnegative_int(control_requirements.get("control_count")) <= 0:
        violations.append("missing-controls")

    reviewer_requirements = data.get("reviewer_requirements")
    if not isinstance(reviewer_requirements, dict) or _nonnegative_int(reviewer_requirements.get("required_review_count")) <= 0:
        violations.append("review-insufficient")

    if "surface-ready" not in source_stages:
        violations.append("missing-surface-readiness")
    if "preflight-ready" not in source_stages:
        violations.append("missing-preflight")
    if "review-ready" not in source_stages:
        violations.append("review-insufficient")

    handoff_blockers = readiness_blockers(violations, sorted(source_blockers))
    if not violations:
        decision = "review-to-reading-handoff-ready-no-claim"
        status_ok = True
        readiness_stage = "handoff-ready"
    elif "claim-safety" in handoff_blockers:
        decision = "review-to-reading-handoff-risk-detected"
        status_ok = False
        readiness_stage = "blocked"
    else:
        decision = "review-to-reading-handoff-blocked-no-claim"
        status_ok = False
        readiness_stage = "blocked"
    payload = no_claim_payload(
        decision,
        status_ok,
        manifest_file=str(manifest_path),
        protocol_version=data.get("handoff_protocol_version"),
        readiness_stage=readiness_stage,
        readiness_blockers=handoff_blockers,
        next_private_step_type=next_step,
        source_readiness_count=len(source_rows),
        source_readiness_stages=sorted(source_stages),
        source_readiness_rows=source_rows,
        surface_ready=_bool_field(surface_summary, "surface_ready"),
        controls_present=isinstance(control_requirements, dict) and control_requirements.get("controls_present") is True,
        reviewer_summary=data.get("reviewer_requirements", {}).get("reviewer_summary") if isinstance(data.get("reviewer_requirements"), dict) else None,
        violations=violations,
        violation_categories=violation_categories(violations),
    )
    write_json(out_json, payload)
    if out_md:
        write_status_markdown(out_md, "Review-to-Reading Handoff Status", payload)
    return payload
