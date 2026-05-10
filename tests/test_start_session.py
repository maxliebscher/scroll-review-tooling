from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.start_session import build_session


class Args:
    def __init__(self, **kwargs: object) -> None:
        self.inputs = kwargs.get("inputs", [])
        self.name = kwargs.get("name", "Synthetic Session")
        self.session_dir = kwargs.get("session_dir")
        self.bundle = kwargs.get("bundle", "demo/bundle_manifest.json")
        self.demo = kwargs.get("demo", False)
        self.no_audit = kwargs.get("no_audit", True)


class StartSessionTests(unittest.TestCase):
    def test_start_session_creates_isolated_demo_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = build_session(Args(session_dir=tmp, demo=True))
            out = Path(str(result["out_dir"]))
            self.assertEqual(result["decision"], "local-review-session-ready")
            self.assertTrue(result["status_ok"])
            self.assertTrue((out / "review_status.json").exists())
            self.assertTrue((out / "second_check.json").exists())
            self.assertTrue((out / "attention.json").exists())
            self.assertTrue((out / "session_summary.md").exists())
            self.assertEqual(result["claim_status"], "no-claim")
            self.assertFalse(result["public_claim_allowed"])
            self.assertFalse(result["target_inference_allowed"])

    def test_start_session_copies_dragged_json_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            response = root / "response.json"
            response.write_text('{"review_protocol_version":"wrong"}\n', encoding="utf-8")
            session_dir = root / "session"
            result = build_session(Args(session_dir=str(session_dir), inputs=[str(response)]))
            self.assertEqual(result["copied_input_count"], 1)
            self.assertTrue((session_dir / "inbox" / "response.json").exists())

    def test_start_session_rejects_non_json_dragged_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            response = root / "response.txt"
            response.write_text("not json\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                build_session(Args(session_dir=str(root / "session"), inputs=[str(response)]))

    def test_batch_wrapper_forwards_drag_drop_args_without_network_flags(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        text = (repo / "START_REVIEW_SESSION.cmd").read_text(encoding="utf-8")
        self.assertIn("%*", text)
        self.assertIn("python scripts\\start_session.py --demo", text)
        forbidden = ["--host", "--port", "curl", "Invoke-WebRequest", "http://", "https://"]
        for phrase in forbidden:
            self.assertNotIn(phrase.lower(), text.lower())


if __name__ == "__main__":
    unittest.main()
