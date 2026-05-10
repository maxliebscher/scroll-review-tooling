from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_release import leak_scan, release_check_markdown, release_check_payload, write_outputs


class CheckReleaseTests(unittest.TestCase):
    def test_release_check_payload_shape(self) -> None:
        payload = release_check_payload([{"check_id": "leak-scan", "label": "leak-scan", "command": "internal", "status": "ok", "returncode": "0"}])
        self.assertIn("created", payload)
        self.assertEqual(payload["decision"], "release-check-pass")
        self.assertTrue(payload["status_ok"])
        self.assertEqual(payload["release_check_protocol_version"], "release-check-v1")
        self.assertEqual(payload["protocol_version"], "release-check-v1")
        self.assertEqual(payload["readiness_stage"], "release-ready")
        self.assertEqual(payload["readiness_blockers"], [])
        self.assertEqual(payload["claim_status"], "no-claim")
        self.assertFalse(payload["public_claim_allowed"])
        self.assertFalse(payload["target_inference_allowed"])
        self.assertIn("checks", payload)
        self.assertIn("leak-scan", {row["check_id"] for row in payload["checks"]})
        self.assertIn("leak-scan", {row["label"] for row in payload["checks"]})

    def test_release_check_payload_records_failed_check(self) -> None:
        payload = release_check_payload([{"check_id": "unit-tests", "label": "unit-tests", "command": "test", "status": "failed", "returncode": "1"}])
        self.assertEqual(payload["decision"], "release-check-fail")
        self.assertFalse(payload["status_ok"])
        self.assertEqual(payload["readiness_stage"], "blocked")
        self.assertEqual(payload["readiness_blockers"], ["unit-tests"])
        self.assertEqual(payload["claim_status"], "no-claim")

    def test_release_check_markdown_is_claim_safe(self) -> None:
        payload = release_check_payload([{"check_id": "leak-scan", "label": "leak-scan", "command": "internal", "status": "ok", "returncode": "0"}])
        markdown = release_check_markdown(payload)
        self.assertIn("# Release Check", markdown)
        self.assertIn("Created:", markdown)
        self.assertIn("Protocol: `release-check-v1`", markdown)
        self.assertIn("Readiness: `release-ready`", markdown)
        self.assertIn("Public claim allowed: `False`", markdown)
        self.assertIn("leak-scan", markdown)
        self.assertIn("No OCR", markdown)

    def test_write_outputs_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = release_check_payload([{"check_id": "leak-scan", "label": "leak-scan", "command": "internal", "status": "ok", "returncode": "0"}])
            write_outputs(payload, str(root / "release_check.json"), str(root / "release_check.md"))
            self.assertIn("release-check-pass", (root / "release_check.json").read_text(encoding="utf-8"))
            self.assertIn("# Release Check", (root / "release_check.md").read_text(encoding="utf-8"))

    def test_leak_scan_passes_claim_safe_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Review tooling only; no OCR, no transcription, no reading, no public claim.\n",
                encoding="utf-8",
            )
            result = leak_scan(root)
            self.assertEqual(result["check_id"], "leak-scan")
            self.assertEqual(result["label"], "leak-scan")
            self.assertEqual(result["status"], "ok")

    def test_leak_scan_blocks_private_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("private " + "Discord export\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                leak_scan(root)


if __name__ == "__main__":
    unittest.main()
