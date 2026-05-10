from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.reports import inspect_outputs, prioritize_outputs
from scroll_review_tooling.review_workflow import (
    attention_delta,
    make_dossier,
    make_template,
    second_check,
    validate_handoff_manifest,
    validate_inbox,
    validate_pack,
    validate_preflight_manifest,
    validate_surface_review,
    write_json,
)


class ReviewWorkflowTests(unittest.TestCase):
    def build_bundle(self) -> dict:
        return {
            "bundle_id": "demo-bundle",
            "blind_sheets": [
                {"blind_id": "D01", "path": "demo/images/D01.jpg"},
                {"blind_id": "D02", "path": "demo/images/D02.jpg"},
            ],
        }

    def build_response(self, template: dict, verdict: str) -> dict:
        data = json.loads(json.dumps(template))
        data["reviewer_alias"] = "unit-test"
        data["expertise_domain"] = "workflow"
        for key in data["required_acks"]:
            data["required_acks"][key] = True
        for row in data["blind_review_scores"]:
            row["surface_quality_1_to_5"] = 3
            row["artifact_risk_1_to_5"] = 2
            row["structured_signal_confidence_0_to_5"] = 1
            row["textlike_confidence_0_to_5"] = 0
        data["post_reveal_assessment"]["reveal_opened_after_blind_scores_recorded"] = True
        data["post_reveal_assessment"]["final_verdict"] = verdict
        return data

    def test_ambiguous_response_validates_without_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(self.build_bundle())
            template_path = root / "template.json"
            inbox = root / "inbox"
            inbox.mkdir()
            write_json(template_path, template)
            write_json(inbox / "ambiguous.json", self.build_response(template, "ambiguous"))
            status = validate_inbox(template_path, inbox, root / "status.json")
            self.assertEqual(status["decision"], "independent-review-received-no-controlled-next-step")
            self.assertEqual(status["valid_response_count"], 1)
            self.assertEqual(status["supportive_response_count"], 0)

    def test_supportive_response_triggers_attention_not_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(self.build_bundle())
            template_path = root / "template.json"
            inbox = root / "inbox"
            inbox.mkdir()
            write_json(template_path, template)
            write_json(inbox / "supportive.json", self.build_response(template, "supports-controlled-next-step"))
            status = validate_inbox(template_path, inbox, root / "status.json")
            second = second_check(root / "status.json", root / "second.json")
            attention = attention_delta(root / "second.json", root / "state.json", root / "attention.json", update_baseline=False)
            self.assertEqual(status["supportive_response_count"], 1)
            self.assertEqual(second["decision"], "attention-independent-review-supports-controlled-next-step")
            self.assertFalse(second["public_claim_allowed"])
            self.assertEqual(attention["decision"], "attention-action-trigger")

    def test_missing_ack_invalidates_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(self.build_bundle())
            template_path = root / "template.json"
            inbox = root / "inbox"
            inbox.mkdir()
            response = self.build_response(template, "supports-controlled-next-step")
            response["required_acks"]["no_ocr_or_transcription_attempted"] = False
            write_json(template_path, template)
            write_json(inbox / "bad.json", response)
            status = validate_inbox(template_path, inbox, root / "status.json")
            self.assertEqual(status["decision"], "waiting-for-independent-review-response")
            self.assertEqual(status["valid_response_count"], 0)
            self.assertIn("missing-ack:no_ocr_or_transcription_attempted", status["rows"][0]["protocol_violations"])

    def test_duplicate_blind_id_invalidates_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(self.build_bundle())
            template_path = root / "template.json"
            inbox = root / "inbox"
            inbox.mkdir()
            response = self.build_response(template, "supports-controlled-next-step")
            response["blind_review_scores"][1]["blind_id"] = response["blind_review_scores"][0]["blind_id"]
            write_json(template_path, template)
            write_json(inbox / "duplicate.json", response)
            status = validate_inbox(template_path, inbox, root / "status.json")
            self.assertEqual(status["decision"], "waiting-for-independent-review-response")
            self.assertEqual(status["valid_response_count"], 0)
            self.assertIn("blind-id-set-mismatch", status["rows"][0]["protocol_violations"])
            self.assertIn("duplicate-blind-id:D01", status["rows"][0]["protocol_violations"])

    def build_pack_manifest(self) -> dict:
        return {
            "review_pack_protocol_version": "review-pack-v1",
            "review_type": "blind_signal",
            "scroll_id": "synthetic-scroll",
            "segment_id": "synthetic-segment",
            "coordinate_frame": "synthetic-local",
            "scale_um_per_px": 7.9,
            "source_control_split": {"source": ["D01"], "controls": ["D02"]},
            "training_overlap_statement": "Synthetic fixture only.",
            "render_command": "python scripts/run_demo.py",
            "claim_safety": "Synthetic only; no OCR, no transcription, no reading, no public claim.",
            "public_claim_allowed": False,
            "target_inference_allowed": False,
        }

    def test_validate_pack_requires_no_claim_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.build_pack_manifest()
            write_json(root / "pack.json", manifest)
            status = validate_pack(root / "pack.json", root / "pack_status.json", root / "pack_status.md")
            self.assertEqual(status["decision"], "review-pack-valid-no-claim")
            self.assertTrue(status["status_ok"])
            self.assertEqual(status["readiness_stage"], "manifest-valid")
            self.assertFalse(status["public_claim_allowed"])
            self.assertIn("Status OK", (root / "pack_status.md").read_text(encoding="utf-8"))
            manifest["public_claim_allowed"] = True
            write_json(root / "bad_pack.json", manifest)
            bad = validate_pack(root / "bad_pack.json", root / "bad_pack_status.json")
            self.assertEqual(bad["decision"], "review-pack-invalid")
            self.assertFalse(bad["status_ok"])
            self.assertIn("public-claim-not-allowed", bad["violations"])
            manifest = self.build_pack_manifest()
            manifest["source_control_split"] = {"source": "D01", "controls": ["D02"]}
            write_json(root / "bad_split.json", manifest)
            bad_split = validate_pack(root / "bad_split.json", root / "bad_split_status.json")
            self.assertIn("invalid-source-control-split", bad_split["violations"])
            self.assertIn("manifest-shape", bad_split["violation_categories"])
            self.assertEqual(bad_split["readiness_stage"], "blocked")
            self.assertIn("manifest-shape", bad_split["readiness_blockers"])
            manifest = self.build_pack_manifest()
            manifest["review_pack_protocol_version"] = "old"
            write_json(root / "bad_protocol.json", manifest)
            bad_protocol = validate_pack(root / "bad_protocol.json", root / "bad_protocol_status.json")
            self.assertIn("wrong-review-pack-protocol-version", bad_protocol["violations"])
            self.assertIn("protocol-version", bad_protocol["violation_categories"])
            self.assertIn("protocol-version", bad_protocol["readiness_blockers"])

    def test_surface_review_blocks_sheet_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.build_pack_manifest()
            manifest["review_type"] = "surface_vc3d"
            manifest["surface_review_protocol_version"] = "surface-vc3d-review-v1"
            manifest["surface_metrics"] = {
                "tifxyz_continuity": "present",
                "valid_coverage": 0.98,
                "neighbor_jump_p95": 1.1,
                "layer_triplet_stability": "stable",
            }
            manifest["surface_review_fields"] = {
                "sheet_switch_visible": True,
                "layer_continuity_blocker": False,
                "boundary_or_crop_bias": False,
                "compressed_region_risk": False,
                "needs_vc3d_surface_review": False,
            }
            write_json(root / "surface.json", manifest)
            status = validate_surface_review(root / "surface.json", root / "surface_status.json", root / "surface_status.md")
            self.assertEqual(status["decision"], "surface-review-blocked-no-claim")
            self.assertFalse(status["status_ok"])
            self.assertEqual(status["readiness_stage"], "blocked")
            self.assertIn("sheet_switch_visible", status["blockers"])
            self.assertIn("sheet_switch_visible", status["readiness_blockers"])
            self.assertIn("Blockers", (root / "surface_status.md").read_text(encoding="utf-8"))
            manifest["surface_review_protocol_version"] = "old"
            write_json(root / "bad_surface_protocol.json", manifest)
            bad_protocol = validate_surface_review(root / "bad_surface_protocol.json", root / "bad_surface_protocol_status.json")
            self.assertIn("wrong-surface-review-protocol-version", bad_protocol["violations"])
            self.assertIn("protocol-version", bad_protocol["violation_categories"])

    def test_preflight_manifest_never_executes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "preflight_protocol_version": "full-volume-preflight-v1",
                "volume_id": "synthetic-volume",
                "chunk_source": "synthetic fixture",
                "data_metadata": {"format": "synthetic-zarr"},
                "coordinate_frame": "synthetic-xyz",
                "model_hash": "sha256:model",
                "protocol_hash": "sha256:protocol",
                "control_panel": ["control-01"],
                "budget": {"disk_mib": 64},
                "output_path_policy": {"allowlist": ["demo/out"]},
                "stop_rules": ["preflight-only"],
                "claim_safety": "No inference, no OCR, no transcription, no reading, no public claim.",
                "execute": False,
            }
            write_json(root / "preflight.json", manifest)
            status = validate_preflight_manifest(root / "preflight.json", root / "preflight_status.json", root / "preflight_status.md")
            self.assertEqual(status["decision"], "full-volume-preflight-ready-no-claim")
            self.assertTrue(status["status_ok"])
            self.assertEqual(status["readiness_stage"], "preflight-ready")
            self.assertFalse(status["execute_allowed"])
            self.assertIn("Full-Volume Preflight Status", (root / "preflight_status.md").read_text(encoding="utf-8"))
            manifest["execute"] = True
            write_json(root / "bad_preflight.json", manifest)
            bad = validate_preflight_manifest(root / "bad_preflight.json", root / "bad_preflight_status.json")
            self.assertEqual(bad["decision"], "full-volume-preflight-invalid")
            self.assertFalse(bad["status_ok"])
            self.assertEqual(bad["readiness_stage"], "blocked")
            self.assertIn("execution-not-allowed-in-preflight", bad["violations"])
            self.assertIn("preflight-execution", bad["violation_categories"])
            self.assertIn("preflight-execution", bad["readiness_blockers"])
            manifest["execute"] = False
            manifest["preflight_protocol_version"] = "old"
            write_json(root / "bad_preflight_protocol.json", manifest)
            bad_protocol = validate_preflight_manifest(root / "bad_preflight_protocol.json", root / "bad_preflight_protocol_status.json")
            self.assertIn("wrong-preflight-protocol-version", bad_protocol["violations"])

    def test_dossier_stays_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "bundle.json", self.build_bundle())
            write_json(root / "review.json", {"decision": "independent-review-received-no-controlled-next-step", "valid_response_count": 1, "supportive_response_count": 0})
            write_json(root / "second.json", {"decision": "waiting-no-success-trigger"})
            write_json(root / "release.json", {"decision": "release-audit-pass"})
            dossier = make_dossier(root / "bundle.json", root / "review.json", root / "second.json", root / "release.json", root / "dossier.json", root / "dossier.md")
            self.assertEqual(dossier["decision"], "candidate-dossier-ready-no-claim")
            self.assertTrue(dossier["status_ok"])
            self.assertEqual(dossier["readiness_stage"], "review-ready")
            self.assertFalse(dossier["public_claim_allowed"])
            self.assertIn("No OCR", (root / "dossier.md").read_text(encoding="utf-8"))

    def test_inspect_outputs_summarizes_no_claim_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "ok.json", {"decision": "review-pack-valid-no-claim", "status_ok": True, "claim_status": "no-claim", "violations": []})
            write_json(root / "blocked.json", {"decision": "surface-review-blocked-no-claim", "status_ok": False, "claim_status": "no-claim", "violations": ["wrong-surface-review-protocol-version"], "violation_categories": ["protocol-version"], "blockers": ["sheet_switch_visible"]})
            summary = inspect_outputs([root / "ok.json", root / "blocked.json"], root / "summary.json", root / "summary.md")
            self.assertEqual(summary["decision"], "inspect-summary-ready-no-claim")
            self.assertEqual(summary["inspected_count"], 2)
            self.assertFalse(summary["public_claim_allowed"])
            self.assertIn("protocol-version", summary["violation_categories"])
            self.assertIn("sheet_switch_visible", summary["blockers"])
            self.assertEqual(summary["readiness_stage"], "summary-ready")
            markdown = (root / "summary.md").read_text(encoding="utf-8")
            self.assertIn("Inspect Summary", markdown)
            self.assertIn("protocol-version", markdown)
            gated = inspect_outputs([root / "ok.json", root / "blocked.json"], root / "gated_summary.json", require_status_ok=True)
            self.assertEqual(gated["decision"], "inspect-summary-blocked-no-claim")
            self.assertFalse(gated["status_ok"])
            self.assertEqual(gated["readiness_stage"], "blocked")
            self.assertEqual(gated["blocked_count"], 1)
            self.assertIn("protocol-version", gated["readiness_blockers"])
            self.assertIn("sheet_switch_visible", gated["readiness_blockers"])

    def test_inspect_outputs_detects_claim_safety_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsafe = {"decision": "unsafe", "status_ok": True, "claim_status": "claim"}
            unsafe["public_" + "claim_allowed"] = True
            unsafe["target_" + "inference_allowed"] = True
            write_json(root / "unsafe.json", unsafe)
            summary = inspect_outputs([root / "unsafe.json"], root / "summary.json")
            self.assertEqual(summary["decision"], "inspect-summary-risk-detected")
            self.assertFalse(summary["status_ok"])
            self.assertEqual(summary["readiness_stage"], "blocked")
            self.assertIn("claim-safety", summary["readiness_blockers"])
            self.assertEqual(summary["risk_count"], 1)

    def test_inspect_outputs_rolls_up_release_ready_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_manifest = self.build_pack_manifest()
            surface_manifest = self.build_pack_manifest()
            surface_manifest["review_type"] = "surface_vc3d"
            surface_manifest["surface_review_protocol_version"] = "surface-vc3d-review-v1"
            surface_manifest["surface_metrics"] = {
                "tifxyz_continuity": "present",
                "valid_coverage": 0.98,
                "neighbor_jump_p95": 1.1,
                "layer_triplet_stability": "stable",
            }
            surface_manifest["surface_review_fields"] = {
                "sheet_switch_visible": False,
                "layer_continuity_blocker": False,
                "boundary_or_crop_bias": False,
                "compressed_region_risk": False,
                "needs_vc3d_surface_review": False,
            }
            preflight_manifest = {
                "preflight_protocol_version": "full-volume-preflight-v1",
                "volume_id": "synthetic-volume",
                "chunk_source": "synthetic fixture",
                "data_metadata": {"format": "synthetic-zarr"},
                "coordinate_frame": "synthetic-xyz",
                "model_hash": "sha256:model",
                "protocol_hash": "sha256:protocol",
                "control_panel": ["control-01"],
                "budget": {"disk_mib": 64},
                "output_path_policy": {"allowlist": ["demo/out"]},
                "stop_rules": ["preflight-only"],
                "claim_safety": "No inference, no OCR, no transcription, no reading, no public claim.",
                "execute": False,
            }
            write_json(root / "pack.json", pack_manifest)
            write_json(root / "surface.json", surface_manifest)
            write_json(root / "preflight.json", preflight_manifest)
            pack = validate_pack(root / "pack.json", root / "pack_status.json")
            surface = validate_surface_review(root / "surface.json", root / "surface_status.json")
            preflight = validate_preflight_manifest(root / "preflight.json", root / "preflight_status.json")
            self.assertEqual(pack["readiness_stage"], "manifest-valid")
            self.assertEqual(surface["readiness_stage"], "surface-ready")
            self.assertEqual(preflight["readiness_stage"], "preflight-ready")

            write_json(root / "bundle.json", self.build_bundle())
            write_json(root / "review.json", {"decision": "independent-review-received-no-controlled-next-step", "valid_response_count": 1, "supportive_response_count": 0})
            write_json(root / "second.json", {"decision": "waiting-no-success-trigger"})
            write_json(root / "release.json", {"decision": "release-audit-pass"})
            dossier = make_dossier(root / "bundle.json", root / "review.json", root / "second.json", root / "release.json", root / "dossier.json")
            self.assertEqual(dossier["readiness_stage"], "review-ready")

            summary = inspect_outputs(
                [root / "pack_status.json", root / "surface_status.json", root / "preflight_status.json", root / "dossier.json"],
                root / "summary.json",
                require_status_ok=True,
            )
            self.assertEqual(summary["decision"], "release-ready-no-claim")
            self.assertTrue(summary["status_ok"])
            self.assertEqual(summary["readiness_stage"], "release-ready")
            self.assertEqual(summary["readiness_blockers"], [])

    def write_ready_sources(self, root: Path) -> list[str]:
        write_json(root / "pack_status.json", {"decision": "review-pack-valid-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "manifest-valid", "readiness_blockers": []})
        write_json(root / "surface_status.json", {"decision": "surface-review-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "surface-ready", "readiness_blockers": []})
        write_json(root / "preflight_status.json", {"decision": "full-volume-preflight-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "preflight-ready", "readiness_blockers": []})
        write_json(root / "dossier.json", {"decision": "candidate-dossier-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "review-ready", "readiness_blockers": []})
        return ["pack_status.json", "surface_status.json", "preflight_status.json", "dossier.json"]

    def build_handoff_manifest(self, source_files: list[str]) -> dict:
        return {
            "handoff_protocol_version": "review-to-reading-handoff-v1",
            "source_readiness_files": source_files,
            "next_private_step_type": "private-reading-review",
            "surface_risk_summary": {
                "surface_ready": True,
                "sheet_switch_risk": False,
                "compressed_region_risk": False,
            },
            "control_requirements": {
                "controls_present": True,
                "control_count": 1,
            },
            "reviewer_requirements": {
                "required_review_count": 1,
                "reviewer_summary": "Synthetic reviewer handoff.",
            },
            "claim_safety": "Synthetic handoff only; no OCR, no transcription, no reading, no public claim.",
        }

    def test_handoff_manifest_validates_ready_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.build_handoff_manifest(self.write_ready_sources(root))
            write_json(root / "handoff.json", manifest)
            status = validate_handoff_manifest(root / "handoff.json", root / "handoff_status.json", root / "handoff_status.md")
            self.assertEqual(status["decision"], "review-to-reading-handoff-ready-no-claim")
            self.assertTrue(status["status_ok"])
            self.assertEqual(status["readiness_stage"], "handoff-ready")
            self.assertEqual(status["next_private_step_type"], "private-reading-review")
            self.assertFalse(status["public_claim_allowed"])
            self.assertIn("Review-to-Reading Handoff Status", (root / "handoff_status.md").read_text(encoding="utf-8"))

    def test_handoff_blocks_missing_controls_and_surface_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_files = self.write_ready_sources(root)
            (root / "surface_status.json").unlink()
            write_json(root / "surface_status.json", {"decision": "surface-review-blocked-no-claim", "status_ok": False, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "blocked", "readiness_blockers": ["sheet-switch-risk"]})
            manifest = self.build_handoff_manifest(source_files)
            manifest["control_requirements"] = {"controls_present": False, "control_count": 0}
            manifest["surface_risk_summary"]["surface_ready"] = False
            manifest["surface_risk_summary"]["sheet_switch_risk"] = True
            write_json(root / "handoff.json", manifest)
            status = validate_handoff_manifest(root / "handoff.json", root / "handoff_status.json")
            self.assertEqual(status["decision"], "review-to-reading-handoff-blocked-no-claim")
            self.assertFalse(status["status_ok"])
            self.assertEqual(status["readiness_stage"], "blocked")
            self.assertIn("missing-controls", status["readiness_blockers"])
            self.assertIn("surface-readiness", status["readiness_blockers"])
            self.assertIn("sheet-switch-risk", status["readiness_blockers"])

    def test_handoff_blocks_claim_safety_and_private_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.build_handoff_manifest(self.write_ready_sources(root))
            manifest["claim_safety"] = "Synthetic handoff only."
            manifest["public_" + "claim_allowed"] = True
            manifest["private_path"] = "synthetic-private-placeholder"
            write_json(root / "handoff.json", manifest)
            status = validate_handoff_manifest(root / "handoff.json", root / "handoff_status.json")
            self.assertEqual(status["decision"], "review-to-reading-handoff-risk-detected")
            self.assertFalse(status["status_ok"])
            self.assertIn("claim-safety", status["readiness_blockers"])
            self.assertIn("forbidden-handoff-field:private_path", status["violations"])

    def test_prioritize_outputs_ranks_ready_handoff_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "blocked.json", {"decision": "review-to-reading-handoff-blocked-no-claim", "status_ok": False, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "blocked", "readiness_blockers": ["missing-controls"], "surface_ready": False, "controls_present": False})
            write_json(root / "ready.json", {"decision": "review-to-reading-handoff-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "handoff-ready", "readiness_blockers": [], "next_private_step_type": "vc3d-sheet-switch-review", "surface_ready": True, "controls_present": True})
            priority = prioritize_outputs([root / "blocked.json", root / "ready.json"], root / "priority.json", root / "priority.md")
            self.assertEqual(priority["decision"], "path-priority-ready-no-claim")
            self.assertTrue(priority["status_ok"])
            self.assertEqual(priority["readiness_stage"], "handoff-ready")
            self.assertTrue(priority["ranked_rows"][0]["path"].endswith("ready.json"))
            self.assertIn("missing-controls", priority["readiness_blockers"])

    def test_inspect_outputs_summarizes_handoff_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "handoff.json", {"decision": "review-to-reading-handoff-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "handoff-ready", "readiness_blockers": [], "next_private_step_type": "vc3d-sheet-switch-review"})
            summary = inspect_outputs([root / "handoff.json"], root / "summary.json", require_status_ok=True)
            self.assertEqual(summary["decision"], "handoff-ready-no-claim")
            self.assertTrue(summary["status_ok"])
            self.assertEqual(summary["readiness_stage"], "handoff-ready")

    def test_prioritize_outputs_blocks_unsafe_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsafe = {"decision": "unsafe", "status_ok": True, "claim_status": "claim", "readiness_stage": "handoff-ready", "readiness_blockers": []}
            unsafe["target_" + "inference_allowed"] = True
            write_json(root / "unsafe.json", unsafe)
            priority = prioritize_outputs([root / "unsafe.json"], root / "priority.json")
            self.assertEqual(priority["decision"], "path-priority-risk-detected")
            self.assertFalse(priority["status_ok"])
            self.assertIn("claim-safety", priority["readiness_blockers"])

    def test_demo_invalid_fixtures_exercise_expected_failures(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_protocol = validate_pack(repo / "demo" / "invalid" / "bad_review_pack_protocol.json", root / "bad_protocol.json")
            bad_split = validate_pack(repo / "demo" / "invalid" / "bad_review_pack_split.json", root / "bad_split.json")
            bad_claim = validate_pack(repo / "demo" / "invalid" / "bad_claim_safety.json", root / "bad_claim.json")
            bad_surface = validate_surface_review(repo / "demo" / "invalid" / "bad_surface_sheet_switch.json", root / "bad_surface.json")
            bad_preflight = validate_preflight_manifest(repo / "demo" / "invalid" / "bad_preflight_execute.json", root / "bad_preflight.json")
            bad_handoff_controls = validate_handoff_manifest(repo / "demo" / "invalid" / "bad_handoff_missing_controls.json", root / "bad_handoff_controls.json")
            bad_handoff_claim = validate_handoff_manifest(repo / "demo" / "invalid" / "bad_handoff_claim_safety.json", root / "bad_handoff_claim.json")
            self.assertIn("wrong-review-pack-protocol-version", bad_protocol["violations"])
            self.assertIn("invalid-source-control-split", bad_split["violations"])
            self.assertIn("missing-no-ocr", bad_claim["violations"])
            self.assertIn("sheet_switch_visible", bad_surface["blockers"])
            self.assertIn("execution-not-allowed-in-preflight", bad_preflight["violations"])
            self.assertIn("missing-controls", bad_handoff_controls["violations"])
            self.assertIn("claim-safety", bad_handoff_claim["readiness_blockers"])


if __name__ == "__main__":
    unittest.main()
