from __future__ import annotations

from email.message import Message
import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path

from scripts import operator_server as local_server
from scroll_review_tooling.operator_server import (
    ALLOWED_REPORTS,
    GITHUB_REPO_URL,
    OPERATOR_SERVER_PROTOCOL_VERSION,
    read_status,
    render_home,
    run_guided_chunk_flow,
)


def _step_payload(decision: str, protocol: str, status_ok: bool = True, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision": decision,
        "status_ok": status_ok,
        "protocol_version": protocol,
        "claim_status": "no-claim",
        "public_claim_allowed": False,
        "target_inference_allowed": False,
    }
    payload.update(extra)
    return payload


class OperatorServerTests(unittest.TestCase):
    def test_render_home_is_interactive_and_local_only(self) -> None:
        status = {
            "decision": "local-operator-ready",
            "status_ok": True,
            "readiness_stage": "operator-ready",
            "operator_headline_status": "Ready",
            "operator_tasks": [
                {"label": "Check setup", "status": "done", "action": "done", "output": "demo/out/operator_doctor.html"}
            ],
        }
        html = render_home(status)
        self.assertIn("Scroll Review<br>Operator Studio", html)
        self.assertIn('name="scroll-review-tooling-version"', html)
        self.assertIn('name="scroll-review-action"', html)
        self.assertIn('data-version-from-meta', html)
        self.assertIn('href="#wizard"', html)
        self.assertIn('href="#home"', html)
        self.assertIn('href="#review"', html)
        self.assertIn('href="#safety"', html)
        nav_html = html.split('<nav class="nav">', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn(GITHUB_REPO_URL, nav_html)
        self.assertNotIn("GitHub", nav_html)
        self.assertIn('aria-label="Utility links"', html)
        self.assertIn("Source code", html)
        self.assertIn("Operator cockpit", html)
        self.assertIn("Data journey", html)
        self.assertIn("What data gets picked, and why?", html)
        self.assertIn("Public source", html)
        self.assertIn("Catalog scan label", html)
        self.assertIn("Small chunk preset", html)
        self.assertIn("Local workspace", html)
        self.assertIn("Readiness summary", html)
        self.assertIn("Review report", html)
        self.assertIn("Readiness summary", html)
        self.assertIn("Operator board (optional)", html)
        self.assertIn("Advanced step details and manual controls", html)
        self.assertIn("Most users can stay in the wizard", html)
        self.assertIn("Functional operator wizard", html)
        self.assertIn("First run", html)
        self.assertIn("Wizard step list", html)
        self.assertIn("Wizard inspector", html)
        self.assertIn("Active step", html)
        self.assertIn("What happens next?", html)
        self.assertIn("Output files", html)
        self.assertIn("Supporting views are below.", html)
        workspace_html = render_home({"operator_wizard": {"active_step": "workspace"}})
        self.assertIn("Use suggested workspace and check", workspace_html)
        self.assertIn("data-use-suggested-workspace", workspace_html)
        self.assertIn('data-source-action="check-workspace"', workspace_html)
        review_html = render_home(
            {
                "operator_wizard": {
                    "active_step": "review",
                    "active_label": "Review",
                    "next_action": "dashboard",
                    "next_action_type": "report",
                    "next_action_label": "Open review reports",
                    "mode": "ready",
                    "mode_label": "Review ready",
                    "steps": [{"step_id": "review", "label": "Review", "status": "ready", "level": "ok", "decision": "review-ready"}],
                }
            }
        )
        self.assertIn("Ready to review", review_html)
        self.assertIn("Review ready", review_html)
        self.assertNotIn("Use suggested workspace and check", review_html)
        self.assertIn("Priority queue", html)
        self.assertIn("Kanban readiness board", html)
        self.assertIn("Local review wizard, not a reader.", html)
        self.assertIn("Operator app bar", html)
        self.assertIn("infer letters, or make claims", html)
        self.assertIn("127.0.0.1 only", html)
        self.assertIn("What should I do next?", html)
        self.assertIn("Data step results", html)
        self.assertIn("Choose workspace", html)
        self.assertIn("Check source", html)
        self.assertIn("Plan small chunk", html)
        self.assertIn("Fetch small chunk", html)
        self.assertIn("Create readiness summary", html)
        self.assertIn("Review package", html)
        self.assertIn("Open review reports", html)
        self.assertIn("Load public scan chunk", html)
        self.assertIn("Public source catalog choices", html)
        self.assertIn("Built-in public demo chunk - Ready now", html)
        self.assertIn("Start:", html)
        self.assertIn("max 2.0 MB", html)
        self.assertIn("Setup needed", html)
        self.assertIn("Vesuvius public adapter", html)
        self.assertIn("Run all data steps", html)
        self.assertIn("last-action-result", html)
        self.assertIn("data-source-action=\"guided-chunk-flow\"", html)
        self.assertIn("data-source-action=\"source-catalog\"", html)
        self.assertIn("data-source-action=\"check-workspace\"", html)
        self.assertIn("data-source-action=\"plan-chunk\"", html)
        self.assertIn("data-source-action=\"fetch-chunk\"", html)
        self.assertIn("metadata-safe starting points", html)
        self.assertIn("What this is", html)
        self.assertIn("A local readiness desk, not a reader.", html)
        self.assertIn("data-toggle-info", html)
        self.assertIn("data-toggle-theme", html)
        self.assertIn("document.createElement('strong')", html)
        self.assertIn("operator_result_summary", html)
        self.assertNotIn("resultBox.innerHTML", html)
        self.assertIn("applySuggestedWorkspace(trigger)", html)
        self.assertIn("X-Scroll-Review-Action", html)
        self.assertIn('data-theme="dark"', html)
        self.assertIn(GITHUB_REPO_URL, html)
        self.assertIn('data-action="run-operator"', html)
        self.assertIn('data-action="run-setup"', html)
        self.assertIn("fetch('/action/' + action", html)
        self.assertIn("/report/dashboard", html)
        self.assertIn("/report/setup", review_html)
        self.assertIn("Local only.", html)
        self.assertNotIn("upload data", html.lower().split("does not", 1)[0])

        source_html = render_home(
            {
                "operator_wizard": {
                    "active_step": "source",
                    "active_label": "Choose data",
                    "active_description": "Confirm public source catalog access.",
                    "next_action": "source-catalog",
                    "next_action_type": "source-action",
                    "next_action_label": "Check public catalog",
                    "mode": "in-progress",
                    "mode_label": "2/6 steps ready",
                    "steps": [{"step_id": "source", "label": "Choose data", "status": "waiting", "level": "warn", "decision": "not run"}],
                }
            }
        )
        self.assertIn("Choose public data", source_html)
        self.assertIn("Pick a small, explainable starting point.", source_html)
        self.assertIn("Why this choice?", source_html)
        self.assertIn("What you get next:", source_html)
        self.assertIn("Estimated size", source_html)
        self.assertIn("Storage", source_html)
        self.assertIn("Public data selectors", source_html)
        self.assertIn("Tiny preview", source_html)
        self.assertIn("Small review", source_html)
        self.assertIn("Manual bounds", source_html)
        self.assertLess(source_html.index("tiny-preview"), source_html.index("small-review"))
        self.assertLess(source_html.index("small-review"), source_html.index("manual-bounds"))

    def test_first_run_render_focuses_on_one_next_step(self) -> None:
        html = render_home({"status_ok": False, "readiness_blockers": ["operator-not-run"]})
        self.assertEqual(html.count("data-primary-next"), 1)
        self.assertIn(">Check setup<", html)
        self.assertIn('class="metrics" aria-label="Readiness summary" hidden', html)
        self.assertIn('id="review" class="reports" aria-label="Generated reports" hidden', html)
        self.assertIn("Operator board (optional)", html)
        self.assertIn("Reports appear after the guided run", html)

    def test_ready_render_keeps_open_reports_as_primary_next_step(self) -> None:
        html = render_home(
            {
                "operator_wizard": {
                    "active_step": "review",
                    "active_label": "Review",
                    "next_action": "dashboard",
                    "next_action_type": "report",
                    "next_action_label": "Open review reports",
                    "mode": "ready",
                    "mode_label": "Review ready",
                    "steps": [
                        {"step_id": "review", "label": "Review", "status": "ready", "level": "ok", "decision": "review-ready"}
                    ],
                }
            }
        )
        self.assertEqual(html.count("data-primary-next"), 1)
        self.assertIn('data-primary-next href="/report/dashboard"', html)
        self.assertNotIn('aria-label="Readiness summary" hidden', html)
        self.assertNotIn('aria-label="Generated reports" hidden', html)

    def test_render_home_escapes_status_values(self) -> None:
        html = render_home(
            {
                "decision": "<script>alert(1)</script>",
                "status_ok": False,
                "readiness_stage": "<b>blocked</b>",
                "readiness_blockers": ["<img src=x>"],
                "operator_next_step": "<script>bad()</script>",
                "operator_tasks": [
                    {
                        "label": "<b>Unsafe label</b>",
                        "status": "<script>bad()</script>",
                        "action": "<img src=x>",
                    }
                ],
            }
        )
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn("<b>blocked</b>", html)
        self.assertNotIn("<img src=x>", html)
        self.assertIn("&lt;script&gt;bad()&lt;/script&gt;", html)

    def test_render_home_keeps_reports_on_allowed_routes(self) -> None:
        html = render_home({"status_ok": False, "readiness_blockers": ["operator-not-run"]})
        for key in ("setup", "operator", "dashboard", "summary"):
            self.assertIn(f'href="/report/{key}"', html)
        self.assertNotIn("http://", html.lower())
        without_allowed_github = html.replace(GITHUB_REPO_URL, "")
        self.assertNotIn("https://", without_allowed_github.lower())
        self.assertNotIn("telemetry", html.lower())
        self.assertNotIn("hosted mode", html.lower())

    def test_failed_operator_task_renders_blocked_lane(self) -> None:
        html = render_home(
            {
                "status_ok": False,
                "readiness_blockers": ["release-gate-failed"],
                "operator_tasks": [
                    {"label": "Run release gate", "status": "failed", "action": "Inspect release_check.json"}
                ],
            }
        )
        self.assertIn('class="decision bad"', html)
        self.assertIn("Blocked", html)
        self.assertIn("Run release gate", html)
        self.assertIn("Inspect release_check.json", html)

    def test_render_home_uses_ascii_visible_copy(self) -> None:
        html = render_home({"status_ok": False, "readiness_blockers": ["operator-not-run"]})
        self.assertIn("Runs locally - no upload", html)
        self.assertIn("&#9680; Theme", html)
        self.assertNotIn("Â", html)
        self.assertNotIn("�", html)

    def test_read_status_before_operator_run_is_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = read_status(root)
            self.assertEqual(payload["protocol_version"], OPERATOR_SERVER_PROTOCOL_VERSION)
            self.assertEqual(payload["app_version"], "unknown")
            self.assertTrue(payload["suggested_workspace"].endswith("scroll-review-workspace"))
            self.assertEqual(payload["decision"], "operator-not-run")
            self.assertFalse(payload["status_ok"])
            self.assertEqual(payload["claim_status"], "no-claim")
            self.assertFalse(payload["public_claim_allowed"])
            self.assertFalse(payload["target_inference_allowed"])
            self.assertEqual(payload["server_scope"], "127.0.0.1-only")
            self.assertEqual(payload["operator_wizard"]["active_step"], "setup")
            self.assertEqual(payload["operator_wizard"]["next_action"], "run-setup")
            self.assertEqual(payload["operator_wizard"]["mode"], "fresh")
            self.assertEqual(payload["operator_wizard"]["mode_label"], "First run")
            self.assertEqual(payload["operator_wizard"]["steps"][0]["label"], "Setup")
            selected = payload["selected_data_summary"]
            self.assertEqual(selected["source"], "public-demo")
            self.assertEqual(selected["source_label"], "Built-in public demo chunk")
            self.assertEqual(selected["scan"], "synthetic-public-scroll")
            self.assertEqual(selected["preset"], "tiny-preview")
            self.assertEqual(selected["workspace_label"], "local-workspace-selected")
            self.assertIn("No OCR", selected["not_performed"])

    def test_read_status_selected_data_summary_is_dashboard_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            private_workspace = str(root / "private-operator-workspace")
            (out / "chunk_download_plan.json").write_text(
                json.dumps(
                    _step_payload(
                        "chunk-download-plan-ready",
                        "chunk-download-plan-v1",
                        selection_rationale={
                            "source_label": "Built-in public demo chunk",
                            "scan": "synthetic-public-scroll",
                            "preset": "small-review",
                            "preset_label": "Small review",
                            "estimated_bytes": 65536,
                            "workspace_label": "local-workspace-selected",
                            "workspace_path": private_workspace,
                            "why_this_source": "Small public fixture with bounded size.",
                            "what_you_get": "A checksummed local chunk and no-claim summaries.",
                        },
                        plan={"workspace": private_workspace},
                    )
                ),
                encoding="utf-8",
            )
            payload = read_status(root)
            selected = payload["selected_data_summary"]
            self.assertEqual(selected["preset"], "small-review")
            self.assertEqual(selected["preset_label"], "Small review")
            self.assertEqual(selected["estimated_bytes"], 65536)
            self.assertEqual(selected["workspace_label"], "local-workspace-selected")
            self.assertNotIn(private_workspace, json.dumps(selected))

    def test_read_status_loads_generated_operator_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            (out / "local_operator.json").write_text(
                json.dumps(
                    {
                        "decision": "local-operator-ready",
                        "status_ok": True,
                        "readiness_stage": "operator-ready",
                        "readiness_blockers": [],
                        "operator_tasks": [{"task_id": "setup", "status": "done"}],
                    }
                ),
                encoding="utf-8",
            )
            payload = read_status(root)
            self.assertEqual(payload["decision"], "local-operator-ready")
            self.assertTrue(payload["status_ok"])
            self.assertEqual(payload["operator_tasks"][0]["task_id"], "setup")
            self.assertEqual(payload["operator_wizard"]["active_step"], "setup")
            self.assertNotIn("demo/out/dashboard.html", payload["operator_wizard"]["outputs"])
            self.assertEqual(payload["operator_wizard"]["mode"], "fresh")

    def test_wizard_uses_single_step_actions_after_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            workspace = root.parent / "operator-workspace"
            (out / "operator_doctor.json").write_text(
                json.dumps(_step_payload("operator-doctor-ready", "local-operator-doctor-v1")),
                encoding="utf-8",
            )
            (out / "local_data_workspace.json").write_text(
                json.dumps(
                    _step_payload(
                        "local-data-workspace-ready",
                        "local-data-workspace-v1",
                        workspace_path=str(workspace),
                    )
                ),
                encoding="utf-8",
            )

            payload = read_status(root)
            wizard = payload["operator_wizard"]
            self.assertEqual(payload["workspace_input_value"], str(workspace))
            self.assertEqual(wizard["active_step"], "source")
            self.assertEqual(wizard["next_action"], "source-catalog")
            self.assertEqual(wizard["next_action_label"], "Check public catalog")

            (out / "source_catalog.json").write_text(
                json.dumps(_step_payload("data-source-catalog-ready", "data-source-catalog-v1")),
                encoding="utf-8",
            )
            wizard = read_status(root)["operator_wizard"]
            self.assertEqual(wizard["active_step"], "plan")
            self.assertEqual(wizard["next_action"], "plan-chunk")
            self.assertEqual(wizard["next_action_label"], "Create chunk plan")

            (out / "chunk_download_plan.json").write_text(
                json.dumps(_step_payload("chunk-download-plan-ready", "chunk-download-plan-v1")),
                encoding="utf-8",
            )
            wizard = read_status(root)["operator_wizard"]
            self.assertEqual(wizard["active_step"], "fetch")
            self.assertEqual(wizard["next_action"], "fetch-chunk")
            self.assertEqual(wizard["next_action_label"], "Save chunk locally")

            (out / "chunk_fetch_status.json").write_text(
                json.dumps(_step_payload("chunk-fetch-ready", "chunk-fetch-status-v1")),
                encoding="utf-8",
            )
            wizard = read_status(root)["operator_wizard"]
            self.assertEqual(wizard["active_step"], "readiness")
            self.assertEqual(wizard["next_action"], "scan-readiness")
            self.assertEqual(wizard["next_action_label"], "Create readiness summary")

    def test_render_home_prefills_workspace_and_selected_data(self) -> None:
        workspace = r"C:\ScrollReviewData"
        html = render_home(
            {
                "workspace_input_value": workspace,
                "operator_wizard": {
                    "active_step": "plan",
                    "active_label": "Limit chunk",
                    "active_description": "Limit the selection to a small public chunk.",
                    "next_action": "plan-chunk",
                    "next_action_type": "source-action",
                    "next_action_label": "Create chunk plan",
                    "mode": "in-progress",
                    "mode_label": "3/6 steps ready",
                    "steps": [{"step_id": "plan", "label": "Limit chunk", "status": "waiting", "level": "warn", "decision": "not run"}],
                },
                "selected_data_summary": {
                    "source": "public-demo",
                    "source_label": "Built-in public demo chunk",
                    "scan": "synthetic-public-scroll",
                    "preset": "small-review",
                    "preset_label": "Small review",
                    "estimated_bytes": 131072,
                    "workspace_label": "local-workspace-selected",
                    "why_this_choice": "Small public fixture with bounded size.",
                    "what_you_get": "A bounded chunk.",
                    "not_performed": "No OCR, no transcription, no reading, no inference, no title claim, and no public claim.",
                },
            }
        )
        self.assertIn('data-primary-next data-source-action="plan-chunk"', html)
        self.assertIn("Create chunk plan", html)
        self.assertIn('value="C:\\ScrollReviewData"', html)
        self.assertIn('<option value="small-review" selected data-label="Small review"', html)
        self.assertIn("128 KB", html)
        self.assertIn("updateSelectionPreview()", html)
        self.assertIn("selection-source-summary", html)
        self.assertIn("selection-source-status", html)
        self.assertIn("What happens", html)
        self.assertIn("Output files", html)

    def test_render_home_marks_public_adapter_as_setup_needed(self) -> None:
        html = render_home(
            {
                "operator_wizard": {
                    "active_step": "plan",
                    "active_label": "Limit chunk",
                    "active_description": "Limit the selection to a small public chunk.",
                    "next_action": "plan-chunk",
                    "next_action_type": "source-action",
                    "next_action_label": "Create chunk plan",
                    "mode": "in-progress",
                    "mode_label": "3/6 steps ready",
                    "steps": [{"step_id": "plan", "label": "Limit chunk", "status": "waiting", "level": "warn", "decision": "not run"}],
                },
                "selected_data_summary": {
                    "source": "vesuvius-public",
                    "source_label": "Vesuvius public adapter",
                    "scan": "catalog-from-adapter",
                    "preset": "tiny-preview",
                    "preset_label": "Tiny preview",
                    "estimated_bytes": 16384,
                    "workspace_label": "local-workspace-selected",
                    "why_this_choice": "Adapter-backed public catalog entry.",
                    "what_you_get": "A public adapter-backed catalog entry.",
                    "not_performed": "No OCR, no transcription, no reading, no inference, no title claim, and no public claim.",
                },
            }
        )
        self.assertIn("Vesuvius public adapter - Setup needed", html)
        self.assertIn("Optional public adapter is not installed", html)
        self.assertIn("credentials not needed", html)
        self.assertIn("full volumes blocked", html)
        self.assertIn("data-adapter-available=\"false\"", html)

    def test_read_status_wizard_moves_to_workspace_after_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            (out / "operator_doctor.json").write_text(
                json.dumps(_step_payload("operator-doctor-ready", "local-operator-doctor-v1")),
                encoding="utf-8",
            )
            payload = read_status(root)
            wizard = payload["operator_wizard"]
            self.assertEqual(wizard["active_step"], "workspace")
            self.assertEqual(wizard["next_action"], "check-workspace")
            self.assertEqual(wizard["next_action_label"], "Check workspace")
            self.assertEqual(wizard["mode"], "in-progress")
            self.assertEqual(wizard["mode_label"], "1/6 steps ready")

    def test_read_status_wizard_explains_blocked_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            (out / "operator_doctor.json").write_text(
                json.dumps(_step_payload("operator-doctor-ready", "local-operator-doctor-v1")),
                encoding="utf-8",
            )
            (out / "local_data_workspace.json").write_text(
                json.dumps(
                    _step_payload(
                        "local-data-workspace-blocked",
                        "local-data-workspace-v1",
                        status_ok=False,
                        violations=["workspace-inside-repo"],
                    )
                ),
                encoding="utf-8",
            )
            wizard = read_status(root)["operator_wizard"]
            self.assertEqual(wizard["active_step"], "workspace")
            self.assertIn("inside this repository", wizard["steps"][1]["help"])
            self.assertIn("raw chunks are not tracked", wizard["blockers"][0])

    def test_read_status_wizard_explains_catalog_and_fetch_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            (out / "operator_doctor.json").write_text(
                json.dumps(_step_payload("operator-doctor-ready", "local-operator-doctor-v1")),
                encoding="utf-8",
            )
            (out / "local_data_workspace.json").write_text(
                json.dumps(_step_payload("local-data-workspace-ready", "local-data-workspace-v1")),
                encoding="utf-8",
            )
            (out / "source_catalog.json").write_text(
                json.dumps(_step_payload("data-source-catalog-ready", "data-source-catalog-v1")),
                encoding="utf-8",
            )
            (out / "chunk_download_plan.json").write_text(
                json.dumps(
                    _step_payload(
                        "chunk-download-plan-blocked",
                        "chunk-download-plan-v1",
                        status_ok=False,
                        violations=["adapter-unavailable", "scan-not-in-public-catalog"],
                    )
                ),
                encoding="utf-8",
            )
            wizard = read_status(root)["operator_wizard"]
            self.assertEqual(wizard["active_step"], "plan")
            self.assertIn("optional public adapter", wizard["steps"][3]["help"])

    def test_read_status_wizard_reports_ready_review_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            decisions = {
                "operator_doctor.json": ("operator-doctor-ready", "local-operator-doctor-v1"),
                "local_data_workspace.json": ("local-data-workspace-ready", "local-data-workspace-v1"),
                "source_catalog.json": ("data-source-catalog-ready", "data-source-catalog-v1"),
                "chunk_download_plan.json": ("chunk-download-plan-ready", "chunk-download-plan-v1"),
                "chunk_fetch_status.json": ("chunk-fetch-ready", "chunk-fetch-status-v1"),
                "scan_data_readiness.json": ("scan-data-ready-no-claim", "scan-data-readiness-v1"),
            }
            for name, (decision, protocol) in decisions.items():
                (out / name).write_text(json.dumps(_step_payload(decision, protocol)), encoding="utf-8")
            (out / "local_operator.json").write_text(
                json.dumps(
                    {
                        "decision": "local-operator-ready",
                        "status_ok": True,
                        "readiness_stage": "operator-ready",
                        "readiness_blockers": [],
                    }
                ),
                encoding="utf-8",
            )
            wizard = read_status(root)["operator_wizard"]
            self.assertEqual(wizard["active_step"], "review")
            self.assertEqual(wizard["next_action"], "dashboard")
            self.assertEqual(wizard["mode"], "ready")
            self.assertIn("demo/out/dashboard.html", wizard["outputs"])

    def test_read_status_wizard_blocks_unsafe_ready_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "demo/out"
            out.mkdir(parents=True)
            (out / "operator_doctor.json").write_text(
                json.dumps(
                    _step_payload(
                        "operator-doctor-ready",
                        "local-operator-doctor-v1",
                        **{"public_" + "claim_allowed": True},
                    )
                ),
                encoding="utf-8",
            )
            (out / "local_operator.json").write_text(
                json.dumps({"decision": "local-operator-ready", "status_ok": True, "readiness_blockers": []}),
                encoding="utf-8",
            )

            wizard = read_status(root)["operator_wizard"]

            self.assertEqual(wizard["active_step"], "setup")
            self.assertEqual(wizard["steps"][0]["status"], "blocked")
            self.assertIn("no-claim boundary", wizard["steps"][0]["help"])

    def test_allowed_reports_are_generated_outputs_only(self) -> None:
        for rel in ALLOWED_REPORTS.values():
            self.assertTrue(rel.startswith("demo/out/"))
            self.assertNotIn("..", rel)

    def test_guided_chunk_flow_runs_safe_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp, tempfile.TemporaryDirectory() as workspace_tmp:
            root = Path(repo_tmp)
            (root / "demo/out").mkdir(parents=True)
            result = run_guided_chunk_flow(
                root,
                workspace_tmp,
                "public-demo",
                "synthetic-public-scroll",
                "tiny-preview",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["decision"], "guided-chunk-flow-ready")
            self.assertIn("Chunk stored", result["next_step"])
            self.assertTrue(any(str(item).endswith("scan_data_readiness.json") for item in result["generated_outputs"]))
            self.assertIn("Chunk stored locally", result["operator_result_summary"])
            self.assertFalse(result["public_claim_allowed"])
            self.assertFalse(result["target_inference_allowed"])
            self.assertTrue((root / "demo/out/scan_data_readiness.json").exists())
            self.assertTrue((Path(workspace_tmp) / "chunks/public-demo/synthetic-public-scroll/tiny-preview/chunk.bin").exists())

    def test_guided_chunk_flow_requires_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            root = Path(repo_tmp)
            (root / "demo/out").mkdir(parents=True)
            result = run_guided_chunk_flow(root, "", "public-demo", "synthetic-public-scroll", "tiny-preview")
            self.assertFalse(result["ok"])
            self.assertEqual(result["decision"], "guided-chunk-flow-blocked")
            self.assertEqual(result["steps"][0]["decision"], "workspace-required")

    def test_local_server_rejects_nonlocal_or_nonce_missing_actions(self) -> None:
        handler = _FakeHandler({"Host": "evil.example", "X-Scroll-Review-Action": local_server.LOCAL_ACTION_NONCE})
        self.assertFalse(local_server._host_allowed(handler))
        allowed, error, status = local_server._local_action_allowed(handler)
        self.assertFalse(allowed)
        self.assertEqual(error, "local-host-required")
        self.assertEqual(status, 403)

        handler = _FakeHandler({"Host": "127.0.0.1:8765", "Origin": "http://evil.example"})
        self.assertTrue(local_server._host_allowed(handler))
        allowed, error, status = local_server._local_action_allowed(handler)
        self.assertFalse(allowed)
        self.assertEqual(error, "local-origin-required")
        self.assertEqual(status, 403)

        handler = _FakeHandler({"Host": "127.0.0.1:8765"})
        allowed, error, status = local_server._local_action_allowed(handler)
        self.assertFalse(allowed)
        self.assertEqual(error, "local-action-nonce-required")
        self.assertEqual(status, 403)
        self.assertNotIn("workspace", ALLOWED_REPORTS)
        self.assertNotIn("chunk-plan", ALLOWED_REPORTS)

    def test_local_server_reads_only_small_json_objects(self) -> None:
        payload, error, status = local_server._read_json_payload(
            _FakeHandler({"Content-Length": "2", "Content-Type": "application/json"}, b"[]")
        )
        self.assertIsNone(payload)
        self.assertEqual(error, "json-object-required")
        self.assertEqual(status, 400)

        payload, error, status = local_server._read_json_payload(
            _FakeHandler({"Content-Length": "7", "Content-Type": "text/plain"}, b'{"a":1}')
        )
        self.assertIsNone(payload)
        self.assertEqual(error, "json-body-required")
        self.assertEqual(status, 415)

        oversized = b"{" + b'"a":' + b'"x"' * local_server.MAX_POST_BYTES + b"}"
        payload, error, status = local_server._read_json_payload(
            _FakeHandler(
                {"Content-Length": str(len(oversized)), "Content-Type": "application/json"},
                oversized,
            )
        )
        self.assertIsNone(payload)
        self.assertEqual(error, "request-body-too-large")
        self.assertEqual(status, 413)


class _FakeHandler:
    def __init__(self, headers: dict[str, str], body: bytes = b"") -> None:
        message = Message()
        for key, value in headers.items():
            message[key] = value
        self.headers = message
        self.rfile = io.BytesIO(body)
        self.server = SimpleNamespace(server_address=("127.0.0.1", 8765))


if __name__ == "__main__":
    unittest.main()
