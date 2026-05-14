from __future__ import annotations

import unittest

from scripts.operator_flow_check import run_operator_flow_check


class OperatorFlowCheckTests(unittest.TestCase):
    def test_operator_http_flow_runs_to_review_ready(self) -> None:
        payload = run_operator_flow_check()
        self.assertEqual(payload["decision"], "operator-flow-check-pass")
        self.assertTrue(payload["status_ok"])
        self.assertEqual(payload["readiness_blockers"], [])
        self.assertEqual(payload["claim_status"], "no-claim")
        self.assertFalse(payload["public_claim_allowed"])
        self.assertFalse(payload["target_inference_allowed"])
        self.assertTrue(payload["workspace_marker_exists"])
        self.assertTrue(payload["chunk_exists"])
        self.assertGreater(payload["chunk_byte_count"], 0)
        self.assertEqual(
            {row["action"] for row in payload["actions"]},
            {
                "run-setup",
                "check-workspace",
                "source-catalog",
                "plan-chunk",
                "fetch-chunk",
                "scan-readiness",
            },
        )
        self.assertTrue(all(row["ok"] for row in payload["actions"]))
        self.assertTrue(all(row["claim_safe_copy"] for row in payload["reports"].values()))


if __name__ == "__main__":
    unittest.main()
