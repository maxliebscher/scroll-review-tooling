from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.reports import render_dashboard
from scroll_review_tooling.review_workflow import write_json


class DashboardTests(unittest.TestCase):
    def test_dashboard_renders_static_no_claim_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "handoff.json",
                {
                    "decision": "review-to-reading-handoff-ready-no-claim",
                    "status_ok": True,
                    "claim_status": "no-claim",
                    "public_claim_allowed": False,
                    "target_inference_allowed": False,
                    "readiness_stage": "handoff-ready",
                    "readiness_blockers": [],
                    "next_private_step_type": "vc3d-sheet-switch-review",
                },
            )
            write_json(
                root / "priority.json",
                {
                    "decision": "path-priority-ready-no-claim",
                    "status_ok": True,
                    "claim_status": "no-claim",
                    "public_claim_allowed": False,
                    "target_inference_allowed": False,
                    "readiness_stage": "handoff-ready",
                    "readiness_blockers": [],
                    "ranked_rows": [
                        {
                            "path": "handoff.json",
                            "next_private_step_type": "vc3d-sheet-switch-review",
                            "status_ok": True,
                            "readiness_stage": "handoff-ready",
                            "readiness_blockers": [],
                        }
                    ],
                },
            )
            payload = render_dashboard([root / "handoff.json", root / "priority.json"], root / "dashboard.html")
            html = (root / "dashboard.html").read_text(encoding="utf-8")
            self.assertEqual(payload["decision"], "dashboard-handoff-ready-no-claim")
            self.assertTrue(payload["status_ok"])
            self.assertIn("<!doctype html>", html)
            self.assertIn("handoff-ready", html)
            self.assertIn("vc3d-sheet-switch-review", html)
            self.assertIn("No OCR", html)
            self.assertNotIn("<script", html.lower())
            self.assertNotIn("http://", html.lower())
            self.assertNotIn("https://", html.lower())
            self.assertNotIn("href=", html.lower())

    def test_dashboard_shows_risk_state_and_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unsafe = {
                "decision": "unsafe",
                "status_ok": True,
                "claim_status": "claim",
                "readiness_stage": "handoff-ready",
                "readiness_blockers": [],
            }
            unsafe["target_" + "inference_allowed"] = True
            write_json(root / "unsafe.json", unsafe)
            payload = render_dashboard([root / "unsafe.json"], root / "dashboard.html")
            html = (root / "dashboard.html").read_text(encoding="utf-8")
            self.assertEqual(payload["decision"], "dashboard-risk-detected")
            self.assertFalse(payload["status_ok"])
            self.assertIn("claim-safety", payload["readiness_blockers"])
            self.assertIn("claim-safety", html)
            self.assertIn("dashboard-risk-detected", html)

    def test_dashboard_tolerates_missing_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "minimal.json", {"decision": "minimal"})
            payload = render_dashboard([root / "minimal.json"], root / "dashboard.html")
            html = (root / "dashboard.html").read_text(encoding="utf-8")
            self.assertEqual(payload["decision"], "dashboard-ready-no-claim")
            self.assertIn("none", html)


if __name__ == "__main__":
    unittest.main()
