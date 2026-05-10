from __future__ import annotations

import unittest
from pathlib import Path

from scroll_review_tooling.reports import render_dashboard
from scroll_review_tooling.review_workflow import write_json
from scroll_review_tooling.sessions import validate_session_manifest


class PublicDocsTests(unittest.TestCase):
    def test_docs_avoid_hosted_upload_or_import_language(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        docs = [
            repo / "README.md",
            repo / "docs" / "LOCAL_OPERATOR_GUIDE.md",
        ]
        forbidden = [
            "hosted mode",
            "upload flow",
            "candidate import",
            "drag-and-drop",
            "public web app",
        ]
        for path in docs:
            text = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, text)

    def test_session_blocks_forbidden_suffixes_with_unusual_casing(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with self.subTest("image suffix"):
            manifest = {
                "session_protocol_version": "local-review-session-v1",
                "session_name": "Synthetic invalid session",
                "dashboard_inputs": ["demo/out/Preview.JPG"],
                "claim_safety": "Synthetic only; no OCR, no transcription, no reading, no public claim.",
            }
            temp = repo / "demo" / "out" / "session_suffix_test.json"
            write_json(temp, manifest)
            status = validate_session_manifest(temp)
            self.assertFalse(status["status_ok"])
            self.assertIn("dashboard-inputs", status["readiness_blockers"])

    def test_dashboard_escapes_suspicious_input_text(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        source = repo / "demo" / "out" / "escape_input.json"
        out_html = repo / "demo" / "out" / "escape_dashboard.html"
        write_json(
            source,
            {
                "decision": "<img src=x onerror=alert(1)>",
                "status_ok": True,
                "claim_status": "no-claim",
                "public_claim_allowed": False,
                "target_inference_allowed": False,
                "readiness_stage": "handoff-ready",
                "readiness_blockers": ["<script>alert(1)</script>"],
            },
        )
        render_dashboard([source], out_html)
        html = out_html.read_text(encoding="utf-8")
        self.assertIn("&lt;img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<script>alert", html)


if __name__ == "__main__":
    unittest.main()
