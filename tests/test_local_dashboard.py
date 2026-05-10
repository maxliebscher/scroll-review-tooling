from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.local_dashboard import local_dashboard_payload


class LocalDashboardTests(unittest.TestCase):
    def test_local_dashboard_payload_reports_ready_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dashboard = Path(tmp) / "dashboard.html"
            dashboard.write_text("<!doctype html>\n", encoding="utf-8")
            payload = local_dashboard_payload({"decision": "release-check-pass"}, dashboard)
            self.assertEqual(payload["decision"], "local-dashboard-ready")
            self.assertTrue(payload["status_ok"])
            self.assertEqual(payload["protocol_version"], "local-dashboard-launch-v1")
            self.assertEqual(payload["readiness_stage"], "dashboard-ready")
            self.assertEqual(payload["readiness_blockers"], [])
            self.assertEqual(payload["claim_status"], "no-claim")
            self.assertFalse(payload["public_claim_allowed"])
            self.assertFalse(payload["target_inference_allowed"])
            self.assertIn("no OCR", payload["claim_safety"])

    def test_local_dashboard_payload_blocks_failed_release_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dashboard = Path(tmp) / "dashboard.html"
            dashboard.write_text("<!doctype html>\n", encoding="utf-8")
            payload = local_dashboard_payload({"decision": "release-check-fail"}, dashboard)
            self.assertEqual(payload["decision"], "local-dashboard-blocked")
            self.assertFalse(payload["status_ok"])
            self.assertIn("release-check", payload["readiness_blockers"])

    def test_local_dashboard_payload_blocks_missing_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dashboard = Path(tmp) / "missing.html"
            payload = local_dashboard_payload({"decision": "release-check-pass"}, dashboard)
            self.assertEqual(payload["decision"], "local-dashboard-blocked")
            self.assertFalse(payload["status_ok"])
            self.assertIn("missing-dashboard", payload["readiness_blockers"])


if __name__ == "__main__":
    unittest.main()
