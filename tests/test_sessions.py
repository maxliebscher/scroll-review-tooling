from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.review_workflow import write_json
from scroll_review_tooling.sessions import validate_session_manifest


class SessionTests(unittest.TestCase):
    def write_input(self, root: Path, name: str = "handoff.json") -> None:
        write_json(
            root / name,
            {
                "decision": "review-to-reading-handoff-ready-no-claim",
                "status_ok": True,
                "claim_status": "no-claim",
                "public_claim_allowed": False,
                "target_inference_allowed": False,
                "readiness_stage": "handoff-ready",
                "readiness_blockers": [],
            },
        )

    def session_manifest(self, input_name: str = "handoff.json") -> dict:
        return {
            "session_protocol_version": "local-review-session-v1",
            "session_name": "Synthetic local session",
            "dashboard_inputs": [input_name],
            "dashboard_output": "dashboard.html",
            "claim_safety": "Synthetic local session only; no OCR, no transcription, no reading, no public claim.",
            "public_claim_allowed": False,
            "target_inference_allowed": False,
        }

    def test_valid_session_manifest_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_input(root)
            write_json(root / "session.json", self.session_manifest())
            status = validate_session_manifest(root / "session.json")
            self.assertEqual(status["decision"], "local-review-session-valid")
            self.assertTrue(status["status_ok"])
            self.assertEqual(status["readiness_stage"], "session-ready")
            self.assertEqual(status["session_name"], "Synthetic local session")
            self.assertEqual(status["readiness_blockers"], [])

    def test_session_blocks_missing_dashboard_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "session.json", self.session_manifest("missing.json"))
            status = validate_session_manifest(root / "session.json")
            self.assertEqual(status["decision"], "local-review-session-blocked")
            self.assertFalse(status["status_ok"])
            self.assertIn("dashboard-inputs", status["readiness_blockers"])

    def test_session_blocks_private_candidate_like_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_input(root)
            manifest = self.session_manifest()
            manifest["candidate_id"] = "synthetic-placeholder"
            manifest["notes"] = {"private_path": "synthetic-private-placeholder"}
            write_json(root / "session.json", manifest)
            status = validate_session_manifest(root / "session.json")
            self.assertFalse(status["status_ok"])
            self.assertIn("private-material", status["readiness_blockers"])

    def test_session_blocks_claim_risk_and_external_urls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_input(root)
            manifest = self.session_manifest()
            manifest["claim_safety"] = "Synthetic local session only."
            manifest["target_" + "inference_allowed"] = True
            manifest["dashboard_inputs"] = ["https://example.invalid/status.json"]
            write_json(root / "session.json", manifest)
            status = validate_session_manifest(root / "session.json")
            self.assertFalse(status["status_ok"])
            self.assertIn("claim-safety", status["readiness_blockers"])
            self.assertIn("private-material", status["readiness_blockers"])

    def test_dashboard_cli_can_render_from_session(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_input(root)
            manifest = self.session_manifest()
            write_json(root / "session.json", manifest)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scroll_review_tooling.review_workflow",
                    "dashboard",
                    "--session",
                    str(root / "session.json"),
                ],
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("dashboard-handoff-ready-no-claim", (root / "dashboard.html").read_text(encoding="utf-8"))

    def test_missing_optional_dashboard_output_uses_default_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_input(root)
            manifest = self.session_manifest()
            manifest.pop("dashboard_output")
            write_json(root / "session.json", manifest)
            status = validate_session_manifest(root / "session.json")
            self.assertTrue(status["status_ok"])
            self.assertTrue(status["dashboard_output"].endswith("demo/out/dashboard.html"))


if __name__ == "__main__":
    unittest.main()
