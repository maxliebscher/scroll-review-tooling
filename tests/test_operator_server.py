from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.operator_server import (
    ALLOWED_REPORTS,
    OPERATOR_SERVER_PROTOCOL_VERSION,
    read_status,
    render_home,
)


class OperatorServerTests(unittest.TestCase):
    def test_render_home_is_interactive_and_local_only(self) -> None:
        status = {
            "decision": "local-operator-ready",
            "status_ok": True,
            "readiness_stage": "operator-ready",
            "operator_headline_status": "Ready",
            "operator_tasks": [
                {"label": "Check setup", "status": "done", "action": "done", "output": "demo/out/operator_doctor.html"}
            ],
        }
        html = render_home(status)
        self.assertIn("Scroll Review Local App", html)
        self.assertIn('data-action="run-operator"', html)
        self.assertIn('data-action="run-setup"', html)
        self.assertIn("fetch('/action/' + action", html)
        self.assertIn("/report/dashboard", html)
        self.assertNotIn("https://", html.lower())
        self.assertNotIn("upload data", html.lower().split("does not", 1)[0])

    def test_read_status_before_operator_run_is_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = read_status(root)
            self.assertEqual(payload["protocol_version"], OPERATOR_SERVER_PROTOCOL_VERSION)
            self.assertEqual(payload["decision"], "operator-not-run")
            self.assertFalse(payload["status_ok"])
            self.assertEqual(payload["claim_status"], "no-claim")
            self.assertFalse(payload["public_claim_allowed"])
            self.assertFalse(payload["target_inference_allowed"])
            self.assertEqual(payload["server_scope"], "127.0.0.1-only")

    def test_read_status_loads_generated_operator_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            (out / "local_operator.json").write_text(
                json.dumps(
                    {
                        "decision": "local-operator-ready",
                        "status_ok": True,
                        "readiness_stage": "operator-ready",
                        "readiness_blockers": [],
                        "operator_tasks": [{"task_id": "setup", "status": "done"}],
                    }
                ),
                encoding="utf-8",
            )
            payload = read_status(root)
            self.assertEqual(payload["decision"], "local-operator-ready")
            self.assertTrue(payload["status_ok"])
            self.assertEqual(payload["operator_tasks"][0]["task_id"], "setup")

    def test_allowed_reports_are_generated_outputs_only(self) -> None:
        for rel in ALLOWED_REPORTS.values():
            self.assertTrue(rel.startswith("demo/out/"))
            self.assertNotIn("..", rel)


if __name__ == "__main__":
    unittest.main()
