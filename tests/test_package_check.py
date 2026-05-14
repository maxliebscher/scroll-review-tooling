from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.package_check import build_package_check_payload


class PackageCheckScriptTests(unittest.TestCase):
    def test_package_check_payload_is_no_claim_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("public no-claim source\n", encoding="utf-8")
            payload = build_package_check_payload(root)

        self.assertEqual(payload["decision"], "package-check-pass")
        self.assertTrue(payload["status_ok"])
        self.assertEqual(payload["protocol_version"], "package-check-v1")
        self.assertEqual(payload["readiness_stage"], "package-ready")
        self.assertEqual(payload["readiness_blockers"], [])
        self.assertEqual(payload["claim_status"], "no-claim")
        self.assertFalse(payload["public_claim_allowed"])
        self.assertFalse(payload["target_inference_allowed"])
        self.assertFalse(payload["archive_written"])

    def test_package_check_payload_blocks_generated_and_raw_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocked = [
                "demo/out/dashboard.html",
                "chunks/public/sample.tif",
                "models/model.ckpt",
                "notes/local.txt",
            ]
            for rel in blocked:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                text = ("to" + "ken: local\n") if rel == "notes/local.txt" else "placeholder\n"
                path.write_text(text, encoding="utf-8")
            payload = build_package_check_payload(root)

        self.assertEqual(payload["decision"], "package-check-blocked")
        self.assertFalse(payload["status_ok"])
        self.assertEqual(payload["readiness_stage"], "blocked")
        self.assertGreaterEqual(payload["finding_count"], 4)
        self.assertIn("demo/out/dashboard.html", payload["readiness_blockers"])
        self.assertIn("chunks/public/sample.tif", payload["readiness_blockers"])


if __name__ == "__main__":
    unittest.main()
