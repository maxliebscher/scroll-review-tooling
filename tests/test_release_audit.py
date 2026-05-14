from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.release_audit import audit


class ReleaseAuditTests(unittest.TestCase):
    def build_minimal_repo(self, root: Path) -> None:
        for rel in [
            "README.md",
            "CHECK_LOCAL_SETUP.cmd",
            "OPEN_LOCAL_OPERATOR.cmd",
            "RUN_LOCAL_DASHBOARD.cmd",
            "RUN_LOCAL_APP.cmd",
            "RUN_LOCAL_OPERATOR.cmd",
            "START_REVIEW_SESSION.cmd",
            "CHANGELOG.md",
            "LICENSE",
            "SECURITY.md",
            "PRIVACY.md",
            "RELEASE_CHECKLIST.md",
            "START_HERE.cmd",
            "START_HERE.md",
            "pyproject.toml",
            ".github/workflows/test.yml",
            "demo/handoff_manifest.json",
            "demo/session_manifest.json",
            "docs/LOCAL_OPERATOR_GUIDE.md",
            "docs/CONTINUATION_GUIDE.md",
            "docs/MANIFESTS.md",
            "docs/OPERATOR_APP_ROADMAP.md",
            "scripts/check_release.py",
            "scripts/local_dashboard.py",
            "scripts/local_operator.py",
            "scripts/operator_server.py",
            "scripts/operator_doctor.py",
            "scripts/operator_flow_check.py",
            "scripts/package_check.py",
            "scripts/start_session.py",
            "scroll_review_tooling/common.py",
            "scroll_review_tooling/data_sources.py",
            "scroll_review_tooling/manifest_validation.py",
            "scroll_review_tooling/operator_app.py",
            "scroll_review_tooling/operator_doctor.py",
            "scroll_review_tooling/operator_server.py",
            "scroll_review_tooling/reports.py",
            "scroll_review_tooling/review_workflow.py",
            "scroll_review_tooling/release_audit.py",
            "scroll_review_tooling/sessions.py",
            "tests/test_check_release.py",
            "tests/test_dashboard.py",
            "tests/test_data_sources.py",
            "tests/test_local_dashboard.py",
            "tests/test_launcher.py",
            "tests/test_operator_app.py",
            "tests/test_operator_doctor.py",
            "tests/test_operator_flow_check.py",
            "tests/test_operator_server.py",
            "tests/test_package_check.py",
            "tests/test_output_contracts.py",
            "tests/test_public_docs.py",
            "tests/test_release_audit.py",
            "tests/test_review_workflow.py",
            "tests/test_sessions.py",
        ]:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")

    def test_blocks_strategic_audit_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_minimal_repo(root)
            path = root / "docs" / ("PROJECT" + "_AUDIT_2026-05-07.md")
            path.parent.mkdir(exist_ok=True)
            path.write_text("claim-safe placeholder\n", encoding="utf-8")
            result = audit(root)
            self.assertEqual(result["decision"], "release-audit-blocked")
            self.assertIn("forbidden-strategic-audit-file", {f["reason"] for f in result["findings"]})

    def test_blocks_private_strategy_terms(self) -> None:
        blocked_terms = [
            "private " + "Discord export",
            "Prize-Relevant " + "Hypothesis",
            "Most Useful " + "Next Work",
            "Sources " + "checked:",
            "cf-" + "f34954d855fd7d16",
            "public_claim_allowed" + ": true",
            "target_inference_allowed" + ": true",
            "ink " + "found",
            "title " + "found",
            "reading " + "claim",
        ]
        for term in blocked_terms:
            with self.subTest(term=term):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.build_minimal_repo(root)
                    (root / "README.md").write_text(f"{term}\n", encoding="utf-8")
                    result = audit(root)
                    self.assertEqual(result["decision"], "release-audit-blocked")
                    self.assertIn("forbidden-private-or-secret-pattern", {f["reason"] for f in result["findings"]})

    def test_allows_claim_safe_readme_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_minimal_repo(root)
            (root / "README.md").write_text(
                "Review examples only; no OCR, no transcription, no reading, no public claim.\n",
                encoding="utf-8",
            )
            result = audit(root)
            self.assertEqual(result["decision"], "release-audit-pass")

    def test_requires_release_check_script_and_tests(self) -> None:
        for rel in ["scripts/check_release.py", "tests/test_check_release.py"]:
            with self.subTest(rel=rel):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.build_minimal_repo(root)
                    (root / rel).unlink()
                    result = audit(root)
                    self.assertEqual(result["decision"], "release-audit-blocked")
                    self.assertIn(rel, {f["path"] for f in result["findings"]})

    def test_blocks_raw_scan_and_model_suffixes(self) -> None:
        for rel in [
            "data/public/sample.zarr",
            "data/public/sample.tiff",
            "data/public/sample.npy",
            "models/checkpoint.pt",
            "models/checkpoint.safetensors",
        ]:
            with self.subTest(rel=rel):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.build_minimal_repo(root)
                    path = root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("raw placeholder\n", encoding="utf-8")
                    result = audit(root)
                    self.assertEqual(result["decision"], "release-audit-blocked")
                    self.assertIn("forbidden-heavy-or-raw-suffix", {f["reason"] for f in result["findings"]})

    def test_blocks_credentials_and_tokens(self) -> None:
        blocked_texts = [
            "api" + "_key = abc123",
            "to" + "ken: abc123",
            "author" + "ization = Bearer local",
        ]
        for text in blocked_texts:
            with self.subTest(text=text):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    self.build_minimal_repo(root)
                    (root / "README.md").write_text(text + "\n", encoding="utf-8")
                    result = audit(root)
                    self.assertEqual(result["decision"], "release-audit-blocked")
                    self.assertIn("forbidden-private-or-secret-pattern", {f["reason"] for f in result["findings"]})


if __name__ == "__main__":
    unittest.main()
