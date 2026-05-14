from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

from .common import no_claim_payload, write_json, write_status_markdown

SOURCE_CATALOG_PROTOCOL_VERSION = "data-source-catalog-v1"
WORKSPACE_PROTOCOL_VERSION = "local-data-workspace-v1"
CHUNK_PLAN_PROTOCOL_VERSION = "chunk-download-plan-v1"
CHUNK_FETCH_PROTOCOL_VERSION = "chunk-fetch-status-v1"
SCAN_READINESS_PROTOCOL_VERSION = "scan-data-readiness-v1"

MAX_FETCH_BYTES = 2 * 1024 * 1024
WORKSPACE_MARKER = ".scroll-review-workspace.json"
LOCAL_WORKSPACE_LABEL = "local-workspace-selected"
ALLOWED_PRESETS = {
    "tiny-preview": {"estimated_bytes": 16 * 1024, "bounds": [0, 0, 0, 16, 16, 16]},
    "small-review": {"estimated_bytes": 128 * 1024, "bounds": [0, 0, 0, 64, 64, 32]},
    "manual-bounds": {"estimated_bytes": 256 * 1024, "bounds": [0, 0, 0, 64, 64, 64]},
}
PRESET_EXPLANATIONS = {
    "tiny-preview": {
        "plain_label": "Tiny preview",
        "operator_goal": "Prove that the app, workspace, download limit, checksum, and reports work.",
        "what_you_get": "A very small public/demo chunk for storage and readiness-flow checks.",
        "limitations": "Too small for meaningful visual review; use it to learn the workflow first.",
    },
    "small-review": {
        "plain_label": "Small review",
        "operator_goal": "Prepare a small public chunk for controlled review-readiness triage.",
        "what_you_get": "A bounded chunk that is still small enough to keep local storage predictable.",
        "limitations": "Still not a reading path; it only prepares material for later private review.",
    },
    "manual-bounds": {
        "plain_label": "Manual bounds",
        "operator_goal": "Use explicit bounds from another controlled workflow without guessing here.",
        "what_you_get": "A bounded chunk selected by already-known coordinates from outside this public app.",
        "limitations": "The public app does not discover candidates or infer where interesting material is.",
    },
}


def _preset_summary(preset: str) -> dict[str, Any]:
    info = ALLOWED_PRESETS.get(preset, ALLOWED_PRESETS["tiny-preview"])
    guidance = PRESET_EXPLANATIONS.get(preset, PRESET_EXPLANATIONS["tiny-preview"])
    return {
        "preset": preset,
        "plain_label": guidance["plain_label"],
        "operator_goal": guidance["operator_goal"],
        "what_you_get": guidance["what_you_get"],
        "limitations": guidance["limitations"],
        "estimated_bytes": int(info["estimated_bytes"]),
        "bounds": info["bounds"],
    }


def _adapter_available() -> bool:
    return importlib.util.find_spec("vesuvius") is not None


def _adapter_readiness(adapter: str, available: bool, *, fetch_enabled: bool) -> dict[str, Any]:
    if adapter == "built-in":
        return {
            "status": "ready",
            "status_label": "Ready now",
            "can_plan": True,
            "can_fetch": fetch_enabled,
            "setup_required": False,
            "setup_hint": "Built into this app; no installation or credentials are needed.",
            "credential_required": False,
            "full_volume_allowed": False,
            "public_only": True,
        }
    if available:
        return {
            "status": "adapter-ready",
            "status_label": "Adapter detected",
            "can_plan": True,
            "can_fetch": fetch_enabled,
            "setup_required": False,
            "setup_hint": "Optional public adapter detected. Keep runs small and public-only; this build still blocks full-volume and claim workflows.",
            "credential_required": False,
            "full_volume_allowed": False,
            "public_only": True,
        }
    return {
        "status": "setup-needed",
        "status_label": "Setup needed",
        "can_plan": False,
        "can_fetch": False,
        "setup_required": True,
        "setup_hint": "Optional public adapter is not installed. Use the built-in public demo until the adapter is installed and accepted separately.",
        "credential_required": False,
        "full_volume_allowed": False,
        "public_only": True,
    }


def source_catalog(out_json: Path | None = None) -> dict[str, Any]:
    adapter_available = _adapter_available()
    public_demo_readiness = _adapter_readiness("built-in", True, fetch_enabled=True)
    vesuvius_readiness = _adapter_readiness("vesuvius", adapter_available, fetch_enabled=False)
    payload = no_claim_payload(
        "data-source-catalog-ready",
        True,
        protocol_version=SOURCE_CATALOG_PROTOCOL_VERSION,
        data_source_catalog_protocol_version=SOURCE_CATALOG_PROTOCOL_VERSION,
        readiness_stage="catalog-ready",
        readiness_blockers=[],
        adapter_status="adapter-available" if adapter_available else "adapter-unavailable",
        sources=[
            {
                "source_id": "public-demo",
                "label": "Built-in public demo chunk",
                "public_access": True,
                "adapter": "built-in",
                "adapter_available": True,
                "adapter_readiness": public_demo_readiness,
                "credential_required": False,
                "full_volume_allowed": False,
                "fetch_enabled": True,
                "scan_labels": ["synthetic-public-scroll"],
                "operator_goal": "Learn the end-to-end workflow without private data or large downloads.",
                "why_start_here": "It is always available, tiny, deterministic, and safe for first-run training.",
                "what_you_get": "A synthetic public/demo chunk plus JSON and Markdown readiness summaries.",
                "limitations": "This is not real evidence and cannot support reading, OCR, inference, or claims.",
                "recommended_start_points": [
                    {
                        "scan": "synthetic-public-scroll",
                        "preset": "tiny-preview",
                        "reason": "smallest safe public demo path for checking storage, download, and readiness flow",
                        "why_this_choice": "Use this first to confirm the app can write to your workspace and produce reports.",
                    }
                ],
                "presets": sorted(ALLOWED_PRESETS),
                "preset_guidance": [_preset_summary(preset) for preset in sorted(ALLOWED_PRESETS)],
                "max_fetch_bytes": MAX_FETCH_BYTES,
            },
            {
                "source_id": "vesuvius-public",
                "label": "Vesuvius public adapter",
                "public_access": True,
                "adapter": "vesuvius",
                "adapter_available": adapter_available,
                "adapter_readiness": vesuvius_readiness,
                "credential_required": False,
                "full_volume_allowed": False,
                "fetch_enabled": False,
                "scan_labels": ["catalog-from-adapter"],
                "operator_goal": "Use official public scan access when the optional adapter is installed and accepted.",
                "why_start_here": "Official public tooling can expose remote CT/scroll data without manually handling full volumes.",
                "what_you_get": "A public adapter-backed catalog entry that can be planned as a limited small chunk later.",
                "limitations": "Catalog planning is blocked until the adapter is available; this app still does not fetch full volumes, run OCR, infer letters, or read text.",
                "recommended_start_points": [
                    {
                        "scan": "catalog-from-adapter",
                        "preset": "tiny-preview",
                        "reason": "adapter-backed public catalog entry; use only after adapter availability is confirmed",
                        "why_this_choice": "Start tiny so source access, storage, and limits are proven before any larger public review chunk.",
                    }
                ],
                "presets": sorted(ALLOWED_PRESETS),
                "preset_guidance": [_preset_summary(preset) for preset in sorted(ALLOWED_PRESETS)],
                "max_fetch_bytes": MAX_FETCH_BYTES,
            },
        ],
        public_only=True,
    )
    if out_json:
        write_json(out_json, payload)
    return payload


def _safe_resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _workspace_violations(workspace: Path, repo_root: Path, min_free_bytes: int) -> list[str]:
    violations: list[str] = []
    resolved = _safe_resolve(workspace)
    repo = _safe_resolve(repo_root)
    lower = str(resolved).lower()
    if _is_inside(resolved, repo):
        violations.append("workspace-inside-repo")
    if any(part in lower for part in ["\\windows", "\\program files", "\\appdata\\local\\google\\chrome"]):
        violations.append("workspace-system-or-browser-path")
    if resolved.anchor and resolved == Path(resolved.anchor):
        violations.append("workspace-drive-root")
    try:
        resolved.mkdir(parents=True, exist_ok=True)
        probe = resolved / ".scroll-review-write-test"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        violations.append("workspace-not-writable")
    try:
        free = shutil.disk_usage(resolved).free
        if free < min_free_bytes:
            violations.append("workspace-insufficient-free-space")
    except OSError:
        violations.append("workspace-free-space-unavailable")
    return violations


def check_workspace(
    workspace: Path,
    repo_root: Path,
    out_json: Path | None = None,
    min_free_bytes: int = MAX_FETCH_BYTES,
) -> dict[str, Any]:
    resolved = _safe_resolve(workspace)
    violations = _workspace_violations(resolved, repo_root, min_free_bytes)
    status_ok = not violations
    if status_ok:
        marker = {
            "protocol_version": WORKSPACE_PROTOCOL_VERSION,
            "workspace_label": LOCAL_WORKSPACE_LABEL,
            "public_only": True,
            "claim_safety": "No OCR, no transcription, no reading, no public claim.",
        }
        write_json(resolved / WORKSPACE_MARKER, marker)
    payload = no_claim_payload(
        "local-data-workspace-ready" if status_ok else "local-data-workspace-blocked",
        status_ok,
        protocol_version=WORKSPACE_PROTOCOL_VERSION,
        local_data_workspace_protocol_version=WORKSPACE_PROTOCOL_VERSION,
        readiness_stage="workspace-ready" if status_ok else "blocked",
        readiness_blockers=[] if status_ok else ["workspace"],
        workspace_label=LOCAL_WORKSPACE_LABEL,
        workspace_path=str(resolved),
        workspace_marker=WORKSPACE_MARKER if status_ok else None,
        violations=violations,
        min_free_bytes=min_free_bytes,
    )
    if out_json:
        write_json(out_json, payload)
    return payload


def _catalog_source(source_id: str) -> dict[str, Any] | None:
    for source in source_catalog().get("sources", []):
        if source.get("source_id") == source_id:
            return source
    return None


def plan_chunk(
    source: str,
    scan: str,
    preset: str,
    workspace: Path,
    repo_root: Path,
    out_json: Path | None = None,
) -> dict[str, Any]:
    violations: list[str] = []
    source_row = _catalog_source(source)
    if not source_row:
        violations.append("unknown-source")
    elif not source_row.get("public_access"):
        violations.append("source-not-public")
    elif not (source_row.get("adapter_readiness") or {}).get("can_plan", source_row.get("adapter_available")):
        violations.append("adapter-unavailable")
    if preset not in ALLOWED_PRESETS:
        violations.append("invalid-preset")
    if preset == "full-volume":
        violations.append("full-volume-not-allowed")
    workspace_status = check_workspace(workspace, repo_root)
    if not workspace_status.get("status_ok"):
        violations.append("workspace-blocked")
    preset_info = ALLOWED_PRESETS.get(preset, ALLOWED_PRESETS["tiny-preview"])
    estimated_bytes = int(preset_info["estimated_bytes"])
    if estimated_bytes > MAX_FETCH_BYTES:
        violations.append("estimated-bytes-over-limit")
    if source_row and scan not in source_row.get("scan_labels", []):
        violations.append("scan-not-in-public-catalog")
    status_ok = not violations
    plan = {
        "source": source,
        "scan": scan,
        "preset": preset,
        "bounds": preset_info["bounds"],
        "estimated_bytes": estimated_bytes,
        "workspace_path": str(_safe_resolve(workspace)),
        "workspace_label": LOCAL_WORKSPACE_LABEL,
        "public_only": True,
        "max_fetch_bytes": MAX_FETCH_BYTES,
    }
    preset_guidance = _preset_summary(preset)
    source_label = str(source_row.get("label") or source) if source_row else source
    selection_rationale = {
        "source": source,
        "source_label": source_label,
        "scan": scan,
        "preset": preset,
        "preset_label": preset_guidance["plain_label"],
        "estimated_bytes": estimated_bytes,
        "workspace_label": LOCAL_WORKSPACE_LABEL,
        "why_this_source": str(source_row.get("why_start_here") or "Public source selected from the catalog.") if source_row else "Unknown source.",
        "why_this_scan": "This scan label is listed by the selected public source catalog.",
        "why_this_preset": preset_guidance["operator_goal"],
        "what_you_get": preset_guidance["what_you_get"],
        "limitations": preset_guidance["limitations"],
        "safe_storage": "Raw bytes stay in the selected local workspace; generated summaries stay under demo/out.",
        "not_performed": "No OCR, no transcription, no reading, no inference, no title claim, and no public claim.",
    }
    payload = no_claim_payload(
        "chunk-download-plan-ready" if status_ok else "chunk-download-plan-blocked",
        status_ok,
        protocol_version=CHUNK_PLAN_PROTOCOL_VERSION,
        chunk_download_plan_protocol_version=CHUNK_PLAN_PROTOCOL_VERSION,
        readiness_stage="chunk-plan-ready" if status_ok else "blocked",
        readiness_blockers=[] if status_ok else sorted(set(_plan_blocker(v) for v in violations)),
        plan=plan,
        selection_rationale=selection_rationale,
        violations=violations,
    )
    if out_json:
        write_json(out_json, payload)
    return payload


def _plan_blocker(violation: str) -> str:
    if "workspace" in violation:
        return "workspace"
    if "adapter" in violation or "source" in violation or "catalog" in violation:
        return "source"
    if "volume" in violation or "preset" in violation or "bytes" in violation:
        return "download-scope"
    return "chunk-plan"


def _chunk_bytes(plan: dict[str, Any]) -> bytes:
    seed = json.dumps(
        {
            "source": plan.get("source"),
            "scan": plan.get("scan"),
            "preset": plan.get("preset"),
            "bounds": plan.get("bounds"),
        },
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    size = min(int(plan.get("estimated_bytes") or 0), MAX_FETCH_BYTES)
    repeats = (size // len(digest)) + 1
    return (digest * repeats)[:size]


def fetch_chunk(plan_path: Path, out_json: Path | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    violations: list[str] = []
    if plan_payload.get("protocol_version") != CHUNK_PLAN_PROTOCOL_VERSION:
        violations.append("wrong-plan-protocol-version")
    if not plan_payload.get("status_ok"):
        violations.append("plan-not-ready")
    plan = plan_payload.get("plan") if isinstance(plan_payload.get("plan"), dict) else {}
    source_row = _catalog_source(str(plan.get("source") or ""))
    if source_row and not source_row.get("fetch_enabled"):
        violations.append("fetch-adapter-unavailable")
    elif plan.get("source") != "public-demo":
        violations.append("fetch-adapter-unavailable")
    if plan.get("preset") not in ALLOWED_PRESETS:
        violations.append("invalid-preset")
    if plan.get("preset") == "full-volume":
        violations.append("full-volume-not-allowed")
    estimated_bytes = int(plan.get("estimated_bytes") or 0)
    if estimated_bytes > MAX_FETCH_BYTES:
        violations.append("estimated-bytes-over-limit")
    workspace = _safe_resolve(Path(str(plan.get("workspace_path") or "")))
    if repo_root is not None:
        workspace_status = check_workspace(workspace, repo_root)
        if not workspace_status.get("status_ok"):
            violations.append("workspace-blocked")
    chunk_rel = Path("chunks") / str(plan.get("source")) / str(plan.get("scan")) / str(plan.get("preset")) / "chunk.bin"
    chunk_path = _safe_resolve(workspace / chunk_rel)
    if not _is_inside(chunk_path, workspace):
        violations.append("chunk-path-outside-workspace")
    status_ok = not violations
    byte_count = 0
    checksum = None
    if status_ok:
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        data = _chunk_bytes(plan)
        chunk_path.write_bytes(data)
        byte_count = len(data)
        checksum = hashlib.sha256(data).hexdigest()
    payload = no_claim_payload(
        "chunk-fetch-ready" if status_ok else "chunk-fetch-blocked",
        status_ok,
        protocol_version=CHUNK_FETCH_PROTOCOL_VERSION,
        chunk_fetch_status_protocol_version=CHUNK_FETCH_PROTOCOL_VERSION,
        readiness_stage="chunk-fetched" if status_ok else "blocked",
        readiness_blockers=[] if status_ok else sorted(set(_plan_blocker(v) for v in violations)),
        source=plan.get("source"),
        scan=plan.get("scan"),
        preset=plan.get("preset"),
        workspace_label=LOCAL_WORKSPACE_LABEL,
        chunk_file=f"{LOCAL_WORKSPACE_LABEL}/{chunk_rel.as_posix()}",
        byte_count=byte_count,
        checksum_sha256=checksum,
        selection_rationale=plan_payload.get("selection_rationale") if isinstance(plan_payload.get("selection_rationale"), dict) else None,
        violations=violations,
        public_only=True,
    )
    if out_json:
        write_json(out_json, payload)
    return payload


def scan_readiness(fetch_status_path: Path, out_json: Path, out_md: Path | None = None) -> dict[str, Any]:
    fetch_status = json.loads(fetch_status_path.read_text(encoding="utf-8-sig"))
    violations: list[str] = []
    if fetch_status.get("protocol_version") != CHUNK_FETCH_PROTOCOL_VERSION:
        violations.append("wrong-fetch-protocol-version")
    if not fetch_status.get("status_ok"):
        violations.append("fetch-not-ready")
    status_ok = not violations
    payload = no_claim_payload(
        "scan-data-ready-no-claim" if status_ok else "scan-data-blocked-no-claim",
        status_ok,
        protocol_version=SCAN_READINESS_PROTOCOL_VERSION,
        scan_data_readiness_protocol_version=SCAN_READINESS_PROTOCOL_VERSION,
        readiness_stage="data-ready" if status_ok else "blocked",
        readiness_blockers=[] if status_ok else ["fetch"],
        source=fetch_status.get("source"),
        scan=fetch_status.get("scan"),
        preset=fetch_status.get("preset"),
        workspace_label=fetch_status.get("workspace_label") or LOCAL_WORKSPACE_LABEL,
        byte_count=fetch_status.get("byte_count"),
        checksum_sha256=fetch_status.get("checksum_sha256"),
        operator_summary="Chunk stored locally, checksum recorded, public-only status preserved, and no-claim review summary ready.",
        selection_rationale=fetch_status.get("selection_rationale") if isinstance(fetch_status.get("selection_rationale"), dict) else None,
        next_private_step="review downloaded chunk metadata and decide whether a controlled private analysis is warranted",
        violations=violations,
    )
    write_json(out_json, payload)
    if out_md:
        write_status_markdown(out_md, "Scan Data Readiness", payload)
    return payload
