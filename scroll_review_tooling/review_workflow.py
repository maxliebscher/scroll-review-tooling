from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import load_json, sha256_text, write_json
from .data_sources import check_workspace, fetch_chunk, plan_chunk, scan_readiness, source_catalog
from .manifest_validation import validate_handoff_manifest, validate_pack, validate_preflight_manifest, validate_surface_review
from .reports import inspect_outputs, make_dossier, prioritize_outputs, render_dashboard
from .sessions import session_input_paths, session_output_path, validate_session_manifest

PROTOCOL_VERSION = "blind-review-v1"
VALID_FINAL_VERDICTS = {
    "supports-controlled-next-step",
    "ambiguous",
    "reject-artifact-risk",
    "insufficient-material",
}


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["response_file", "status", "reviewer_alias", "final_verdict", "protocol_violations", "claim_status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, dialect="excel-tab", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            if isinstance(flat.get("protocol_violations"), list):
                flat["protocol_violations"] = ";".join(flat["protocol_violations"])
            writer.writerow(flat)


def make_template(bundle: dict[str, Any]) -> dict[str, Any]:
    blind_sheets = bundle.get("blind_sheets", [])
    return {
        "review_protocol_version": PROTOCOL_VERSION,
        "reviewer_alias": "",
        "expertise_domain": "",
        "reviewed_bundle_id": bundle.get("bundle_id", ""),
        "review_date_utc": "",
        "required_acks": {
            "blind_review_completed_before_reveal": False,
            "no_ocr_or_transcription_attempted": False,
            "no_letter_title_or_reading_claim_made": False,
            "understands_this_is_internal_review_only": False,
        },
        "blind_review_scores": [
            {
                "blind_id": sheet["blind_id"],
                "review_file": sheet["path"],
                "surface_quality_1_to_5": None,
                "artifact_risk_1_to_5": None,
                "structured_signal_confidence_0_to_5": None,
                "textlike_confidence_0_to_5": None,
                "would_prioritize_for_method_context_before_reveal": False,
                "blind_notes_no_letters": "",
            }
            for sheet in blind_sheets
        ],
        "post_reveal_assessment": {
            "reveal_opened_after_blind_scores_recorded": False,
            "source_like_blind_ids_before_reveal": [],
            "source_tiles_remain_plausible_after_method_context": None,
            "control_tiles_explain_signal": None,
            "final_verdict": "ambiguous",
            "final_notes_no_letters": "",
        },
        "allowed_final_verdicts": sorted(VALID_FINAL_VERDICTS),
        "claim_safety": "Template only; no OCR, no reading, no claim.",
    }


def validate_response(path: Path, template: dict[str, Any]) -> dict[str, Any]:
    try:
        data = load_json(path)
    except Exception as exc:
        return {
            "response_file": str(path),
            "status": "invalid-review-response",
            "reviewer_alias": "",
            "final_verdict": "",
            "protocol_violations": [f"invalid-json:{type(exc).__name__}"],
            "claim_status": "no-claim",
        }
    violations: list[str] = []
    if data.get("review_protocol_version") != template.get("review_protocol_version"):
        violations.append("wrong-protocol-version")
    if data.get("reviewed_bundle_id") != template.get("reviewed_bundle_id"):
        violations.append("wrong-bundle-id")
    acks = data.get("required_acks", {})
    for key in template.get("required_acks", {}):
        if acks.get(key) is not True:
            violations.append(f"missing-ack:{key}")
    expected_ids = {r.get("blind_id") for r in template.get("blind_review_scores", [])}
    scored_rows = data.get("blind_review_scores", [])
    scored_id_list = [r.get("blind_id") for r in scored_rows]
    scored_ids = set(scored_id_list)
    if scored_ids != expected_ids:
        violations.append("blind-id-set-mismatch")
    if len(scored_id_list) != len(expected_ids):
        violations.append("blind-id-count-mismatch")
    duplicate_ids = sorted({blind_id for blind_id in scored_id_list if scored_id_list.count(blind_id) > 1})
    for blind_id in duplicate_ids:
        violations.append(f"duplicate-blind-id:{blind_id}")
    for row in scored_rows:
        for key, low, high in [
            ("surface_quality_1_to_5", 1, 5),
            ("artifact_risk_1_to_5", 1, 5),
            ("structured_signal_confidence_0_to_5", 0, 5),
            ("textlike_confidence_0_to_5", 0, 5),
        ]:
            value = row.get(key)
            if not isinstance(value, int) or value < low or value > high:
                violations.append(f"invalid-score:{row.get('blind_id')}:{key}")
    post = data.get("post_reveal_assessment", {})
    verdict = post.get("final_verdict", "")
    if verdict not in VALID_FINAL_VERDICTS:
        violations.append("invalid-final-verdict")
    if post.get("reveal_opened_after_blind_scores_recorded") is not True:
        violations.append("reveal-order-not-acknowledged")
    if violations:
        status = "invalid-review-response"
    elif verdict == "supports-controlled-next-step":
        status = "independent-review-supports-controlled-next-step-no-claim"
    elif verdict == "ambiguous":
        status = "independent-review-ambiguous-no-claim"
    elif verdict == "reject-artifact-risk":
        status = "independent-review-rejects-artifact-risk-no-claim"
    else:
        status = "independent-review-insufficient-material-no-claim"
    return {
        "response_file": str(path),
        "status": status,
        "reviewer_alias": data.get("reviewer_alias", ""),
        "final_verdict": verdict,
        "protocol_violations": violations,
        "claim_status": "no-claim",
    }


def validate_inbox(template_path: Path, inbox: Path, out_json: Path, out_tsv: Path | None = None) -> dict[str, Any]:
    template = load_json(template_path)
    rows = []
    for path in sorted(inbox.glob("*.json")):
        if path.resolve() == template_path.resolve():
            continue
        rows.append(validate_response(path, template))
    valid = [r for r in rows if r["status"] != "invalid-review-response"]
    supportive = [r for r in valid if r["status"] == "independent-review-supports-controlled-next-step-no-claim"]
    if supportive:
        decision = "independent-review-supports-controlled-next-step-no-claim"
    elif valid:
        decision = "independent-review-received-no-controlled-next-step"
    else:
        decision = "waiting-for-independent-review-response"
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "response_count": len(rows),
        "valid_response_count": len(valid),
        "supportive_response_count": len(supportive),
        "rows": rows,
        "claim_safety": "Reviewer validation only; no OCR, no reading, no claim.",
    }
    write_json(out_json, payload)
    if out_tsv:
        write_tsv(out_tsv, rows)
    return payload


def second_check(review_status_path: Path, out_json: Path) -> dict[str, Any]:
    review = load_json(review_status_path)
    supportive = int(review.get("supportive_response_count", 0) or 0) > 0
    if supportive:
        decision = "attention-independent-review-supports-controlled-next-step"
    else:
        decision = "waiting-no-success-trigger"
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "independent_review": {
            "decision": review.get("decision"),
            "valid_response_count": review.get("valid_response_count"),
            "supportive_response_count": review.get("supportive_response_count"),
        },
        "success": supportive,
        "public_claim_allowed": False,
        "claim_safety": "Second-check only; no OCR, no reading, no claim.",
    }
    write_json(out_json, payload)
    return payload


def attention_delta(second_check_path: Path, state_path: Path, out_json: Path, update_baseline: bool = False) -> dict[str, Any]:
    second = load_json(second_check_path)
    semantic = {
        "second_check_decision": second.get("decision"),
        "success": second.get("success"),
        "independent_review": second.get("independent_review"),
    }
    current_hash = sha256_text(semantic)
    previous = {}
    if state_path.exists():
        previous = load_json(state_path)
    previous_hash = previous.get("semantic_hash")
    items = []
    if second.get("decision") == "attention-independent-review-supports-controlled-next-step":
        items.append({"priority": "attention", "reason": "independent-review-supports-controlled-next-step"})
    if items:
        decision = "attention-action-trigger"
    elif previous_hash == current_hash:
        decision = "quiet-wait"
    elif previous_hash:
        decision = "attention-state-changed"
    else:
        decision = "baseline-created"
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "semantic_hash": current_hash,
        "previous_semantic_hash": previous_hash,
        "attention_items": items,
        "claim_safety": "Attention monitor only; no OCR, no reading, no claim.",
    }
    write_json(out_json, payload)
    if update_baseline or not state_path.exists():
        write_json(state_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_template = sub.add_parser("init-template")
    p_template.add_argument("--bundle", required=True)
    p_template.add_argument("--out", required=True)
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--template", required=True)
    p_validate.add_argument("--inbox", required=True)
    p_validate.add_argument("--out-json", required=True)
    p_validate.add_argument("--out-tsv")
    p_second = sub.add_parser("second-check")
    p_second.add_argument("--review-status", required=True)
    p_second.add_argument("--out-json", required=True)
    p_attention = sub.add_parser("attention")
    p_attention.add_argument("--second-check", required=True)
    p_attention.add_argument("--state", required=True)
    p_attention.add_argument("--out-json", required=True)
    p_attention.add_argument("--update-baseline", action="store_true")
    p_pack = sub.add_parser("validate-pack")
    p_pack.add_argument("--manifest", required=True)
    p_pack.add_argument("--out-json", required=True)
    p_pack.add_argument("--out-md")
    p_surface = sub.add_parser("surface-review")
    p_surface.add_argument("--manifest", required=True)
    p_surface.add_argument("--out-json", required=True)
    p_surface.add_argument("--out-md")
    p_preflight = sub.add_parser("preflight-manifest")
    p_preflight.add_argument("--manifest", required=True)
    p_preflight.add_argument("--out-json", required=True)
    p_preflight.add_argument("--out-md")
    p_handoff = sub.add_parser("handoff")
    p_handoff.add_argument("--manifest", required=True)
    p_handoff.add_argument("--out-json", required=True)
    p_handoff.add_argument("--out-md")
    p_dossier = sub.add_parser("dossier")
    p_dossier.add_argument("--bundle", required=True)
    p_dossier.add_argument("--review-status", required=True)
    p_dossier.add_argument("--second-check", required=True)
    p_dossier.add_argument("--release-audit", required=True)
    p_dossier.add_argument("--out-json", required=True)
    p_dossier.add_argument("--out-md")
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--input-json", nargs="+", required=True)
    p_inspect.add_argument("--out-json", required=True)
    p_inspect.add_argument("--out-md")
    p_inspect.add_argument("--require-status-ok", action="store_true")
    p_prioritize = sub.add_parser("prioritize")
    p_prioritize.add_argument("--input-json", nargs="+", required=True)
    p_prioritize.add_argument("--out-json", required=True)
    p_prioritize.add_argument("--out-md")
    p_dashboard = sub.add_parser("dashboard")
    p_dashboard.add_argument("--input-json", nargs="+")
    p_dashboard.add_argument("--out-html")
    p_dashboard.add_argument("--session")
    p_catalog = sub.add_parser("source-catalog")
    p_catalog.add_argument("--out-json", required=True)
    p_workspace = sub.add_parser("check-workspace")
    p_workspace.add_argument("--workspace", required=True)
    p_workspace.add_argument("--out-json", required=True)
    p_plan = sub.add_parser("plan-chunk")
    p_plan.add_argument("--source", required=True)
    p_plan.add_argument("--scan", required=True)
    p_plan.add_argument("--preset", default="tiny-preview")
    p_plan.add_argument("--workspace", required=True)
    p_plan.add_argument("--out-json", required=True)
    p_fetch = sub.add_parser("fetch-chunk")
    p_fetch.add_argument("--plan", required=True)
    p_fetch.add_argument("--out-json", required=True)
    p_scan = sub.add_parser("scan-readiness")
    p_scan.add_argument("--fetch-status", required=True)
    p_scan.add_argument("--out-json", required=True)
    p_scan.add_argument("--out-md")
    args = parser.parse_args()
    if args.cmd == "init-template":
        payload = make_template(load_json(Path(args.bundle)))
        write_json(Path(args.out), payload)
    elif args.cmd == "validate":
        payload = validate_inbox(Path(args.template), Path(args.inbox), Path(args.out_json), Path(args.out_tsv) if args.out_tsv else None)
        print(json.dumps(payload, indent=2))
    elif args.cmd == "second-check":
        print(json.dumps(second_check(Path(args.review_status), Path(args.out_json)), indent=2))
    elif args.cmd == "attention":
        print(json.dumps(attention_delta(Path(args.second_check), Path(args.state), Path(args.out_json), args.update_baseline), indent=2))
    elif args.cmd == "validate-pack":
        print(json.dumps(validate_pack(Path(args.manifest), Path(args.out_json), Path(args.out_md) if args.out_md else None), indent=2))
    elif args.cmd == "surface-review":
        print(json.dumps(validate_surface_review(Path(args.manifest), Path(args.out_json), Path(args.out_md) if args.out_md else None), indent=2))
    elif args.cmd == "preflight-manifest":
        print(json.dumps(validate_preflight_manifest(Path(args.manifest), Path(args.out_json), Path(args.out_md) if args.out_md else None), indent=2))
    elif args.cmd == "handoff":
        print(json.dumps(validate_handoff_manifest(Path(args.manifest), Path(args.out_json), Path(args.out_md) if args.out_md else None), indent=2))
    elif args.cmd == "dossier":
        print(json.dumps(make_dossier(Path(args.bundle), Path(args.review_status), Path(args.second_check), Path(args.release_audit), Path(args.out_json), Path(args.out_md) if args.out_md else None), indent=2))
    elif args.cmd == "inspect":
        payload = inspect_outputs(
            [Path(path) for path in args.input_json],
            Path(args.out_json),
            Path(args.out_md) if args.out_md else None,
            require_status_ok=args.require_status_ok,
        )
        print(json.dumps(payload, indent=2))
        if args.require_status_ok and not payload.get("status_ok"):
            sys.exit(1)
    elif args.cmd == "prioritize":
        payload = prioritize_outputs(
            [Path(path) for path in args.input_json],
            Path(args.out_json),
            Path(args.out_md) if args.out_md else None,
        )
        print(json.dumps(payload, indent=2))
    elif args.cmd == "dashboard":
        if args.session:
            session = validate_session_manifest(Path(args.session))
            if not session.get("status_ok"):
                print(json.dumps(session, indent=2))
                sys.exit(1)
            input_paths = session_input_paths(session)
            out_html = Path(args.out_html) if args.out_html else session_output_path(session)
            session_name = str(session.get("session_name") or "")
        else:
            if not args.input_json or not args.out_html:
                parser.error("dashboard requires --session or both --input-json and --out-html")
            input_paths = [Path(path) for path in args.input_json]
            out_html = Path(args.out_html)
            session_name = None
        payload = render_dashboard(
            input_paths,
            out_html,
            session_name=session_name,
        )
        print(json.dumps(payload, indent=2))
    elif args.cmd == "source-catalog":
        print(json.dumps(source_catalog(Path(args.out_json)), indent=2))
    elif args.cmd == "check-workspace":
        print(json.dumps(check_workspace(Path(args.workspace), Path.cwd(), Path(args.out_json)), indent=2))
    elif args.cmd == "plan-chunk":
        print(
            json.dumps(
                plan_chunk(
                    args.source,
                    args.scan,
                    args.preset,
                    Path(args.workspace),
                    Path.cwd(),
                    Path(args.out_json),
                ),
                indent=2,
            )
        )
    elif args.cmd == "fetch-chunk":
        print(json.dumps(fetch_chunk(Path(args.plan), Path(args.out_json), repo_root=Path.cwd()), indent=2))
    elif args.cmd == "scan-readiness":
        print(json.dumps(scan_readiness(Path(args.fetch_status), Path(args.out_json), Path(args.out_md) if args.out_md else None), indent=2))


if __name__ == "__main__":
    main()
