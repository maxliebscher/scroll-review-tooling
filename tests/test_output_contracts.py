from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.check_release import release_check_payload
from scroll_review_tooling.reports import inspect_outputs, make_dossier, prioritize_outputs
from scroll_review_tooling.review_workflow import (
    validate_handoff_manifest,
    validate_pack,
    validate_preflight_manifest,
    validate_surface_review,
    write_json,
)


def assert_no_claim_contract(test: unittest.TestCase, payload: dict, protocol_version: str) -> None:
    test.assertIn("created", payload)
    datetime.fromisoformat(payload["created"])
    test.assertIn("decision", payload)
    test.assertIn("status_ok", payload)
    test.assertEqual(payload["protocol_version"], protocol_version)
    test.assertIn("readiness_stage", payload)
    test.assertIn("readiness_blockers", payload)
    test.assertIsInstance(payload["readiness_blockers"], list)
    test.assertEqual(payload["claim_status"], "no-claim")
    test.assertFalse(payload["public_claim_allowed"])
    test.assertFalse(payload["target_inference_allowed"])
    test.assertIn("no OCR", payload["claim_safety"])
    test.assertIn("no transcription", payload["claim_safety"])
    test.assertIn("no reading", payload["claim_safety"])


class OutputContractTests(unittest.TestCase):
    def review_pack_manifest(self) -> dict:
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
        }

    def surface_manifest(self) -> dict:
        data = self.review_pack_manifest()
        data.update(
            {
                "review_type": "surface_vc3d",
                "surface_review_protocol_version": "surface-vc3d-review-v1",
                "surface_metrics": {
                    "tifxyz_continuity": "present",
                    "valid_coverage": 0.98,
                    "neighbor_jump_p95": 1.1,
                    "layer_triplet_stability": "stable",
                },
                "surface_review_fields": {
                    "sheet_switch_visible": False,
                    "layer_continuity_blocker": False,
                    "boundary_or_crop_bias": False,
                    "compressed_region_risk": False,
                    "needs_vc3d_surface_review": False,
                },
            }
        )
        return data

    def preflight_manifest(self) -> dict:
        return {
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

    def handoff_manifest(self) -> dict:
        return {
            "handoff_protocol_version": "review-to-reading-handoff-v1",
            "source_readiness_files": ["pack_status.json", "surface_status.json", "preflight_status.json", "dossier.json"],
            "next_private_step_type": "vc3d-sheet-switch-review",
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

    def test_validator_output_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "pack.json", self.review_pack_manifest())
            write_json(root / "surface.json", self.surface_manifest())
            write_json(root / "preflight.json", self.preflight_manifest())
            pack = validate_pack(root / "pack.json", root / "pack_status.json")
            surface = validate_surface_review(root / "surface.json", root / "surface_status.json")
            preflight = validate_preflight_manifest(root / "preflight.json", root / "preflight_status.json")
            assert_no_claim_contract(self, pack, "review-pack-v1")
            assert_no_claim_contract(self, surface, "surface-vc3d-review-v1")
            assert_no_claim_contract(self, preflight, "full-volume-preflight-v1")
            self.assertEqual(pack["readiness_stage"], "manifest-valid")
            self.assertEqual(surface["readiness_stage"], "surface-ready")
            self.assertEqual(preflight["readiness_stage"], "preflight-ready")

    def test_handoff_and_priority_output_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "pack_status.json", {"decision": "review-pack-valid-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "manifest-valid", "readiness_blockers": []})
            write_json(root / "surface_status.json", {"decision": "surface-review-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "surface-ready", "readiness_blockers": []})
            write_json(root / "preflight_status.json", {"decision": "full-volume-preflight-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "preflight-ready", "readiness_blockers": []})
            write_json(root / "dossier.json", {"decision": "candidate-dossier-ready-no-claim", "status_ok": True, "claim_status": "no-claim", "public_claim_allowed": False, "target_inference_allowed": False, "readiness_stage": "review-ready", "readiness_blockers": []})
            write_json(root / "handoff.json", self.handoff_manifest())
            handoff = validate_handoff_manifest(root / "handoff.json", root / "handoff_status.json")
            priority = prioritize_outputs([root / "handoff_status.json"], root / "priority.json")
            assert_no_claim_contract(self, handoff, "review-to-reading-handoff-v1")
            assert_no_claim_contract(self, priority, "path-priority-v1")
            self.assertEqual(handoff["readiness_stage"], "handoff-ready")
            self.assertEqual(priority["decision"], "path-priority-ready-no-claim")

    def test_report_output_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "bundle.json", {"bundle_id": "demo-bundle", "blind_sheets": [{"blind_id": "D01"}]})
            write_json(root / "review.json", {"decision": "independent-review-received-no-controlled-next-step", "valid_response_count": 1, "supportive_response_count": 0})
            write_json(root / "second.json", {"decision": "waiting-no-success-trigger"})
            write_json(root / "release.json", {"decision": "release-audit-pass"})
            dossier = make_dossier(root / "bundle.json", root / "review.json", root / "second.json", root / "release.json", root / "dossier.json")
            inspect = inspect_outputs([root / "dossier.json"], root / "inspect.json")
            assert_no_claim_contract(self, dossier, "review-dossier-v1")
            assert_no_claim_contract(self, inspect, "inspect-summary-v1")
            self.assertEqual(dossier["readiness_stage"], "review-ready")
            self.assertEqual(inspect["readiness_stage"], "summary-ready")

    def test_release_check_output_contract(self) -> None:
        payload = release_check_payload([{"check_id": "leak-scan", "label": "leak-scan", "command": "internal", "status": "ok", "returncode": "0"}])
        assert_no_claim_contract(self, payload, "release-check-v1")
        self.assertEqual(payload["readiness_stage"], "release-ready")


if __name__ == "__main__":
    unittest.main()
