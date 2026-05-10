from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.operator_doctor import (
    OPERATOR_DOCTOR_PROTOCOL_VERSION,
    build_doctor_payload,
    render_doctor_html,
    render_doctor_markdown,
    write_doctor_outputs,
)


class OperatorDoctorTests(unittest.TestCase):
    def build_repo(self, root: Path) -> None:
        for rel in [
            "README.md",
            "OPEN_LOCAL_OPERATOR.cmd",
            "RUN_LOCAL_OPERATOR.cmd",
            "START_REVIEW_SESSION.cmd",
            "scripts/local_operator.py",
            "scripts/start_session.py",
            "demo/session_manifest.json",
            "demo/out/review_pack_status.json",
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")
        (root / "demo/session_manifest.json").write_text(
            """{
  "session_protocol_version": "local-review-session-v1",
  "session_name": "Synthetic operator session",
  "dashboard_inputs": ["demo/out/review_pack_status.json"],
  "dashboard_output": "demo/out/dashboard.html",
  "claim_safety": "No OCR, no transcription, no reading, no public claim."
}
""",
            encoding="utf-8",
        )
        (root / "demo/out/review_pack_status.json").write_text(
            """{
  "decision": "review-pack-valid-no-claim",
  "status_ok": true,
  "protocol_version": "review-pack-v1",
  "claim_status": "no-claim",
  "public_claim_allowed": false,
  "target_inference_allowed": false
}
""",
            encoding="utf-8",
        )

    def test_doctor_reports_ready_for_valid_local_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_repo(root)
            payload = build_doctor_payload(root, Path("demo/session_manifest.json"))
            self.assertEqual(payload["protocol_version"], OPERATOR_DOCTOR_PROTOCOL_VERSION)
            self.assertEqual(payload["decision"], "operator-doctor-ready")
            self.assertTrue(payload["status_ok"])
            self.assertEqual(payload["operator_next_command"], "OPEN_LOCAL_OPERATOR.cmd")
            self.assertIn("data-boundary", {check["check_id"] for check in payload["checks"]})
            html = render_doctor_html(payload)
            md = render_doctor_markdown(payload)
            self.assertIn("Scroll Review Setup Doctor", html)
            self.assertIn("No OCR", md)
            self.assertNotIn("<script", html.lower())
            self.assertNotIn("http://", html.lower())
            self.assertNotIn("https://", html.lower())

    def test_doctor_blocks_missing_session_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_repo(root)
            (root / "demo/session_manifest.json").unlink()
            payload = build_doctor_payload(root, Path("demo/session_manifest.json"))
            self.assertEqual(payload["decision"], "operator-doctor-blocked")
            self.assertFalse(payload["status_ok"])
            self.assertIn("session-manifest", payload["readiness_blockers"])
            self.assertEqual(payload["operator_next_command"], "CHECK_LOCAL_SETUP.cmd")

    def test_doctor_escapes_written_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "decision": "<script>alert(1)</script>",
                "status_ok": False,
                "operator_next_command": "<img src=x>",
                "checks": [{"label": "<b>bad</b>", "status": "blocked", "detail": "<script>", "next_step": "<img>"}],
            }
            write_doctor_outputs(
                payload,
                out_json=root / "doctor.json",
                out_md=root / "doctor.md",
                out_html=root / "doctor.html",
            )
            html = (root / "doctor.html").read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;", html)
            self.assertIn("&lt;img", html)
            self.assertNotIn("<script>alert", html)
            self.assertNotIn("<img src=x", html)


if __name__ == "__main__":
    unittest.main()
