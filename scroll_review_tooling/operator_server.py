from __future__ import annotations

from html import escape
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .common import load_json
from .data_sources import (
    ALLOWED_PRESETS,
    CHUNK_FETCH_PROTOCOL_VERSION,
    CHUNK_PLAN_PROTOCOL_VERSION,
    LOCAL_WORKSPACE_LABEL,
    PRESET_EXPLANATIONS,
    SCAN_READINESS_PROTOCOL_VERSION,
    SOURCE_CATALOG_PROTOCOL_VERSION,
    WORKSPACE_PROTOCOL_VERSION,
    check_workspace,
    fetch_chunk,
    plan_chunk,
    scan_readiness,
    source_catalog,
)
from .operator_doctor import OPERATOR_DOCTOR_PROTOCOL_VERSION

PROJECT_NAME = "scroll-review-tooling"
OPERATOR_SERVER_PROTOCOL_VERSION = "local-operator-server-v1"
GITHUB_REPO_URL = "https://github.com/maxliebscher/scroll-review-tooling"
ALLOWED_PRESET_BYTES = {key: int(value["estimated_bytes"]) for key, value in ALLOWED_PRESETS.items()}
ALLOWED_REPORTS = {
    "operator": "demo/out/operator.html",
    "dashboard": "demo/out/dashboard.html",
    "setup": "demo/out/operator_doctor.html",
    "summary": "demo/out/operator_summary.md",
    "status": "demo/out/local_operator.json",
    "release": "demo/out/release_check.json",
    "source-catalog": "demo/out/source_catalog.json",
    "chunk-fetch": "demo/out/chunk_fetch_status.json",
    "scan-readiness": "demo/out/scan_data_readiness.json",
}
OUTPUT_REPORT_KEYS = {
    "demo/out/operator_doctor.html": "setup",
    "demo/out/source_catalog.json": "source-catalog",
    "demo/out/chunk_fetch_status.json": "chunk-fetch",
    "demo/out/scan_data_readiness.md": "scan-readiness",
    "demo/out/scan_data_readiness.json": "scan-readiness",
    "demo/out/dashboard.html": "dashboard",
}


def _html(value: Any) -> str:
    if value is None or value == "":
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_html(item) for item in value) or "none"
    return escape(str(value), quote=True)


def _project_version(repo_root: Path | None = None) -> str:
    if repo_root is not None:
        pyproject = repo_root / "pyproject.toml"
        if pyproject.exists():
            try:
                in_project = False
                for raw_line in pyproject.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if line == "[project]":
                        in_project = True
                        continue
                    if in_project and line.startswith("[") and line.endswith("]"):
                        break
                    if in_project and line.startswith("version"):
                        _, value = line.split("=", 1)
                        return value.strip().strip('"').strip("'")
            except OSError:
                pass
    try:
        return package_version(PROJECT_NAME)
    except PackageNotFoundError:
        return "unknown"


def _suggested_workspace(repo_root: Path) -> str:
    return str((repo_root.parent / "scroll-review-workspace").resolve())


def _run_python(repo_root: Path, args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def run_setup(repo_root: Path) -> dict[str, Any]:
    result = _run_python(repo_root, ["scripts/operator_doctor.py"])
    return {"action": "setup", **result, "status": read_status(repo_root)}


def run_operator(repo_root: Path) -> dict[str, Any]:
    result = _run_python(repo_root, ["scripts/local_operator.py"])
    return {"action": "operator", **result, "status": read_status(repo_root)}


def run_source_catalog(repo_root: Path) -> dict[str, Any]:
    payload = source_catalog(repo_root / "demo/out/source_catalog.json")
    return {"action": "source-catalog", "ok": bool(payload.get("status_ok")), "payload": payload}


def run_workspace_check(repo_root: Path, workspace: str) -> dict[str, Any]:
    if not workspace:
        return {"action": "check-workspace", "ok": False, "error": "workspace-required"}
    payload = check_workspace(Path(workspace), repo_root, repo_root / "demo/out/local_data_workspace.json")
    return {"action": "check-workspace", "ok": bool(payload.get("status_ok")), "payload": payload}


def run_chunk_plan(repo_root: Path, workspace: str, source: str, scan: str, preset: str) -> dict[str, Any]:
    if not workspace:
        return {"action": "plan-chunk", "ok": False, "error": "workspace-required"}
    payload = plan_chunk(
        source or "public-demo",
        scan or "synthetic-public-scroll",
        preset or "tiny-preview",
        Path(workspace),
        repo_root,
        repo_root / "demo/out/chunk_download_plan.json",
    )
    return {"action": "plan-chunk", "ok": bool(payload.get("status_ok")), "payload": payload}


def run_chunk_fetch(repo_root: Path) -> dict[str, Any]:
    plan_path = repo_root / "demo/out/chunk_download_plan.json"
    if not plan_path.exists():
        return {"action": "fetch-chunk", "ok": False, "error": "chunk-plan-required"}
    payload = fetch_chunk(plan_path, repo_root / "demo/out/chunk_fetch_status.json", repo_root=repo_root)
    return {"action": "fetch-chunk", "ok": bool(payload.get("status_ok")), "payload": payload}


def run_scan_readiness(repo_root: Path) -> dict[str, Any]:
    fetch_path = repo_root / "demo/out/chunk_fetch_status.json"
    if not fetch_path.exists():
        return {"action": "scan-readiness", "ok": False, "error": "chunk-fetch-required"}
    payload = scan_readiness(
        fetch_path,
        repo_root / "demo/out/scan_data_readiness.json",
        repo_root / "demo/out/scan_data_readiness.md",
    )
    return {"action": "scan-readiness", "ok": bool(payload.get("status_ok")), "payload": payload}


def run_guided_chunk_flow(repo_root: Path, workspace: str, source: str, scan: str, preset: str) -> dict[str, Any]:
    if not workspace:
        return {
            "action": "guided-chunk-flow",
            "ok": False,
            "decision": "guided-chunk-flow-blocked",
            "next_step": "Choose a local workspace folder outside this repo, then run the data step again.",
            "steps": [{"step": "workspace", "ok": False, "decision": "workspace-required"}],
        }
    steps: list[dict[str, Any]] = []
    catalog = source_catalog(repo_root / "demo/out/source_catalog.json")
    steps.append({"step": "catalog", "ok": bool(catalog.get("status_ok")), "decision": catalog.get("decision")})
    workspace_status = check_workspace(Path(workspace), repo_root, repo_root / "demo/out/local_data_workspace.json")
    steps.append({"step": "workspace", "ok": bool(workspace_status.get("status_ok")), "decision": workspace_status.get("decision")})
    if not workspace_status.get("status_ok"):
        return _guided_result(False, steps, "Fix the workspace blocker, then retry the data flow.")
    plan = plan_chunk(
        source or "public-demo",
        scan or "synthetic-public-scroll",
        preset or "tiny-preview",
        Path(workspace),
        repo_root,
        repo_root / "demo/out/chunk_download_plan.json",
    )
    steps.append({"step": "plan", "ok": bool(plan.get("status_ok")), "decision": plan.get("decision")})
    if not plan.get("status_ok"):
        return _guided_result(False, steps, "Choose a public source, supported scan, and small preset, then retry.")
    fetched = fetch_chunk(
        repo_root / "demo/out/chunk_download_plan.json",
        repo_root / "demo/out/chunk_fetch_status.json",
        repo_root=repo_root,
    )
    steps.append({"step": "fetch", "ok": bool(fetched.get("status_ok")), "decision": fetched.get("decision")})
    if not fetched.get("status_ok"):
        return _guided_result(False, steps, "Inspect chunk_fetch_status.json and fix the blocked fetch step.")
    readiness = scan_readiness(
        repo_root / "demo/out/chunk_fetch_status.json",
        repo_root / "demo/out/scan_data_readiness.json",
        repo_root / "demo/out/scan_data_readiness.md",
    )
    steps.append({"step": "readiness", "ok": bool(readiness.get("status_ok")), "decision": readiness.get("decision")})
    return _guided_result(
        bool(readiness.get("status_ok")),
        steps,
        "Chunk stored in your selected workspace. Readiness summary created under demo/out. Open review reports for the no-claim review package.",
    )


def _guided_result(ok: bool, steps: list[dict[str, Any]], next_step: str) -> dict[str, Any]:
    generated_outputs = [
        "demo/out/source_catalog.json",
        "demo/out/local_data_workspace.json",
        "demo/out/chunk_download_plan.json",
        "demo/out/chunk_fetch_status.json",
        "demo/out/scan_data_readiness.json",
        "demo/out/scan_data_readiness.md",
    ]
    return {
        "action": "guided-chunk-flow",
        "ok": ok,
        "decision": "guided-chunk-flow-ready" if ok else "guided-chunk-flow-blocked",
        "readiness_stage": "data-ready" if ok else "blocked",
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
        "next_step": next_step,
        "generated_outputs": generated_outputs if ok else [],
        "operator_result_summary": (
            "Chunk stored locally; no-claim readiness summary created; reports can be opened."
            if ok
            else "Data flow blocked before a review-ready summary could be created."
        ),
        "steps": steps,
    }


def _safe_step_state(path: Path, expected_protocol: str) -> dict[str, Any]:
    if not path.exists():
        return {"decision": None, "violations": []}
    try:
        payload = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"decision": "invalid-json", "violations": ["invalid-json"]}
    violations: list[str] = []
    if payload.get("protocol_version") != expected_protocol:
        violations.append("wrong-protocol-version")
    if payload.get("status_ok") is not True:
        violations.append("status-not-ok")
    if payload.get("claim_status") != "no-claim":
        violations.append("claim-status-not-no-claim")
    if payload.get("public_claim_allowed") is not False:
        violations.append("public-claim-enabled")
    if payload.get("target_inference_allowed") is not False:
        violations.append("target-inference-enabled")
    for item in payload.get("violations") or []:
        if isinstance(item, str):
            violations.append(item)
    return {
        "decision": str(payload.get("decision") or "unknown"),
        "violations": sorted(set(violations)),
    }


def _safe_list(path: Path, key: str) -> list[str]:
    if not path.exists():
        return []
    value = load_json(path).get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _default_selected_data_summary() -> dict[str, Any]:
    catalog = source_catalog()
    source = next((item for item in catalog.get("sources", []) if item.get("source_id") == "public-demo"), {})
    starts = source.get("recommended_start_points") or []
    start = starts[0] if starts and isinstance(starts[0], dict) else {}
    preset = str(start.get("preset") or "tiny-preview")
    preset_guidance = PRESET_EXPLANATIONS.get(preset, PRESET_EXPLANATIONS["tiny-preview"])
    return {
        "source": str(source.get("source_id") or "public-demo"),
        "source_label": str(source.get("label") or "Built-in public demo chunk"),
        "scan": str(start.get("scan") or "synthetic-public-scroll"),
        "preset": preset,
        "preset_label": preset_guidance["plain_label"],
        "estimated_bytes": 16 * 1024,
        "workspace_label": LOCAL_WORKSPACE_LABEL,
        "why_this_choice": str(start.get("why_this_choice") or source.get("why_start_here") or "Safe default public/demo path."),
        "what_you_get": preset_guidance["what_you_get"],
        "not_performed": "No OCR, no transcription, no reading, no inference, no title claim, and no public claim.",
    }


def _selected_data_summary(plan_path: Path, readiness_path: Path) -> dict[str, Any]:
    summary = _default_selected_data_summary()
    payload: dict[str, Any] = {}
    if readiness_path.exists():
        payload = load_json(readiness_path)
    elif plan_path.exists():
        payload = load_json(plan_path)
    rationale = payload.get("selection_rationale") if isinstance(payload.get("selection_rationale"), dict) else {}
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    if rationale or plan:
        summary.update(
            {
                "source_label": str(rationale.get("source_label") or plan.get("source") or summary["source_label"]),
                "source": str(rationale.get("source") or plan.get("source") or summary["source"]),
                "scan": str(rationale.get("scan") or plan.get("scan") or summary["scan"]),
                "preset": str(rationale.get("preset") or plan.get("preset") or summary["preset"]),
                "preset_label": str(rationale.get("preset_label") or summary["preset_label"]),
                "estimated_bytes": int(rationale.get("estimated_bytes") or plan.get("estimated_bytes") or summary["estimated_bytes"]),
                "workspace_label": str(rationale.get("workspace_label") or plan.get("workspace_label") or LOCAL_WORKSPACE_LABEL),
                "why_this_choice": str(rationale.get("why_this_source") or rationale.get("why_this_choice") or summary["why_this_choice"]),
                "what_you_get": str(rationale.get("what_you_get") or summary["what_you_get"]),
                "not_performed": str(rationale.get("not_performed") or summary["not_performed"]),
            }
        )
    if payload.get("operator_summary"):
        summary["what_you_get"] = str(payload.get("operator_summary"))
    return summary


def _explain_wizard_state(step_id: str, decision: str | None, violations: list[str] | None = None) -> str:
    if decision is None:
        waiting = {
            "setup": "Run the setup check before choosing data.",
            "workspace": "Choose or accept a local workspace outside this repository.",
            "source": "Check the public source catalog.",
            "plan": "Create a tiny public chunk plan.",
            "fetch": "Fetch the planned tiny chunk into the workspace.",
            "readiness": "Create the no-claim readiness summary.",
            "review": "Finish the previous steps before opening review reports.",
        }
        return waiting.get(step_id, "Run this step to continue.")
    violation_set = set(violations or [])
    if "workspace-inside-repo" in violation_set:
        return "The workspace is inside this repository. Choose a folder outside the repo so raw chunks are not tracked."
    if "workspace-not-writable" in violation_set:
        return "The app cannot write to that folder. Choose a folder where your Windows user has write permission."
    if "workspace-system-or-browser-path" in violation_set or "workspace-drive-root" in violation_set:
        return "That folder is too broad or system-owned. Use a normal project workspace folder instead."
    if "adapter-unavailable" in violation_set:
        return "The optional public adapter is not available. Use the built-in public demo or install the adapter separately."
    if "scan-not-in-public-catalog" in violation_set:
        return "That scan is not listed for the selected public source. Pick one of the catalog scan labels."
    if "full-volume-not-allowed" in violation_set:
        return "Full-volume downloads are blocked. Choose tiny-preview or small-review."
    if "estimated-bytes-over-limit" in violation_set:
        return "That chunk is too large for the public-safe flow. Choose a smaller preset."
    if "workspace-blocked" in violation_set:
        return "The selected workspace is blocked. Fix the workspace step before planning or fetching."
    if "plan-not-ready" in violation_set:
        return "The chunk plan is not ready yet. Create a valid small public chunk plan first."
    if "fetch-adapter-unavailable" in violation_set:
        return "Fetching from that adapter is not available in this public build. Use the built-in public demo."
    if "chunk-plan-required" in violation_set:
        return "Create a chunk plan before fetching."
    if "chunk-fetch-required" in violation_set:
        return "Fetch a chunk before creating the readiness summary."
    if "wrong-protocol-version" in violation_set:
        return "The generated JSON has the wrong protocol version. Regenerate this step before continuing."
    if "status-not-ok" in violation_set:
        return "The generated JSON says this step is not OK yet. Fix the listed blocker and rerun the step."
    if {"public-claim-enabled", "target-inference-enabled", "claim-status-not-no-claim"} & violation_set:
        return "This output violates the no-claim boundary. Regenerate it with public claims and target inference disabled."
    if _decision_level(decision) == "bad":
        return "This step is blocked. Open Advanced details for the exact local JSON output."
    if _decision_level(decision) == "ok":
        return "This step is ready."
    return "Review this step before continuing."


def _decision_label(step_id: str, decision: str | None) -> str:
    if decision is None:
        return "Not run yet"
    if _decision_level(decision) == "bad":
        blocked = {
            "setup": "Setup blocked",
            "workspace": "Workspace blocked",
            "source": "Catalog blocked",
            "plan": "Chunk plan blocked",
            "fetch": "Fetch blocked",
            "readiness": "Summary blocked",
            "review": "Review blocked",
        }
        return blocked.get(step_id, "Blocked")
    if _decision_level(decision) == "ok":
        ready = {
            "setup": "Setup passed",
            "workspace": "Workspace ready",
            "source": "Public catalog ready",
            "plan": "Chunk plan ready",
            "fetch": "Chunk fetched",
            "readiness": "Readiness summary created",
            "review": "Review reports ready",
        }
        return ready.get(step_id, "Ready")
    return "Needs review"


def _wizard_step(
    step_id: str,
    label: str,
    decision: str | None,
    description: str,
    output: str,
    violations: list[str] | None = None,
) -> dict[str, str]:
    if decision is None:
        level = "warn"
        status = "waiting"
    elif violations:
        level = "bad"
        status = "blocked"
    else:
        level = _decision_level(decision)
        if level == "bad":
            status = "blocked"
        elif level == "ok":
            status = "ready"
        else:
            status = "review"
    return {
        "step_id": step_id,
        "label": label,
        "status": status,
        "level": level,
        "decision": decision or "not run",
        "decision_label": _decision_label(step_id, decision),
        "description": description,
        "output": output,
        "help": _explain_wizard_state(step_id, decision, violations),
    }


def _build_operator_wizard(
    status_ok: bool,
    doctor_decision: str | None,
    source_decision: str | None,
    workspace_decision: str | None,
    plan_decision: str | None,
    fetch_decision: str | None,
    readiness_decision: str | None,
    violations_by_step: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    violations_by_step = violations_by_step or {}
    required_decisions = [
        doctor_decision,
        workspace_decision,
        source_decision,
        plan_decision,
        fetch_decision,
        readiness_decision,
    ]
    required_steps = ["setup", "workspace", "source", "plan", "fetch", "readiness"]
    contracts_ready = all(not violations_by_step.get(step) for step in required_steps)
    review_decision = (
        "review-ready"
        if contracts_ready and all(_decision_level(decision) == "ok" for decision in required_decisions)
        else None
    )
    steps = [
        _wizard_step("setup", "Setup", doctor_decision, "Check Python, generated output folders, and local files.", "demo/out/operator_doctor.html", violations_by_step.get("setup")),
        _wizard_step("workspace", "Workspace", workspace_decision, "Choose a local folder for raw chunk files.", "demo/out/local_data_workspace.json", violations_by_step.get("workspace")),
        _wizard_step("source", "Choose data", source_decision, "Choose a public source and scan label.", "demo/out/source_catalog.json", violations_by_step.get("source")),
        _wizard_step("plan", "Limit chunk", plan_decision, "Limit the selection to a small public chunk.", "demo/out/chunk_download_plan.json", violations_by_step.get("plan")),
        _wizard_step("fetch", "Save locally", fetch_decision, "Save only the limited planned chunk in your workspace.", "demo/out/chunk_fetch_status.json", violations_by_step.get("fetch")),
        _wizard_step("readiness", "Create summary", readiness_decision, "Create a no-claim data-readiness summary.", "demo/out/scan_data_readiness.md", violations_by_step.get("readiness")),
        _wizard_step("review", "Review", review_decision, "Open local review reports and share summary.", "demo/out/dashboard.html", violations_by_step.get("review")),
    ]
    active = next((step for step in steps if step["status"] != "ready"), steps[-1])
    completed_steps = sum(1 for step in steps[:-1] if step["status"] == "ready")
    if active["step_id"] == "review" and review_decision:
        mode = "ready"
        mode_label = "Review ready"
    elif completed_steps == 0:
        mode = "fresh"
        mode_label = "First run"
    else:
        mode = "in-progress"
        mode_label = f"{completed_steps}/6 steps ready"
    action_map = {
        "setup": ("run-setup", "Check setup", "action"),
        "workspace": ("check-workspace", "Check workspace", "source-action"),
        "source": ("source-catalog", "Check public catalog", "source-action"),
        "plan": ("plan-chunk", "Create chunk plan", "source-action"),
        "fetch": ("fetch-chunk", "Save chunk locally", "source-action"),
        "readiness": ("scan-readiness", "Create readiness summary", "source-action"),
        "review": ("dashboard", "Open review reports", "report"),
    }
    next_action, next_label, action_type = action_map[active["step_id"]]
    blockers = [f'{step["label"]}: {step["help"]}' for step in steps if step["status"] == "blocked"]
    outputs = [step["output"] for step in steps if step["status"] == "ready"]
    return {
        "active_step": active["step_id"],
        "active_label": active["label"],
        "active_description": active["description"],
        "next_action": next_action,
        "next_action_label": next_label,
        "next_action_type": action_type,
        "blockers": blockers,
        "outputs": outputs,
        "mode": mode,
        "mode_label": mode_label,
        "completed_steps": completed_steps,
        "total_steps": 6,
        "steps": steps,
    }


def read_status(repo_root: Path) -> dict[str, Any]:
    status_path = repo_root / "demo/out/local_operator.json"
    doctor_path = repo_root / "demo/out/operator_doctor.json"
    release_path = repo_root / "demo/out/release_check.json"
    source_catalog_path = repo_root / "demo/out/source_catalog.json"
    workspace_path = repo_root / "demo/out/local_data_workspace.json"
    chunk_plan_path = repo_root / "demo/out/chunk_download_plan.json"
    fetch_path = repo_root / "demo/out/chunk_fetch_status.json"
    scan_readiness_path = repo_root / "demo/out/scan_data_readiness.json"
    payload: dict[str, Any] = {
        "protocol_version": OPERATOR_SERVER_PROTOCOL_VERSION,
        "app_version": _project_version(repo_root),
        "suggested_workspace": _suggested_workspace(repo_root),
        "server_scope": "127.0.0.1-only",
        "allowed_actions": ["run-setup", "run-operator", "open-generated-report"],
        "allowed_reports": ALLOWED_REPORTS,
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
    }
    if status_path.exists():
        operator = load_json(status_path)
        payload.update(
            {
                "decision": operator.get("decision"),
                "status_ok": operator.get("status_ok"),
                "readiness_stage": operator.get("readiness_stage"),
                "readiness_blockers": operator.get("readiness_blockers"),
                "operator_headline_status": operator.get("operator_headline_status"),
                "operator_next_step": operator.get("operator_next_step"),
                "operator_tasks": operator.get("operator_tasks") or [],
                "operator_shareable_outputs": operator.get("operator_shareable_outputs") or [],
            }
        )
    else:
        payload.update(
            {
                "decision": "operator-not-run",
                "status_ok": False,
                "readiness_stage": "not-started",
                "readiness_blockers": ["operator-not-run"],
                "operator_headline_status": "Start by checking setup",
                "operator_next_step": "Click Check setup, choose the suggested workspace, then follow the highlighted data steps.",
                "operator_tasks": [],
                "operator_shareable_outputs": [],
            }
        )
    step_states = {
        "setup": _safe_step_state(doctor_path, OPERATOR_DOCTOR_PROTOCOL_VERSION),
        "source": _safe_step_state(source_catalog_path, SOURCE_CATALOG_PROTOCOL_VERSION),
        "workspace": _safe_step_state(workspace_path, WORKSPACE_PROTOCOL_VERSION),
        "plan": _safe_step_state(chunk_plan_path, CHUNK_PLAN_PROTOCOL_VERSION),
        "fetch": _safe_step_state(fetch_path, CHUNK_FETCH_PROTOCOL_VERSION),
        "readiness": _safe_step_state(scan_readiness_path, SCAN_READINESS_PROTOCOL_VERSION),
    }
    if step_states["setup"]["decision"] is not None:
        payload["doctor_decision"] = step_states["setup"]["decision"]
    if release_path.exists():
        payload["release_check_decision"] = str(load_json(release_path).get("decision") or "unknown")
    if workspace_path.exists():
        workspace_payload = load_json(workspace_path)
        payload["workspace_input_value"] = str(workspace_payload.get("workspace_path") or _suggested_workspace(repo_root))
    else:
        payload["workspace_input_value"] = _suggested_workspace(repo_root)
    payload["selected_data_summary"] = _selected_data_summary(chunk_plan_path, scan_readiness_path)
    for key, step in [
        ("source_catalog_decision", "source"),
        ("workspace_decision", "workspace"),
        ("chunk_plan_decision", "plan"),
        ("chunk_fetch_decision", "fetch"),
        ("scan_readiness_decision", "readiness"),
    ]:
        if step_states[step]["decision"] is not None:
            payload[key] = step_states[step]["decision"]
    violations_by_step = {step: state["violations"] for step, state in step_states.items()}
    payload["operator_wizard"] = _build_operator_wizard(
        bool(payload.get("status_ok")),
        step_states["setup"]["decision"],
        step_states["source"]["decision"],
        step_states["workspace"]["decision"],
        step_states["plan"]["decision"],
        step_states["fetch"]["decision"],
        step_states["readiness"]["decision"],
        violations_by_step,
    )
    return payload


def _status_level(status: dict[str, Any]) -> str:
    if status.get("status_ok"):
        return "ok"
    blockers = status.get("readiness_blockers") or []
    if blockers and blockers != ["operator-not-run"]:
        return "bad"
    return "warn"


def _meter_width(status: dict[str, Any]) -> int:
    if status.get("status_ok"):
        return 88
    blockers = status.get("readiness_blockers") or []
    if blockers and blockers != ["operator-not-run"]:
        return 34
    return 18


def _blocker_count(status: dict[str, Any]) -> int:
    blockers = status.get("readiness_blockers") or []
    return len([blocker for blocker in blockers if blocker and blocker != "operator-not-run"])


def _queue_rows(status: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = [task for task in status.get("operator_tasks") or [] if isinstance(task, dict)]
    if tasks:
        rows: list[dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            task_status = str(task.get("status") or "").lower()
            if task_status in {"done", "ok", "pass", "ready"}:
                level = "ok"
            elif task_status in {"blocked", "failed", "fail", "error"}:
                level = "bad"
            else:
                level = "warn"
            rows.append(
                {
                    "rank": index,
                    "label": task.get("label") or task.get("task_id") or f"Step {index}",
                    "detail": task.get("action") or task.get("output") or "Review generated status.",
                    "decision": task.get("status") or "review",
                    "level": level,
                    "meter": 86 if level == "ok" else 24 if level == "bad" else 56,
                }
            )
        return rows
    if status.get("status_ok"):
        return [
            {
                "rank": 1,
                "label": "Generated review package",
                "detail": "Dashboard and no-claim summary are ready to inspect.",
                "decision": "ready",
                "level": "ok",
                "meter": 88,
            }
        ]
    return [
        {
            "rank": 1,
            "label": "Check setup",
            "detail": "Run the local setup check before building the dashboard.",
            "decision": "start",
            "level": "warn",
            "meter": 22,
        },
        {
            "rank": 2,
            "label": "Build demo dashboard",
            "detail": "Generate local reports from existing review-status JSON.",
            "decision": "waiting",
            "level": "warn",
            "meter": 12,
        },
    ]


def _lane_items(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lanes: dict[str, list[dict[str, Any]]] = {"Blocked": [], "Needs review": [], "Ready": []}
    for row in rows:
        if row.get("level") == "bad":
            lanes["Blocked"].append(row)
        elif row.get("level") == "ok":
            lanes["Ready"].append(row)
        else:
            lanes["Needs review"].append(row)
    return lanes


def _render_meter(width: int, level: str) -> str:
    return f'<div class="meter"><i class="m-{_html(level)}" style="width:{max(0, min(100, width))}%"></i></div>'


def _decision_level(decision: Any) -> str:
    text = str(decision or "").lower()
    if not text or text in {"none", "not checked", "not planned", "not generated", "waiting"}:
        return "warn"
    if any(marker in text for marker in ["blocked", "failed", "fail", "error", "required", "not-ready"]):
        return "bad"
    if any(marker in text for marker in ["ready", "pass", "ok"]):
        return "ok"
    return "warn"


def _operator_flow_steps(status: dict[str, Any]) -> list[dict[str, str]]:
    catalog = status.get("source_catalog_decision") or "waiting"
    workspace = status.get("workspace_decision") or "waiting"
    plan = status.get("chunk_plan_decision") or "waiting"
    chunk = status.get("chunk_fetch_decision") or "waiting"
    readiness_status = status.get("scan_readiness_decision") or "waiting"
    review_status = "ready" if status.get("status_ok") or _decision_level(readiness_status) == "ok" else "waiting"
    return [
        {
            "label": "Choose workspace",
            "status": str(workspace),
            "next": "Type a local folder outside this repo.",
            "output": "demo/out/local_data_workspace.json",
            "level": _decision_level(workspace),
        },
        {
            "label": "Check source",
            "status": str(catalog),
            "next": "Use the built-in public demo or a public adapter catalog.",
            "output": "demo/out/source_catalog.json",
            "level": _decision_level(catalog),
        },
        {
            "label": "Plan small chunk",
            "status": str(plan),
            "next": "Create a bounded tiny/small chunk plan.",
            "output": "demo/out/chunk_download_plan.json",
            "level": _decision_level(plan),
        },
        {
            "label": "Fetch small chunk",
            "status": str(chunk),
            "next": "Save only the planned chunk in the local workspace.",
            "output": "local workspace + demo/out/chunk_fetch_status.json",
            "level": _decision_level(chunk),
        },
        {
            "label": "Create readiness summary",
            "status": str(readiness_status),
            "next": "Generate a no-claim summary before review.",
            "output": "demo/out/scan_data_readiness.md",
            "level": _decision_level(readiness_status),
        },
        {
            "label": "Review reports",
            "status": str(review_status),
            "next": "Open the dashboard and share summary when ready.",
            "output": "demo/out/dashboard.html",
            "level": _decision_level(review_status),
        },
    ]


def _render_flow_rows(steps: list[dict[str, str]]) -> str:
    rows: list[str] = []
    for step in steps:
        level = step.get("level") or "warn"
        rows.append(
            '<div class="result-row">'
            f'<span class="state-dot {_html(level)}"></span>'
            f'<div><strong>{_html(step.get("label"))}</strong><div class="muted">{_html(step.get("next"))}</div></div>'
            f'<div class="result-status {_html(level)}">{_html(step.get("status"))}</div>'
            f'<code>{_html(step.get("output"))}</code>'
            "</div>"
        )
    return "\n".join(rows)


def _safe_catalog_sources() -> list[dict[str, Any]]:
    try:
        sources = source_catalog().get("sources") or []
    except Exception:  # pragma: no cover - defensive UI fallback
        return []
    return [source for source in sources if isinstance(source, dict) and source.get("public_access")]


def _render_source_options(sources: list[dict[str, Any]], selected: str = "public-demo") -> str:
    rows: list[str] = []
    for source in sources:
        source_id = str(source.get("source_id") or "")
        if not source_id:
            continue
        readiness = source.get("adapter_readiness") if isinstance(source.get("adapter_readiness"), dict) else {}
        can_plan = bool(readiness.get("can_plan", source.get("adapter_available")))
        status = str(readiness.get("status_label") or ("Ready now" if can_plan else "Setup needed"))
        setup_hint = str(readiness.get("setup_hint") or ("Ready now." if can_plan else "Optional public adapter is not installed, so planning is blocked for this source."))
        selected_attr = " selected" if source_id == selected else ""
        rows.append(
            f'<option value="{_html(source_id)}"{selected_attr} '
            f'data-label="{_html(source.get("label") or source_id)}" '
            f'data-status="{_html(status)}" '
            f'data-adapter-available="{_html(can_plan)}" '
            f'data-setup-hint="{_html(setup_hint)}" '
            f'data-why="{_html(source.get("why_start_here") or "Public source selected from the catalog.")}" '
            f'data-what="{_html(source.get("what_you_get") or "A bounded public chunk summary.")}">'
            f'{_html(source.get("label") or source_id)} - {_html(status)}</option>'
        )
    return "\n".join(rows) or '<option value="public-demo">Built-in public demo - ready</option>'


def _render_scan_options(sources: list[dict[str, Any]], selected: str = "synthetic-public-scroll") -> str:
    seen: set[str] = set()
    rows: list[str] = []
    for source in sources:
        for scan in source.get("scan_labels") or []:
            scan_id = str(scan)
            if scan_id and scan_id not in seen:
                seen.add(scan_id)
                selected_attr = " selected" if scan_id == selected else ""
                rows.append(f'<option value="{_html(scan_id)}"{selected_attr}>{_html(scan_id)}</option>')
    return "\n".join(rows) or '<option value="synthetic-public-scroll">synthetic-public-scroll</option>'


def _render_preset_options(sources: list[dict[str, Any]], selected: str = "tiny-preview") -> str:
    seen: set[str] = set()
    values: list[str] = []
    for source in sources:
        for preset in source.get("presets") or []:
            preset_id = str(preset)
            if preset_id and preset_id not in seen:
                seen.add(preset_id)
                values.append(preset_id)
    preferred = ["tiny-preview", "small-review", "manual-bounds"]
    ordered = [item for item in preferred if item in seen]
    ordered.extend(sorted(item for item in values if item not in preferred))
    rows = []
    for preset_id in ordered:
        guidance = PRESET_EXPLANATIONS.get(preset_id)
        label = str(guidance.get("plain_label") if guidance else preset_id)
        estimated = ALLOWED_PRESET_BYTES.get(preset_id, 0)
        selected_attr = " selected" if preset_id == selected else ""
        rows.append(
            f'<option value="{_html(preset_id)}"{selected_attr} '
            f'data-label="{_html(label)}" '
            f'data-estimated-bytes="{_html(estimated)}" '
            f'data-what="{_html(guidance.get("what_you_get") if guidance else "A bounded public chunk.")}" '
            f'data-goal="{_html(guidance.get("operator_goal") if guidance else "Keep the chunk small and controlled.")}">'
            f'{_html(label)}</option>'
        )
    return "\n".join(rows) or '<option value="tiny-preview">tiny-preview</option>'


def _format_bytes(value: Any) -> str:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return "unknown size"
    if count >= 1024 * 1024:
        return f"{count / (1024 * 1024):.1f} MB"
    if count >= 1024:
        return f"{count // 1024} KB"
    return f"{count} bytes"


def _render_catalog_cards(sources: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for source in sources:
        readiness = source.get("adapter_readiness") if isinstance(source.get("adapter_readiness"), dict) else {}
        can_plan = bool(readiness.get("can_plan", source.get("adapter_available")))
        level = "ok" if can_plan else "warn"
        status = str(readiness.get("status_label") or ("ready" if can_plan else "adapter not installed"))
        setup_hint = str(readiness.get("setup_hint") or "")
        starts = source.get("recommended_start_points") or []
        reason = "public small-chunk source"
        scan = "choose from catalog"
        preset = "tiny-preview"
        if starts and isinstance(starts[0], dict):
            reason = str(starts[0].get("reason") or reason)
            scan = str(starts[0].get("scan") or scan)
            preset = str(starts[0].get("preset") or preset)
        presets = source.get("presets") or []
        size = "small-chunk only"
        if source.get("max_fetch_bytes"):
            size = f"max {_format_bytes(source.get('max_fetch_bytes'))}"
        rows.append(
            '<div class="flow-card">'
            f'<span class="state-dot {_html(level)}"></span>'
            f'<strong>{_html(source.get("label") or source.get("source_id"))}</strong>'
            f'<span class="{_html(level)}">{_html(status)}</span>'
            f'<p><strong>Start:</strong> {_html(scan)} / {_html(preset)}</p>'
            f'<p><strong>Scope:</strong> {_html(size)}; presets: {_html(", ".join(str(item) for item in presets) or "none")}</p>'
            f'<p><strong>Why here?</strong> {_html(source.get("why_start_here") or reason)}</p>'
            f'<p><strong>What you get:</strong> {_html(source.get("what_you_get") or "A bounded public chunk summary.")}</p>'
            f'<p><strong>Limit:</strong> {_html(source.get("limitations") or "No reading, OCR, inference, or claims.")}</p>'
            f'<p><strong>Access:</strong> public-only; credentials {_html("not needed" if not source.get("credential_required") else "blocked")}; full volumes {_html("blocked" if not source.get("full_volume_allowed") else "not recommended")}</p>'
            f'<p><strong>Setup:</strong> {_html(setup_hint)}</p>'
            "</div>"
        )
    return "\n".join(rows) or '<div class="flow-card"><strong>Built-in public demo</strong><span class="ok">ready</span><p>Small synthetic public flow for setup and storage checks.</p></div>'


def _selected_source_row(sources: list[dict[str, Any]], selected: dict[str, Any]) -> dict[str, Any]:
    source_id = str(selected.get("source") or "public-demo")
    return next((source for source in sources if str(source.get("source_id") or "") == source_id), {})


def _render_data_journey() -> str:
    steps = [
        ("Public source", "Only public, no-login sources enter the flow."),
        ("Catalog scan label", "Pick a scan listed by that public catalog."),
        ("Small chunk preset", "Choose tiny-preview first, not a full volume."),
        ("Local workspace", "Raw bytes stay in your chosen local folder."),
        ("Readiness summary", "The app records checksum, status, and blockers."),
        ("Review report", "Open the no-claim report before any private next step."),
    ]
    rows: list[str] = []
    for index, (title, body) in enumerate(steps, start=1):
        rows.append(
            f'<div class="journey-node" title="{_html(body)}">'
            f'<span>{index}</span>'
            f'<strong>{_html(title)}</strong>'
            f'<p>{_html(body)}</p>'
            "</div>"
        )
    return (
        '<section id="data-journey" class="panel data-journey" aria-label="Data journey explanation">'
        '<div class="journey-copy">'
        '<div><div class="label">Data journey</div>'
        '<h2>What data gets picked, and why?</h2></div>'
        '<p>Public source to small chunk to local review report. The details sit in the active wizard step.</p>'
        "</div>"
        '<div class="journey-map">'
        + "\n".join(rows)
        + "</div>"
        '<div class="journey-boundary"><strong>Important boundary:</strong> this is selection and readiness only. No full-volume download, no private credentials, no OCR, no inference, no reading, no title claim.</div>'
        "</section>"
    )


def _render_preset_guidance() -> str:
    rows: list[str] = []
    for preset in ("tiny-preview", "small-review", "manual-bounds"):
        guidance = PRESET_EXPLANATIONS[preset]
        rows.append(
            '<div class="preset-card">'
            f'<strong>{_html(guidance["plain_label"])}</strong>'
            f'<p>{_html(guidance["operator_goal"])}</p>'
            f'<small>{_html(guidance["limitations"])}</small>'
            "</div>"
        )
    return "\n".join(rows)


def _render_selection_focus(sources: list[dict[str, Any]], active_step: str, selected: dict[str, Any]) -> str:
    if active_step not in {"source", "plan", "fetch", "readiness"}:
        return ""
    size = _format_bytes(selected.get("estimated_bytes"))
    source_row = _selected_source_row(sources, selected)
    readiness = source_row.get("adapter_readiness") if isinstance(source_row.get("adapter_readiness"), dict) else {}
    source_ready = bool(readiness.get("can_plan", source_row.get("adapter_available", True)))
    source_level = "ok" if source_ready else "warn"
    source_status = str(readiness.get("status_label") or ("Ready now" if source_ready else "Setup needed before this source can be planned"))
    source_hint = str(
        readiness.get("setup_hint")
        or (
            "This source can be used for the next chunk plan."
            if source_ready
            else "The optional public adapter is not available. Keep the built-in demo selected unless the adapter is installed."
        )
    )
    return (
        '<div class="selection-focus" aria-label="Data selection explanation">'
        '<div class="label">Choose public data</div>'
        '<h2>Pick a small, explainable starting point.</h2>'
        '<p>Start with the built-in public demo unless you have an available public adapter. The app shows what will be stored locally before it fetches anything.</p>'
        f'<div id="selection-source-status" class="source-status {source_level}"><strong>{_html(source_status)}</strong><span>{_html(source_hint)}</span></div>'
        '<div class="selection-summary">'
        f'<div><span>Source</span><strong id="selection-source-summary">{_html(selected.get("source_label"))}</strong></div>'
        f'<div><span>Scan label</span><strong id="selection-scan-summary">{_html(selected.get("scan"))}</strong></div>'
        f'<div><span>Preset</span><strong id="selection-preset-summary">{_html(selected.get("preset_label") or selected.get("preset"))}</strong></div>'
        f'<div><span>Estimated size</span><strong id="selection-size-summary">{_html(size)}</strong></div>'
        f'<div><span>Storage</span><strong id="selection-storage-summary">{_html(selected.get("workspace_label"))}</strong></div>'
        "</div>"
        f'<p><strong>Why this choice?</strong> <span id="selection-why-summary">{_html(selected.get("why_this_choice"))}</span></p>'
        f'<p><strong>What you get next:</strong> <span id="selection-what-summary">{_html(selected.get("what_you_get"))}</span></p>'
        f'<p><strong>Not performed:</strong> {_html(selected.get("not_performed"))}</p>'
        '<div class="wizard-form compact-selectors" aria-label="Public data selectors">'
        f'  <label>Source<select id="source-input">{_render_source_options(sources, str(selected.get("source") or "public-demo"))}</select></label>'
        f'  <label>Scan<select id="scan-input">{_render_scan_options(sources, str(selected.get("scan") or "synthetic-public-scroll"))}</select></label>'
        f'  <label>Preset<select id="preset-input">{_render_preset_options(sources, str(selected.get("preset") or "tiny-preview"))}</select></label>'
        + "</div>"
        "</div>"
    )


def _render_wizard_steps(steps: list[dict[str, Any]], active_step: str) -> str:
    rows: list[str] = []
    for index, step in enumerate(steps, start=1):
        active = " active" if step.get("step_id") == active_step else ""
        level = str(step.get("level") or "warn")
        rows.append(
            f'<div class="wizard-step {active}">'
            f'<span class="state-dot {_html(level)}"></span>'
            f'<div><strong>{index}. {_html(step.get("label"))}</strong>'
            f'<small>{_html(step.get("status"))} - {_html(step.get("decision_label") or step.get("decision"))}</small></div>'
            "</div>"
        )
    return "\n".join(rows)


def _render_wizard_outputs(outputs: list[Any]) -> str:
    if not outputs:
        return '<li><code title="none yet">none yet</code></li>'
    rows = []
    for output in outputs:
        text = str(output)
        prefix = "workspace + " if text.startswith("local workspace + ") else ""
        clean = text.removeprefix("local workspace + ").replace("\\", "/")
        parts = clean.split("/")
        label = f"{prefix}{parts[-2]}/{parts[-1]}" if len(parts) >= 2 else f"{prefix}{clean}"
        report_key = OUTPUT_REPORT_KEYS.get(clean)
        if report_key:
            rows.append(
                f'<li><a class="output-link" href="/report/{_html(report_key)}" target="_blank" rel="noreferrer" title="{_html(text)}">{_html(label)}</a></li>'
            )
        else:
            rows.append(f'<li><code title="{_html(text)}">{_html(label)}</code></li>')
    return "\n".join(rows)


def _render_next_action(wizard: dict[str, Any]) -> str:
    label = _html(wizard.get("next_action_label"))
    action = _html(wizard.get("next_action"))
    action_type = wizard.get("next_action_type")
    if action_type == "action":
        return f'<button class="primary" type="button" data-primary-next data-action="{action}">{label}</button>'
    if action_type == "source-action":
        return f'<button class="primary" type="button" data-primary-next data-source-action="{action}">{label}</button>'
    if action_type == "report":
        return '<a class="button primary" data-primary-next href="/report/dashboard" target="_blank" rel="noreferrer">Open review reports</a>'
    return f'<button class="primary" type="button" data-primary-next disabled>{label}</button>'


def _render_mode_card(wizard: dict[str, Any]) -> str:
    mode = str(wizard.get("mode") or "fresh")
    if mode == "ready":
        title = "Ready to review"
        body = "The safe local summaries are ready. Open the reports, share only generated no-claim outputs, and keep raw evidence in the workspace."
    elif mode == "in-progress":
        title = "Continue the current run"
        body = "Follow the active step. The app keeps raw chunk files in the selected workspace and writes only summaries under demo/out."
    else:
        title = "First run"
        body = "Start here. The app checks your local setup, creates a safe workspace outside the repo, then builds a no-claim review summary from a tiny public/demo chunk."
    return (
        f'<div class="mode-card { _html(mode) }">'
        f'<strong>{_html(title)}</strong>'
        f'<p>{_html(body)}</p>'
        "</div>"
    )


def render_home(status: dict[str, Any]) -> str:
    app_version = str(status.get("app_version") or "unknown")
    action_nonce = str(status.get("local_action_nonce") or "")
    suggested_workspace = str(status.get("suggested_workspace") or "")
    workspace_input_value = str(status.get("workspace_input_value") or suggested_workspace)
    status_level = _status_level(status)
    catalog_sources = _safe_catalog_sources()
    selected_data = status.get("selected_data_summary") if isinstance(status.get("selected_data_summary"), dict) else _default_selected_data_summary()
    queue_rows = _queue_rows(status)
    lanes = _lane_items(queue_rows)
    flow_steps = _operator_flow_steps(status)
    wizard = status.get("operator_wizard")
    if not isinstance(wizard, dict):
        wizard = _build_operator_wizard(
            bool(status.get("status_ok")),
            status.get("doctor_decision"),
            status.get("source_catalog_decision"),
            status.get("workspace_decision"),
            status.get("chunk_plan_decision"),
            status.get("chunk_fetch_decision"),
            status.get("scan_readiness_decision"),
            status.get("wizard_violations_by_step") if isinstance(status.get("wizard_violations_by_step"), dict) else None,
        )
    wizard_steps = [step for step in wizard.get("steps", []) if isinstance(step, dict)]
    active_step = str(wizard.get("active_step") or "setup")
    wizard_mode = str(wizard.get("mode") or "fresh")
    is_first_run = wizard_mode == "fresh"
    needs_workspace = active_step in {"workspace", "plan", "fetch", "readiness"}
    is_workspace_step = active_step == "workspace"
    active_row = next((step for step in wizard_steps if step.get("step_id") == active_step), wizard_steps[0] if wizard_steps else {})
    wizard_blockers = [item for item in wizard.get("blockers", []) if item]
    blocker_count = max(_blocker_count(status), len(wizard_blockers))
    if wizard_mode == "ready":
        status_level = "ok"
        readiness = 100
    else:
        status_level = "bad" if wizard_blockers else "warn"
        total_steps = max(int(wizard.get("total_steps") or 6), 1)
        readiness = min(92, max(10, int((int(wizard.get("completed_steps") or 0) / total_steps) * 100)))
    claim_status = status.get("claim_status") or "no-claim"
    safety_width = 100 if claim_status == "no-claim" and not status.get("public_claim_allowed") else 20
    report_cards = [
        ("Setup report", "setup", "Checks Python, files, output folder, and session shape."),
        ("Operator report", "operator", "Plain-language status page."),
        ("Dashboard", "dashboard", "Readiness, blockers, handoff, and priority queue."),
        ("Share summary", "summary", "Short no-claim summary for reviewers."),
    ]
    lines = [
        "<!doctype html>",
        '<html lang="en" data-theme="dark">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f'  <meta name="scroll-review-tooling-version" content="{_html(app_version)}">',
        f'  <meta name="scroll-review-tooling-protocol" content="{_html(OPERATOR_SERVER_PROTOCOL_VERSION)}">',
        f'  <meta name="scroll-review-action" content="{_html(action_nonce)}">',
        "  <title>Scroll Review Local App</title>",
        "  <style>",
        "    * { box-sizing:border-box; }",
        "    :root { color-scheme:light; --ink:#14202a; --muted:#607070; --line:#d8e0dc; --bg:#eef2f1; --panel:#ffffff; --soft:#f6faf8; --accent:#007b6d; --dark:#15212b; --ok:#087443; --warn:#b66d00; --bad:#b42318; }",
        "    :root[data-theme='dark'] { color-scheme:dark; --ink:#f5edff; --muted:#c8b8dc; --line:#503565; --bg:#170f22; --panel:#241531; --soft:#2d1b3d; --accent:#b98cff; --dark:#0f0a18; --ok:#7ee0a5; --warn:#f0b85a; --bad:#ff7f8e; }",
        "    html, body { max-width:100%; overflow-x:hidden; }",
        "    body { margin:0; font-family:Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--ink); }",
        "    a { color:inherit; text-decoration:none; }",
        "    h1, h2, h3, p, div, span, strong, a { overflow-wrap:anywhere; }",
        "    p { color:var(--muted); line-height:1.5; }",
        "    main { width:min(1360px, 100%); margin:0 auto; padding:18px; }",
        "    .app { display:grid; grid-template-columns:190px minmax(0, 1fr); gap:14px; min-width:0; align-items:start; }",
        "    .app > section { min-width:0; }",
        "    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 14px 34px rgba(32,48,42,.07); min-width:0; }",
        "    .rail { position:sticky; top:18px; padding:14px; min-height:calc(100vh - 36px); }",
        "    .brand { font-size:20px; font-weight:900; line-height:1.05; margin:6px 0 8px; }",
        "    .version-pill { display:inline-flex; margin:0 0 16px; color:var(--muted); font-size:12px; font-weight:850; }",
        "    .nav { display:grid; gap:6px; }",
        "    .nav a { padding:9px 10px; border-radius:8px; color:#31413d; font-weight:700; }",
        "    :root[data-theme='dark'] .nav a { color:#eadfff; }",
        "    .nav a.active { background:#e4f0ec; color:#005b51; }",
        "    :root[data-theme='dark'] .nav a.active { background:#3a2451; color:#ffffff; }",
        "    .rail-utility { margin-top:16px; padding-top:14px; border-top:1px solid var(--line); display:grid; gap:8px; color:var(--muted); font-size:12px; }",
        "    .rail-utility a { color:var(--muted); text-decoration:underline; text-underline-offset:3px; font-weight:800; }",
        "    .safe { border-left:4px solid var(--ok); background:#edf8f2; border-radius:8px; padding:10px 12px; color:var(--ink); }",
        "    :root[data-theme='dark'] .safe { background:#21142f; color:var(--ink); }",
        "    .appbar { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:9px 14px; margin-bottom:10px; }",
        "    .appbar strong { display:block; font-size:18px; }",
        "    .appbar span { color:var(--muted); }",
        "    .appbar-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }",
        "    .hero { padding:18px; display:grid; grid-template-columns:minmax(0, 1fr) 300px; gap:16px; align-items:start; border-top:3px solid var(--accent); }",
        "    .hero h1 { font-size:31px; line-height:1.08; margin:6px 0 8px; }",
        "    .pill { display:inline-flex; align-items:center; border-radius:999px; padding:6px 10px; background:#edf4f1; border:1px solid var(--line); font-size:12px; font-weight:800; }",
        "    :root[data-theme='dark'] .pill { background:#2d1b3d; color:var(--ink); }",
        "    .actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }",
        "    button, .button { display:inline-flex; align-items:center; justify-content:center; border:1px solid #cad7d2; border-radius:8px; min-height:42px; padding:10px 14px; font:inherit; font-weight:800; background:#fff; color:var(--ink); cursor:pointer; text-decoration:none; white-space:normal; }",
        "    :root[data-theme='dark'] button, :root[data-theme='dark'] .button { background:#2d1b3d; border-color:var(--line); color:var(--ink); }",
        "    button.primary, .button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }",
        "    :root[data-theme='dark'] button.primary, :root[data-theme='dark'] .button.primary { background:var(--accent); border-color:var(--accent); color:#170f22; }",
        "    button.dark, .button.dark { background:var(--dark); border-color:var(--dark); color:#fff; }",
        "    button:disabled { color:#7d8790; border-color:var(--line); cursor:wait; }",
        "    .snapshot { background:var(--soft); border:1px solid var(--line); border-radius:8px; padding:16px; }",
        "    .label { color:var(--muted); font-size:12px; text-transform:uppercase; font-weight:850; letter-spacing:0; }",
        "    .muted { color:var(--muted); }",
        "    .value { font-size:24px; font-weight:900; }",
        "    .ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }",
        "    .traffic { display:flex; gap:6px; margin:12px 0; }",
        "    .dot { width:11px; height:11px; border-radius:99px; }",
        "    .dot.ok { background:var(--ok); } .dot.warn { background:#d68a00; } .dot.bad { background:var(--bad); }",
        "    .metrics { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-top:12px; }",
        "    .metric { padding:16px; }",
        "    .meter { height:10px; border-radius:999px; background:#e3e8ea; overflow:hidden; margin-top:6px; }",
        "    :root[data-theme='dark'] .meter { background:#3e2a52; }",
        "    .meter i { display:block; height:100%; border-radius:999px; }",
        "    .m-ok { background:var(--ok); } .m-warn { background:#d68a00; } .m-bad { background:var(--bad); }",
        "    .data-journey { margin-bottom:10px; padding:9px 12px; display:grid; gap:8px; border-top:3px solid var(--accent); }",
        "    .journey-copy { display:flex; align-items:end; justify-content:space-between; gap:14px; }",
        "    .journey-copy p { max-width:52ch; font-size:13px; text-align:right; }",
        "    .data-journey h2 { margin:2px 0 0; font-size:18px; }",
        "    .data-journey p { margin:0; }",
        "    .journey-map { display:grid; grid-template-columns:repeat(6, minmax(0, 1fr)); gap:6px; }",
        "    .journey-node { display:flex; align-items:center; gap:7px; padding:8px; min-height:42px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }",
        "    .journey-node span { display:inline-flex; width:20px; height:20px; align-items:center; justify-content:center; border:1px solid var(--accent); border-radius:6px; font-size:12px; font-weight:900; flex:0 0 auto; }",
        "    .journey-node strong { display:block; font-size:13px; line-height:1.2; }",
        "    .journey-node p { display:none; margin:0; font-size:13px; }",
        "    .journey-boundary { border-left:4px solid var(--warn); background:var(--soft); border-radius:8px; padding:7px 10px; color:var(--muted); font-size:13px; }",
        "    .workspace { margin-top:12px; padding:16px; }",
        "    .flow-grid { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:10px; margin-top:12px; }",
        "    .flow-card { background:var(--soft); border:1px solid var(--line); border-radius:8px; padding:12px; }",
        "    .flow-card p { margin:6px 0 0; }",
        "    .flow-card strong { display:block; margin-bottom:6px; }",
        "    .selection-focus { display:grid; gap:10px; border:1px solid var(--line); border-radius:8px; background:var(--soft); padding:12px; }",
        "    .selection-focus h2 { margin:0; font-size:20px; }",
        "    .selection-focus p { margin:0; }",
        "    .source-status { display:flex; justify-content:space-between; gap:12px; border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:8px; background:var(--panel); padding:10px; }",
        "    .source-status.warn { border-left-color:var(--warn); }",
        "    .source-status span { color:var(--muted); font-size:13px; }",
        "    .selection-summary { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:8px; }",
        "    .selection-summary div { border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:9px; }",
        "    .selection-summary span { display:block; color:var(--muted); font-size:11px; font-weight:850; text-transform:uppercase; margin-bottom:4px; }",
        "    .selection-summary strong { display:block; font-size:13px; }",
        "    .selection-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); margin-top:0; }",
        "    .compact-selectors { grid-template-columns:repeat(2, minmax(0, 1fr)); }",
        "    .compact-selectors label:first-child { grid-column:1 / -1; }",
        "    .preset-grid { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:8px; }",
        "    .preset-card { border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:10px; }",
        "    .preset-card p { margin:6px 0; font-size:13px; }",
        "    .preset-card small { color:var(--muted); }",
        "    .next-step { border-left:4px solid var(--accent); background:var(--soft); border-radius:8px; padding:12px; margin-top:12px; }",
        "    .result-panel { margin-top:14px; border:1px solid var(--line); border-radius:8px; overflow:hidden; }",
        "    .result-row { display:grid; grid-template-columns:28px minmax(150px, 1fr) minmax(130px, .8fr) minmax(180px, 1fr); gap:10px; align-items:start; padding:12px; border-top:1px solid var(--line); background:var(--panel); }",
        "    .result-row:first-child { border-top:0; }",
        "    .state-dot { width:12px; height:12px; border-radius:99px; margin-top:4px; }",
        "    .state-dot.ok { background:var(--ok); } .state-dot.warn { background:#d68a00; } .state-dot.bad { background:var(--bad); }",
        "    .result-status { font-weight:900; }",
        "    .wizard-shell { display:grid; grid-template-columns:210px minmax(0, 1fr) 300px; gap:12px; padding:14px; margin-bottom:12px; border-top:3px solid var(--accent); }",
        "    .wizard-steps { display:grid; gap:8px; align-content:start; }",
        "    .wizard-step { display:grid; grid-template-columns:18px 1fr; gap:8px; padding:9px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }",
        "    .wizard-step.active { outline:2px solid var(--accent); background:var(--panel); }",
        "    .wizard-step small { display:block; color:var(--muted); margin-top:3px; }",
        "    .wizard-main { display:grid; gap:10px; align-content:start; padding:4px; }",
        "    .wizard-main h1 { font-size:28px; line-height:1.05; margin:0; }",
        "    .mode-card { border:1px solid var(--line); border-left:4px solid var(--accent); background:var(--soft); border-radius:8px; padding:10px; }",
        "    .mode-card strong { display:block; margin-bottom:4px; }",
        "    .mode-card p { margin:0; }",
        "    .wizard-control { display:grid; grid-template-columns:minmax(0, 1fr) auto auto; gap:10px; align-items:end; padding:10px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }",
        "    .wizard-control label { display:grid; gap:6px; color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }",
        "    .wizard-control input { width:100%; min-height:42px; border:1px solid var(--line); border-radius:8px; padding:9px 10px; background:var(--panel); color:var(--ink); font:inherit; }",
        "    .wizard-inspector { display:grid; gap:12px; align-content:start; background:var(--soft); border:1px solid var(--line); border-radius:8px; padding:12px; }",
        "    .wizard-inspector ul { margin:0; padding-left:0; }",
        "    .wizard-inspector li { list-style:none; margin-top:5px; }",
        "    .wizard-inspector code { display:block; max-width:100%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12px; }",
        "    .output-link { display:block; max-width:100%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-family:Consolas, monospace; font-size:12px; color:var(--ink); text-decoration:underline; text-underline-offset:2px; }",
        "    .queue { padding:0; overflow:hidden; margin-top:16px; }",
        "    .queue-row { display:grid; grid-template-columns:64px minmax(260px, 1fr) 190px 96px; gap:12px; align-items:center; padding:15px 16px; border-bottom:1px solid #e0e7e3; }",
        "    :root[data-theme='dark'] .queue-row { border-bottom-color:var(--line); }",
        "    .queue-row:last-child { border-bottom:0; }",
        "    .queue-row.head { background:#edf2f2; color:var(--muted); font-size:12px; text-transform:uppercase; font-weight:900; }",
        "    :root[data-theme='dark'] .queue-row.head { background:#2d1b3d; }",
        "    .rank { font-size:20px; font-weight:900; }",
        "    .work { display:grid; grid-template-columns:1fr; gap:16px; padding:0 16px 16px; }",
        "    .kanban { padding:14px; display:grid; grid-template-columns:repeat(3, minmax(180px, 1fr)); gap:10px; }",
        "    .lane { background:var(--soft); border:1px solid var(--line); border-radius:8px; padding:10px; }",
        "    .ticket { background:#fff; border:1px solid #dae5e0; border-radius:8px; padding:11px; margin-top:10px; }",
        "    :root[data-theme='dark'] .ticket { background:#241531; border-color:var(--line); }",
        "    .reports { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:12px; margin-top:16px; }",
        "    .report-card { padding:14px; }",
        "    .info-panel { margin-top:16px; padding:18px; }",
        "    .info-panel[hidden] { display:none; }",
        "    .intro-brief { margin-top:12px; padding:0; }",
        "    .intro-brief > summary { cursor:pointer; padding:14px 16px; font-weight:900; }",
        "    .intro-brief > summary span { display:block; margin-top:4px; color:var(--muted); font-size:13px; font-weight:500; }",
        "    .intro-body { padding:0 16px 16px; }",
        "    .info-grid { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; }",
        "    .info-box { background:var(--soft); border:1px solid var(--line); border-radius:8px; padding:12px; }",
        "    .advanced-panel { margin-top:12px; padding:0; }",
        "    .advanced-panel > summary { cursor:pointer; padding:14px 16px; font-weight:900; color:var(--ink); }",
        "    .advanced-panel > summary span { display:block; margin-top:4px; color:var(--muted); font-size:13px; font-weight:500; }",
        "    .advanced-body { display:grid; gap:12px; padding:0 16px 16px; }",
        "    .source-wizard { margin-top:12px; padding:16px; }",
        "    .source-grid { display:grid; grid-template-columns:1.2fr .8fr; gap:14px; align-items:start; }",
        "    .wizard-form { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; }",
        "    .wizard-form label { display:grid; gap:6px; color:var(--muted); font-size:12px; font-weight:850; text-transform:uppercase; }",
        "    .wizard-form input, .wizard-form select { width:100%; min-height:40px; border:1px solid var(--line); border-radius:8px; padding:9px 10px; background:var(--panel); color:var(--ink); font:inherit; }",
        "    .wizard-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }",
        "    .wizard-note { border-left:4px solid var(--warn); background:var(--soft); border-radius:8px; padding:12px; }",
        "    pre { white-space:pre-wrap; overflow:auto; max-height:260px; background:#0f1720; color:#d8e2ec; border-radius:8px; padding:12px; margin-top:16px; }",
        "    code { font-family:Consolas, monospace; }",
        "    @media (max-width:980px) { .app, .hero, .source-grid, .wizard-shell, .journey-map { grid-template-columns:1fr; } .rail { position:static; min-height:auto; } .metrics, .kanban, .reports, .info-grid, .wizard-form, .flow-grid, .result-row, .wizard-control, .preset-grid, .selection-summary, .compact-selectors { grid-template-columns:1fr; } .journey-node { min-height:auto; } .appbar { align-items:flex-start; flex-direction:column; } .result-row .state-dot { margin-top:0; } .queue-row { grid-template-columns:48px 1fr; } .queue-row.head { display:none; } .queue-row .meter, .queue-row .decision { grid-column:2; } .queue-row .decision { white-space:nowrap; } }",
        "    @media (max-width:620px) { main { width:100%; max-width:100%; margin:0; padding:8px; overflow:hidden; } .app { display:block; width:100%; max-width:100%; overflow:hidden; } .panel, .rail, .hero, .workspace, .source-wizard, .appbar, .wizard-shell, .data-journey { width:100%; max-width:100%; overflow:hidden; } .panel { margin-bottom:12px; } .rail { padding:14px; min-height:auto; } .brand { font-size:21px; } .nav { grid-template-columns:repeat(2, minmax(0, 1fr)); gap:6px; } .nav a { padding:7px 8px; font-size:13px; } .safe { display:none; } .appbar strong { display:block; max-width:100%; white-space:normal; overflow-wrap:anywhere; } .appbar > div:first-child span { display:none; } .wizard-main { order:1; } .wizard-steps { order:2; } .wizard-inspector { order:3; } .hero p, .snapshot p, .flow-card, .wizard-note, .wizard-main p, .wizard-inspector, .journey-node, .journey-boundary, .selection-focus { max-width:100%; overflow-wrap:anywhere; word-break:break-word; } .data-journey h2 { max-width:100%; white-space:normal; overflow-wrap:anywhere; font-size:23px; } .data-journey p { max-width:min(32ch, 100%); word-break:break-word; } .appbar-actions { display:grid; grid-template-columns:1fr; gap:8px; width:100%; max-width:100%; } .appbar-actions .pill { display:none; } .hero { padding:16px; } .hero h1, .wizard-main h1 { max-width:100%; overflow-wrap:anywhere; font-size:25px; line-height:1.08; } .actions { display:grid; } .button, button { width:100%; min-width:0; } }",
        "  </style>",
        "</head>",
        "<body>",
        "<main class=\"app\">",
        '  <aside class="panel rail" aria-label="Operator navigation">',
        "    <div class=\"brand\">Scroll Review<br>Operator Studio</div>",
        '    <nav class="nav">',
        '      <a class="active" href="#wizard">Start</a>',
        '      <a href="#home">Help</a>',
        '      <a href="#review">Reports</a>',
        '      <a href="#safety">Safety</a>',
        "    </nav>",
        '    <p id="safety" class="safe" style="margin-top:18px;font-size:13px"><strong>Local only.</strong><br>127.0.0.1 only. No upload, OCR, inference, title reading, or claims.</p>',
        '    <div class="rail-utility" aria-label="Utility links">',
        f'      <span data-version-from-meta>Version v{_html(app_version)}</span>',
        f'      <a href="{GITHUB_REPO_URL}" target="_blank" rel="noreferrer">Source code</a>',
        "    </div>",
        "  </aside>",
        "  <section>",
        '    <section class="panel appbar" aria-label="Operator app bar">',
        '      <div><strong>Operator cockpit</strong><span>Follow the highlighted step. Supporting views are below.</span></div>',
        f'      <div class="appbar-actions"><button type="button" data-toggle-info>Info</button><button type="button" data-toggle-theme aria-label="Toggle dark theme">&#9680; Theme</button></div>',
        "    </section>",
        _render_data_journey(),
        '    <section id="wizard" class="panel wizard-shell" aria-label="Functional operator wizard">',
        '      <div class="wizard-steps" aria-label="Wizard step list">',
        _render_wizard_steps(wizard_steps, active_step),
        "      </div>",
        '      <div class="wizard-main">',
        f'        <span class="pill">{_html(wizard.get("mode_label") or "First run")}</span>',
        '        <div class="label">Active step</div>',
        f'        <h1>{_html(wizard.get("active_label") or active_row.get("label") or "Setup")}</h1>',
        f'        <p>{_html(wizard.get("active_description") or active_row.get("description") or "Run the next safe local step.")}</p>',
        '        <div class="wizard-control">',
        f'          <label>Workspace folder<input id="workspace-input" value="{_html(workspace_input_value)}" placeholder="Choose a local folder outside this repo"></label>' if is_workspace_step else f'<input id="workspace-input" type="hidden" value="{_html(workspace_input_value)}">',
        f'          <button class="primary" type="button" data-primary-next data-source-action="check-workspace" data-use-suggested-workspace data-workspace="{_html(suggested_workspace)}">Use suggested workspace and check</button>' if is_workspace_step else "",
        "" if is_workspace_step else f"          {_render_next_action(wizard)}",
        "        </div>",
        _render_selection_focus(catalog_sources, active_step, selected_data),
        f"        {_render_mode_card(wizard)}",
        '        <div class="next-step"><strong>What happens next?</strong><p>The app runs only the highlighted step, writes a JSON or Markdown summary, and refreshes the status. Green means ready, yellow means review needed, red means blocked.</p></div>',
        "      </div>",
        '      <aside class="wizard-inspector" aria-label="Wizard inspector">',
        '        <div><div class="label">What happens</div>',
        f'        <strong class="{_html(active_row.get("level") or "warn")}">{_html(active_row.get("decision_label") or active_row.get("decision") or "not run")}</strong></div>',
        '        <div><div class="label">Why this step</div>',
        f'        <p>{_html(active_row.get("help") or "Run this step to continue.")}</p></div>',
        '        <div><div class="label">Blockers</div>',
        f'        <p>{_html(", ".join(str(item) for item in wizard.get("blockers", [])) or "none")}</p></div>',
        '        <div><div class="label">Output files</div><ul>',
        _render_wizard_outputs([output for output in wizard.get("outputs", [])]),
        '        </ul></div>',
        "      </aside>",
        "    </section>",
        '    <details id="home" class="panel intro-brief">',
        '      <summary>What is this tool?<span>Short answer: a local review-readiness wizard, not a reader. Open this when you need the beginner explanation.</span></summary>',
        '      <div class="intro-body">',
        '        <span class="pill">Runs locally - no upload</span>',
        "        <h2>Local review wizard, not a reader.</h2>",
        "        <p>Use the wizard above to move from setup to a no-claim review summary. Reports appear after the guided run. The app helps decide whether a small public-data path is organized enough for review; it does not read scroll text, infer letters, or make claims.</p>",
        '        <div class="actions"><a class="button" href="/report/dashboard" target="_blank" rel="noreferrer">Open review reports</a></div>',
        "      </div>",
        "    </details>",
        '    <section id="info-panel" class="panel info-panel" hidden>',
        "      <div class=\"label\">What this is</div>",
        "      <h2 style=\"margin:6px 0 10px\">A local readiness desk, not a reader.</h2>",
        "      <div class=\"info-grid\">",
        "        <div class=\"info-box\"><strong>What it is for</strong><p>It helps a normal local operator decide whether a small public-data path is ready for review, blocked, or missing safety checks.</p></div>",
        "        <div class=\"info-box\"><strong>How it works</strong><p>Choose a workspace, load a small public chunk, create a no-claim summary, then open the review reports. Raw chunk files stay in your workspace; generated summaries stay under demo/out.</p></div>",
        "        <div class=\"info-box\"><strong>What it will not do</strong><p>It does not upload data, inspect raw evidence, run OCR, run inference, read titles, or approve public claims.</p></div>",
        "      </div>",
        "    </section>",
        f'    <section class="metrics" aria-label="Readiness summary"{" hidden" if is_first_run else ""}>',
        '      <div class="panel metric"><div class="label">Readiness</div>',
        f'        <div class="value {status_level}">{readiness}%</div>{_render_meter(readiness, status_level)}</div>',
        '      <div class="panel metric"><div class="label">Blockers</div>',
        f'        <div class="value {"ok" if blocker_count == 0 else "warn"}">{blocker_count}</div>{_render_meter(100 if blocker_count == 0 else 42, "ok" if blocker_count == 0 else "warn")}</div>',
        '      <div class="panel metric"><div class="label">Release safety</div>',
        f'        <div class="value ok">{_html(claim_status)}</div>{_render_meter(safety_width, "ok")}</div>',
        "    </section>",
        '    <details class="panel advanced-panel">',
        '      <summary>Advanced step details and manual controls<span>Most users can stay in the wizard. Open this when you need the step log, individual chunk buttons, or debugging output.</span></summary>',
        '      <div class="advanced-body">',
        '    <section id="workspace" class="panel workspace" aria-label="Investigation workspace">',
        '      <div class="source-grid">',
        "        <div>",
        '          <div class="label">Investigation workspace</div>',
        "          <h2 style=\"margin:6px 0 10px\">What should I do next?</h2>",
        "          <p>Use this screen like an operations desk: pick a local workspace, fetch only a small public chunk, then let the app turn the result into a review-ready summary. The goal is not to read text here; the goal is to know whether the material is controlled enough for the next review step.</p>",
        '          <div class="flow-grid">',
        '            <div class="flow-card"><strong>Workspace</strong><span>Where local chunk files and markers live.</span></div>',
        '            <div class="flow-card"><strong>Explore</strong><span>Public source, scan label, and tiny/small preset.</span></div>',
        '            <div class="flow-card"><strong>Triage</strong><span>Readiness, blockers, queue, and Kanban progress.</span></div>',
        '            <div class="flow-card"><strong>Review package</strong><span>Dashboard, summary, and no-claim handoff files.</span></div>',
        "          </div>",
        f'          <div class="next-step"><strong>Recommended next action</strong><p>{_html(status.get("operator_next_step") or "Follow the highlighted wizard step.")}</p></div>',
        '          <div class="result-panel" aria-label="Data step results">',
        '            <div style="padding:12px"><div class="label">Data step results</div><strong>What happened, what is next, and where the output is.</strong></div>',
        _render_flow_rows(flow_steps),
        "          </div>",
        "        </div>",
        '        <div class="snapshot">',
        '          <div class="label">Local data boundary</div>',
        "          <p>Raw chunks stay in your chosen workspace folder. This repo keeps only generated JSON and HTML summaries under ignored output folders.</p>",
        "          <p>Public scan flow is allowed; OCR, transcription, letter inference, title reading, and public claims are outside this app.</p>",
        "        </div>",
        "      </div>",
        "    </section>",
        '    <section id="explore" class="panel source-wizard" aria-label="Load public scan chunk">',
        '      <div class="source-grid">',
        "        <div>",
        '          <div class="label">Load public scan chunk</div>',
        "          <h2 style=\"margin:6px 0 10px\">Fetch a small public chunk into a local workspace.</h2>",
        "          <p>This advanced data run checks a public catalog, suggests metadata-safe starting points, verifies your chosen local folder, creates a small chunk plan, fetches only a limited demo/public chunk, and writes no-claim readiness summaries.</p>",
        '          <p class="wizard-note">It does not download full volumes, use private credentials, inspect raw evidence for text, run OCR, train models, infer letters, submit claims, or store raw chunks in this repo.</p>',
        '          <div class="flow-grid" aria-label="Public source catalog choices">',
        _render_catalog_cards(catalog_sources),
        "          </div>",
        '          <div class="wizard-form">',
        f'            <label>Workspace folder<input id="workspace-input-secondary" value="{_html(workspace_input_value)}" placeholder="Use the workspace field in the wizard above"></label>',
        f'            <label>Source<select id="source-input-advanced">{_render_source_options(catalog_sources, str(selected_data.get("source") or "public-demo"))}</select></label>',
        f'            <label>Scan<select id="scan-input-advanced">{_render_scan_options(catalog_sources, str(selected_data.get("scan") or "synthetic-public-scroll"))}</select></label>',
        f'            <label>Preset<select id="preset-input-advanced">{_render_preset_options(catalog_sources, str(selected_data.get("preset") or "tiny-preview"))}</select></label>',
        "          </div>",
        '          <div class="wizard-actions">',
        '            <button class="primary" type="button" data-source-action="guided-chunk-flow">Run all data steps</button>',
        '            <button type="button" data-source-action="source-catalog">Check public catalog</button>',
        '            <button type="button" data-source-action="check-workspace">Check workspace</button>',
        '            <button type="button" data-source-action="plan-chunk">Plan chunk</button>',
        '            <button type="button" data-source-action="fetch-chunk">Fetch chunk</button>',
        '            <button type="button" data-source-action="scan-readiness">Create readiness summary</button>',
        "          </div>",
        '          <div id="last-action-result" class="next-step"><strong>Result</strong><p>Run a data step to see the current result here. Green means ready, yellow means still waiting, red means blocked.</p></div>',
        "        </div>",
        '        <div class="snapshot">',
        '          <div class="label">Data workflow status</div>',
        f'          <p>Catalog: <strong>{_html(status.get("source_catalog_decision") or "not checked")}</strong></p>',
        f'          <p>Workspace: <strong>{_html(status.get("workspace_decision") or "not checked")}</strong></p>',
        f'          <p>Chunk: <strong>{_html(status.get("chunk_fetch_decision") or status.get("chunk_plan_decision") or "not planned")}</strong></p>',
        f'          <p>Readiness: <strong>{_html(status.get("scan_readiness_decision") or "not generated")}</strong></p>',
        "        </div>",
        "      </div>",
        "    </section>",
        "      </div>",
        "    </details>",
        '    <details id="operator-board" class="panel advanced-panel">',
        '      <summary>Operator board (optional)<span>Queue and Kanban are useful after a run, but they are not the main starting point.</span></summary>',
        '    <section class="work">',
        '      <section id="triage" class="panel queue" aria-label="Priority queue">',
        '        <div class="queue-row head"><div>Rank</div><div>Path</div><div>Readiness</div><div>Decision</div></div>',
    ]
    for row in queue_rows:
        lines.append(
            f'        <div class="queue-row"><div class="rank">{_html(row.get("rank"))}</div><div><strong>{_html(row.get("label"))}</strong><div class="muted">{_html(row.get("detail"))}</div></div>{_render_meter(int(row.get("meter") or 0), str(row.get("level") or "warn"))}<strong class="decision {_html(row.get("level"))}">{_html(row.get("decision"))}</strong></div>'
        )
    lines.extend(
        [
            "      </section>",
            '      <section id="kanban" class="panel kanban" aria-label="Kanban readiness board">',
        ]
    )
    for lane, items in lanes.items():
        lines.append(f'        <div class="lane"><div class="label">{_html(lane)}</div>')
        if items:
            for item in items:
                lines.append(
                    f'          <div class="ticket"><strong>{_html(item.get("label"))}</strong><p>{_html(item.get("detail"))}</p></div>'
                )
        else:
            lines.append('          <div class="ticket"><strong>None</strong><p>No current item in this lane.</p></div>')
        lines.append("        </div>")
    lines.extend(
        [
            "      </section>",
            "    </section>",
            "    </details>",
            f'    <section id="review" class="reports" aria-label="Generated reports"{" hidden" if is_first_run else ""}>',
            '      <div class="panel report-card"><div class="value">Build reports</div><p>Runs the local demo/report builder after setup.</p><button type="button" data-action="run-operator">Build demo reports</button></div>',
        ]
    )
    for label, key, detail in report_cards:
        lines.append(
            f'      <div class="panel report-card"><div class="value">{_html(label)}</div><p>{_html(detail)}</p><a class="button" href="/report/{_html(key)}" target="_blank" rel="noreferrer">Open</a></div>'
        )
    lines.extend(
        [
            "    </section>",
            '    <details id="diagnostics" class="panel report-card" style="margin-top:16px">',
            '      <summary><strong>Diagnostics log</strong><span class="muted"> Raw local action output for debugging.</span></summary>',
            '      <pre id="log">Ready.</pre>',
            "    </details>",
            "  <script>",
            "    async function runAction(action) {",
            "      const log = document.getElementById('log');",
            "      const nonce = document.querySelector('meta[name=\"scroll-review-action\"]')?.content || '';",
            "      const headers = nonce ? { 'X-Scroll-Review-Action': nonce } : {};",
            "      const buttons = Array.from(document.querySelectorAll('button'));",
            "      buttons.forEach((button) => button.disabled = true);",
            "      log.textContent = 'Running ' + action + '...';",
            "      try {",
            "        const response = await fetch('/action/' + action, { method: 'POST', headers });",
            "        const data = await response.json();",
            "        log.textContent = JSON.stringify(data, null, 2);",
            "        if (data.ok) window.location.reload();",
            "      } catch (error) {",
            "        log.textContent = String(error);",
            "      } finally {",
            "        buttons.forEach((button) => button.disabled = false);",
            "      }",
            "    }",
            "    function applySuggestedWorkspace(button) {",
            "      if (!button || !button.hasAttribute('data-use-suggested-workspace')) return;",
            "      const input = document.getElementById('workspace-input');",
            "      const secondary = document.getElementById('workspace-input-secondary');",
            "      if (input) input.value = button.getAttribute('data-workspace') || '';",
            "      if (secondary) secondary.value = button.getAttribute('data-workspace') || '';",
            "    }",
            "    function formatBytes(value) {",
            "      const count = Number(value || 0);",
            "      if (!Number.isFinite(count) || count <= 0) return 'unknown size';",
            "      if (count >= 1024 * 1024) return (count / (1024 * 1024)).toFixed(1) + ' MB';",
            "      if (count >= 1024) return Math.floor(count / 1024) + ' KB';",
            "      return String(count) + ' bytes';",
            "    }",
            "    function selectedOption(select) {",
            "      if (!select || select.selectedIndex < 0) return null;",
            "      return select.options[select.selectedIndex];",
            "    }",
            "    function updateSelectionPreview() {",
            "      const source = selectedOption(document.getElementById('source-input')) || selectedOption(document.getElementById('source-input-advanced'));",
            "      const scan = selectedOption(document.getElementById('scan-input')) || selectedOption(document.getElementById('scan-input-advanced'));",
            "      const preset = selectedOption(document.getElementById('preset-input')) || selectedOption(document.getElementById('preset-input-advanced'));",
            "      const setText = (id, value) => { const node = document.getElementById(id); if (node) node.textContent = String(value || 'none'); };",
            "      if (source) {",
            "        setText('selection-source-summary', source.dataset.label || source.textContent);",
            "        setText('selection-why-summary', source.dataset.why || 'Public source selected from the catalog.');",
            "        const sourceStatus = document.getElementById('selection-source-status');",
            "        if (sourceStatus) {",
            "          sourceStatus.classList.toggle('warn', source.dataset.adapterAvailable !== 'true');",
            "          sourceStatus.classList.toggle('ok', source.dataset.adapterAvailable === 'true');",
            "          const statusStrong = sourceStatus.querySelector('strong');",
            "          const statusSpan = sourceStatus.querySelector('span');",
            "          if (statusStrong) statusStrong.textContent = source.dataset.status || (source.dataset.adapterAvailable === 'true' ? 'Ready now' : 'Setup needed');",
            "          if (statusSpan) statusSpan.textContent = source.dataset.setupHint || '';",
            "        }",
            "      }",
            "      if (scan) setText('selection-scan-summary', scan.value || scan.textContent);",
            "      if (preset) {",
            "        setText('selection-preset-summary', preset.dataset.label || preset.textContent);",
            "        setText('selection-size-summary', formatBytes(preset.dataset.estimatedBytes));",
            "        setText('selection-what-summary', preset.dataset.what || preset.dataset.goal || 'A bounded public chunk.');",
            "      }",
            "    }",
            "    async function runSourceAction(action, trigger) {",
            "      const log = document.getElementById('log');",
            "      applySuggestedWorkspace(trigger);",
            "      const payload = {",
            "        workspace: document.getElementById('workspace-input')?.value || document.getElementById('workspace-input-secondary')?.value || '',",
            "        source: document.getElementById('source-input')?.value || document.getElementById('source-input-advanced')?.value || 'public-demo',",
            "        scan: document.getElementById('scan-input')?.value || document.getElementById('scan-input-advanced')?.value || 'synthetic-public-scroll',",
            "        preset: document.getElementById('preset-input')?.value || document.getElementById('preset-input-advanced')?.value || 'tiny-preview'",
            "      };",
            "      const buttons = Array.from(document.querySelectorAll('button'));",
            "      buttons.forEach((button) => button.disabled = true);",
            "      log.textContent = 'Running data step ' + action + '...';",
            "      try {",
            "        const nonce = document.querySelector('meta[name=\"scroll-review-action\"]')?.content || '';",
            "        const headers = { 'Content-Type': 'application/json' };",
            "        if (nonce) headers['X-Scroll-Review-Action'] = nonce;",
            "        const response = await fetch('/action/' + action, { method: 'POST', headers, body: JSON.stringify(payload) });",
            "        const data = await response.json();",
            "        log.textContent = JSON.stringify(data, null, 2);",
            "        const resultBox = document.getElementById('last-action-result');",
            "        if (resultBox) {",
            "          const decision = data.decision || data.error || (data.payload && data.payload.decision) || 'check diagnostics';",
            "          const summary = data.operator_result_summary || '';",
            "          const nextStep = data.next_step || 'Check the data step results and diagnostics below.';",
            "          resultBox.textContent = '';",
            "          const strong = document.createElement('strong');",
            "          strong.textContent = 'Result: ' + String(decision);",
            "          const para = document.createElement('p');",
            "          para.textContent = (summary ? String(summary) + ' ' : '') + String(nextStep);",
            "          resultBox.append(strong, para);",
            "          if (Array.isArray(data.generated_outputs) && data.generated_outputs.length) {",
            "            const list = document.createElement('ul');",
            "            data.generated_outputs.slice(0, 6).forEach((item) => {",
            "              const li = document.createElement('li');",
            "              li.textContent = String(item);",
            "              list.append(li);",
            "            });",
            "            resultBox.append(list);",
            "          }",
            "        }",
            "        if (data.ok) window.location.reload();",
            "      } catch (error) {",
            "        log.textContent = String(error);",
            "      } finally {",
            "        buttons.forEach((button) => button.disabled = false);",
            "      }",
            "    }",
            "    document.querySelectorAll('button[data-action]').forEach((button) => {",
            "      button.addEventListener('click', () => runAction(button.getAttribute('data-action')));",
            "    });",
            "    document.querySelectorAll('button[data-source-action]').forEach((button) => {",
            "      button.addEventListener('click', () => runSourceAction(button.getAttribute('data-source-action'), button));",
            "    });",
            "    document.querySelectorAll('#source-input, #scan-input, #preset-input, #source-input-advanced, #scan-input-advanced, #preset-input-advanced').forEach((input) => {",
            "      input.addEventListener('change', updateSelectionPreview);",
            "    });",
            "    updateSelectionPreview();",
            "    const infoButton = document.querySelector('[data-toggle-info]');",
            "    const infoPanel = document.getElementById('info-panel');",
            "    if (infoButton && infoPanel) {",
            "      infoButton.addEventListener('click', () => { infoPanel.hidden = !infoPanel.hidden; });",
            "    }",
            "    const themeButton = document.querySelector('[data-toggle-theme]');",
            "    if (themeButton) {",
            "      themeButton.addEventListener('click', () => {",
            "        const root = document.documentElement;",
            "        root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';",
            "      });",
            "    }",
            "    document.querySelectorAll('[data-use-suggested-workspace]:not([data-source-action])').forEach((button) => {",
            "      button.addEventListener('click', () => {",
            "        applySuggestedWorkspace(button);",
            "        document.getElementById('workspace-input')?.focus();",
            "      });",
            "    });",
            "  </script>",
            "  </section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(lines) + "\n"
