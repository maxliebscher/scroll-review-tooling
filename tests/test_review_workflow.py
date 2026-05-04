from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scroll_review_tooling.review_workflow import attention_delta, make_template, second_check, validate_inbox, write_json


class ReviewWorkflowTests(unittest.TestCase):
    def build_bundle(self) -> dict:
        return {
            "bundle_id": "demo-bundle",
            "blind_sheets": [
                {"blind_id": "D01", "path": "demo/images/D01.jpg"},
                {"blind_id": "D02", "path": "demo/images/D02.jpg"},
            ],
        }

    def build_response(self, template: dict, verdict: str) -> dict:
        data = json.loads(json.dumps(template))
        data["reviewer_alias"] = "unit-test"
        data["expertise_domain"] = "workflow"
        for key in data["required_acks"]:
            data["required_acks"][key] = True
        for row in data["blind_review_scores"]:
            row["surface_quality_1_to_5"] = 3
            row["artifact_risk_1_to_5"] = 2
            row["structured_signal_confidence_0_to_5"] = 1
            row["textlike_confidence_0_to_5"] = 0
        data["post_reveal_assessment"]["reveal_opened_after_blind_scores_recorded"] = True
        data["post_reveal_assessment"]["final_verdict"] = verdict
        return data

    def test_ambiguous_response_validates_without_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(self.build_bundle())
            template_path = root / "template.json"
            inbox = root / "inbox"
            inbox.mkdir()
            write_json(template_path, template)
            write_json(inbox / "ambiguous.json", self.build_response(template, "ambiguous"))
            status = validate_inbox(template_path, inbox, root / "status.json")
            self.assertEqual(status["decision"], "independent-review-received-no-controlled-next-step")
            self.assertEqual(status["valid_response_count"], 1)
            self.assertEqual(status["supportive_response_count"], 0)

    def test_supportive_response_triggers_attention_not_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(self.build_bundle())
            template_path = root / "template.json"
            inbox = root / "inbox"
            inbox.mkdir()
            write_json(template_path, template)
            write_json(inbox / "supportive.json", self.build_response(template, "supports-controlled-next-step"))
            status = validate_inbox(template_path, inbox, root / "status.json")
            second = second_check(root / "status.json", root / "second.json")
            attention = attention_delta(root / "second.json", root / "state.json", root / "attention.json", update_baseline=False)
            self.assertEqual(status["supportive_response_count"], 1)
            self.assertEqual(second["decision"], "attention-independent-review-supports-controlled-next-step")
            self.assertFalse(second["public_claim_allowed"])
            self.assertEqual(attention["decision"], "attention-action-trigger")

    def test_missing_ack_invalidates_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = make_template(self.build_bundle())
            template_path = root / "template.json"
            inbox = root / "inbox"
            inbox.mkdir()
            response = self.build_response(template, "supports-controlled-next-step")
            response["required_acks"]["no_ocr_or_transcription_attempted"] = False
            write_json(template_path, template)
            write_json(inbox / "bad.json", response)
            status = validate_inbox(template_path, inbox, root / "status.json")
            self.assertEqual(status["decision"], "waiting-for-independent-review-response")
            self.assertEqual(status["valid_response_count"], 0)
            self.assertIn("missing-ack:no_ocr_or_transcription_attempted", status["rows"][0]["protocol_violations"])


if __name__ == "__main__":
    unittest.main()
