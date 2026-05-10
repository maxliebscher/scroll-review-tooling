from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.operator_app import OPERATOR_APP_PROTOCOL_VERSION, render_operator_app


class OperatorAppTests(unittest.TestCase):
    def test_operator_app_renders_static_no_claim_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dashboard = root / "demo" / "out" / "dashboard.html"
            dashboard.parent.mkdir(parents=True)
            dashboard.write_text("<!doctype html>\n", encoding="utf-8")
            payload = render_operator_app(
                out_html=root / "demo" / "out" / "operator.html",
                out_json=root / "demo" / "out" / "local_operator.json",
                out_md=root / "demo" / "out" / "operator_summary.md",
                repo_root=root,
                session_payload={"status_ok": True, "decision": "local-review-session-valid", "session_name": "Synthetic session"},
                release_payload={"decision": "release-check-pass"},
                dashboard_payload={"status_ok": True, "decision": "dashboard-handoff-ready-no-claim"},
                dashboard_html=dashboard,
            )
            html = (root / "demo" / "out" / "operator.html").read_text(encoding="utf-8")
            md = (root / "demo" / "out" / "operator_summary.md").read_text(encoding="utf-8")
            self.assertEqual(payload["protocol_version"], OPERATOR_APP_PROTOCOL_VERSION)
            self.assertEqual(payload["decision"], "local-operator-ready")
            self.assertTrue(payload["status_ok"])
            self.assertEqual(payload["operator_headline_status"], "Ready: open dashboard and share summary")
            self.assertTrue(payload["operator_can_continue"])
            self.assertEqual(payload["operator_next_command"], "OPEN_LOCAL_OPERATOR.cmd")
            self.assertIn("demo/out/dashboard.html", payload["operator_shareable_outputs"])
            self.assertIn("Scroll Review Local Operator", html)
            self.assertIn("no upload", html)
            self.assertIn("no OCR", html)
            self.assertIn("manifest guided", html)
            self.assertIn('href="dashboard.html"', html)
            self.assertIn('href="local_operator.json"', html)
            self.assertIn('href="release_check.json"', html)
            self.assertIn('href="operator_summary.md"', html)
            self.assertIn("this page is static", html)
            self.assertIn("Who Gets What", html)
            self.assertIn("What Needs Attention", html)
            self.assertIn("The synthetic session, release gate, dashboard, and share summary are ready.", html)
            self.assertIn("Share Guidance", md)
            self.assertIn("Next local step", md)
            self.assertIn("Public claim allowed: `False`", md)
            self.assertIn("Headline status: `Ready: open dashboard and share summary`", md)
            self.assertNotIn("<script", html.lower())
            self.assertNotIn("http://", html.lower())
            self.assertNotIn("https://", html.lower())
            self.assertNotIn("upload endpoint", html.lower())

    def test_operator_app_blocks_when_session_or_dashboard_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = render_operator_app(
                out_html=root / "operator.html",
                out_json=root / "operator.json",
                repo_root=root,
                session_payload={"status_ok": False, "decision": "local-review-session-blocked"},
                release_payload={"decision": "release-check-pass"},
                dashboard_payload={"status_ok": False, "decision": "dashboard-blocked-no-claim"},
                dashboard_html=root / "missing-dashboard.html",
            )
            html = (root / "operator.html").read_text(encoding="utf-8")
            self.assertEqual(payload["decision"], "local-operator-blocked")
            self.assertFalse(payload["status_ok"])
            self.assertFalse(payload["operator_can_continue"])
            self.assertEqual(payload["operator_next_command"], "RUN_LOCAL_OPERATOR.cmd")
            self.assertEqual(payload["operator_shareable_outputs"], [])
            self.assertIn("session", payload["readiness_blockers"])
            self.assertIn("dashboard", payload["readiness_blockers"])
            self.assertEqual(len(payload["operator_guidance"]), 2)
            self.assertIn("local-operator-blocked", html)
            self.assertIn("session blocked", html)
            self.assertIn("dashboard missing or blocked", html)

    def test_operator_app_escapes_input_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dashboard = root / "dashboard.html"
            dashboard.write_text("<!doctype html>\n", encoding="utf-8")
            render_operator_app(
                out_html=root / "operator.html",
                out_json=root / "operator.json",
                repo_root=root,
                session_payload={"status_ok": True, "decision": "<script>alert(1)</script>", "session_name": "<img src=x>"},
                release_payload={"decision": "release-check-pass"},
                dashboard_payload={"status_ok": True, "decision": "dashboard-ready-no-claim"},
                dashboard_html=dashboard,
            )
            html = (root / "operator.html").read_text(encoding="utf-8")
            self.assertIn("&lt;img", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn("<img src=x", html)
            self.assertNotIn("<script>alert", html)


if __name__ == "__main__":
    unittest.main()
