from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.data_sources import (
    CHUNK_FETCH_PROTOCOL_VERSION,
    CHUNK_PLAN_PROTOCOL_VERSION,
    LOCAL_WORKSPACE_LABEL,
    MAX_FETCH_BYTES,
    SCAN_READINESS_PROTOCOL_VERSION,
    SOURCE_CATALOG_PROTOCOL_VERSION,
    WORKSPACE_PROTOCOL_VERSION,
    check_workspace,
    fetch_chunk,
    plan_chunk,
    scan_readiness,
    source_catalog,
)


class DataSourceWorkflowTests(unittest.TestCase):
    def test_source_catalog_reports_optional_adapter_without_crashing(self) -> None:
        catalog = source_catalog()
        self.assertEqual(catalog["protocol_version"], SOURCE_CATALOG_PROTOCOL_VERSION)
        self.assertTrue(catalog["status_ok"])
        self.assertIn(catalog["adapter_status"], {"adapter-available", "adapter-unavailable"})
        self.assertFalse(catalog["public_claim_allowed"])
        self.assertFalse(catalog["target_inference_allowed"])
        public_demo = [source for source in catalog["sources"] if source["source_id"] == "public-demo"][0]
        vesuvius_public = [source for source in catalog["sources"] if source["source_id"] == "vesuvius-public"][0]
        self.assertTrue(public_demo["public_access"])
        self.assertEqual(public_demo["adapter_readiness"]["status"], "ready")
        self.assertTrue(public_demo["adapter_readiness"]["can_plan"])
        self.assertTrue(public_demo["adapter_readiness"]["can_fetch"])
        self.assertFalse(public_demo["credential_required"])
        self.assertFalse(public_demo["full_volume_allowed"])
        self.assertIn("why_start_here", public_demo)
        self.assertIn("what_you_get", public_demo)
        self.assertIn("limitations", public_demo)
        self.assertIn("preset_guidance", public_demo)
        self.assertEqual(public_demo["recommended_start_points"][0]["preset"], "tiny-preview")
        self.assertIn("why_this_choice", public_demo["recommended_start_points"][0])
        self.assertTrue(vesuvius_public["public_access"])
        self.assertFalse(vesuvius_public["credential_required"])
        self.assertFalse(vesuvius_public["full_volume_allowed"])
        self.assertFalse(vesuvius_public["fetch_enabled"])
        self.assertIn(vesuvius_public["adapter_readiness"]["status"], {"adapter-ready", "setup-needed"})
        if not vesuvius_public["adapter_available"]:
            self.assertFalse(vesuvius_public["adapter_readiness"]["can_plan"])
            self.assertIn("Use the built-in public demo", vesuvius_public["adapter_readiness"]["setup_hint"])

    def test_workspace_checker_blocks_repo_paths_and_accepts_user_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            repo = Path(repo_tmp)
            blocked = check_workspace(repo / "data-workspace", repo)
            self.assertEqual(blocked["protocol_version"], WORKSPACE_PROTOCOL_VERSION)
            self.assertFalse(blocked["status_ok"])
            self.assertIn("workspace-inside-repo", blocked["violations"])

            ready = check_workspace(Path(workspace_tmp), repo)
            self.assertTrue(ready["status_ok"])
            self.assertEqual(ready["workspace_label"], LOCAL_WORKSPACE_LABEL)
            self.assertTrue((Path(workspace_tmp) / ".scroll-review-workspace.json").exists())

    def test_chunk_planner_blocks_full_volume_and_private_like_sources(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            blocked = plan_chunk("private-source", "scan", "full-volume", Path(workspace_tmp), Path(repo_tmp))
            self.assertEqual(blocked["protocol_version"], CHUNK_PLAN_PROTOCOL_VERSION)
            self.assertFalse(blocked["status_ok"])
            self.assertIn("unknown-source", blocked["violations"])
            self.assertIn("invalid-preset", blocked["violations"])
            self.assertIn("full-volume-not-allowed", blocked["violations"])

    def test_fetch_redacts_workspace_and_scan_readiness_is_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            repo = Path(repo_tmp)
            plan_path = repo / "plan.json"
            fetch_path = repo / "fetch.json"
            readiness_path = repo / "readiness.json"
            md_path = repo / "readiness.md"

            plan = plan_chunk("public-demo", "synthetic-public-scroll", "tiny-preview", Path(workspace_tmp), repo, plan_path)
            self.assertTrue(plan["status_ok"])
            self.assertLessEqual(plan["plan"]["estimated_bytes"], MAX_FETCH_BYTES)
            self.assertEqual(plan["selection_rationale"]["workspace_label"], LOCAL_WORKSPACE_LABEL)
            self.assertIn("No OCR", plan["selection_rationale"]["not_performed"])
            self.assertNotIn(str(Path(workspace_tmp)), str(plan["selection_rationale"]))

            fetched = fetch_chunk(plan_path, fetch_path)
            self.assertEqual(fetched["protocol_version"], CHUNK_FETCH_PROTOCOL_VERSION)
            self.assertTrue(fetched["status_ok"])
            self.assertEqual(fetched["workspace_label"], LOCAL_WORKSPACE_LABEL)
            self.assertNotIn(str(Path(workspace_tmp)), str(fetched))
            self.assertGreater(fetched["byte_count"], 0)
            self.assertEqual(fetched["selection_rationale"]["preset_label"], "Tiny preview")

            readiness = scan_readiness(fetch_path, readiness_path, md_path)
            self.assertEqual(readiness["protocol_version"], SCAN_READINESS_PROTOCOL_VERSION)
            self.assertEqual(readiness["readiness_stage"], "data-ready")
            self.assertIn("Chunk stored locally", readiness["operator_summary"])
            self.assertEqual(readiness["selection_rationale"]["source"], "public-demo")
            self.assertFalse(readiness["public_claim_allowed"])
            self.assertFalse(readiness["target_inference_allowed"])
            self.assertIn("no ocr", md_path.read_text(encoding="utf-8").lower())

    def test_fetch_revalidates_plan_workspace_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo = Path(repo_tmp)
            plan_path = repo / "plan.json"
            fetch_path = repo / "fetch.json"
            plan = plan_chunk("public-demo", "synthetic-public-scroll", "tiny-preview", repo / "unsafe", repo)
            plan["status_ok"] = True
            plan["decision"] = "chunk-download-plan-ready"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            fetched = fetch_chunk(plan_path, fetch_path, repo_root=repo)

            self.assertFalse(fetched["status_ok"])
            self.assertIn("workspace-blocked", fetched["violations"])
            self.assertFalse((repo / "unsafe/chunks/public-demo/synthetic-public-scroll/tiny-preview/chunk.bin").exists())

    def test_fetch_blocks_chunk_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            repo = Path(repo_tmp)
            plan_path = repo / "plan.json"
            fetch_path = repo / "fetch.json"
            plan = plan_chunk("public-demo", "synthetic-public-scroll", "tiny-preview", Path(workspace_tmp), repo)
            plan["plan"]["preset"] = "../../../../escape"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            fetched = fetch_chunk(plan_path, fetch_path, repo_root=repo)

            self.assertFalse(fetched["status_ok"])
            self.assertIn("invalid-preset", fetched["violations"])
            self.assertIn("chunk-path-outside-workspace", fetched["violations"])
            self.assertFalse((Path(workspace_tmp).parent / "escape/tiny-preview/chunk.bin").exists())


if __name__ == "__main__":
    unittest.main()
