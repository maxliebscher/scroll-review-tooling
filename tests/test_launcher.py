from __future__ import annotations

import unittest
from pathlib import Path


class LauncherTests(unittest.TestCase):
    def test_windows_launcher_is_thin_local_wrapper(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        launcher = repo / "RUN_LOCAL_DASHBOARD.cmd"
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("python scripts\\local_dashboard.py", text)
        self.assertIn("demo\\out\\dashboard.html", text)
        self.assertNotIn("http://", text.lower())
        self.assertNotIn("https://", text.lower())
        self.assertNotIn("start ", text.lower())
        self.assertNotIn("powershell", text.lower())

    def test_windows_operator_launcher_is_thin_local_wrapper(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        launcher = repo / "RUN_LOCAL_OPERATOR.cmd"
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("python scripts\\local_operator.py", text)
        self.assertIn('--session "%~1"', text)
        self.assertIn("demo\\out\\operator.html", text)
        self.assertIn("demo\\out\\dashboard.html", text)
        self.assertNotIn("http://", text.lower())
        self.assertNotIn("https://", text.lower())
        self.assertNotIn("start ", text.lower())
        self.assertNotIn("powershell", text.lower())

    def test_windows_open_operator_launcher_only_opens_local_file(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        launcher = repo / "OPEN_LOCAL_OPERATOR.cmd"
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("call RUN_LOCAL_OPERATOR.cmd %*", text)
        self.assertIn('start "" "demo\\out\\operator.html"', text)
        self.assertNotIn("http://", text.lower())
        self.assertNotIn("https://", text.lower())
        self.assertNotIn("powershell", text.lower())

    def test_windows_setup_checker_is_local_only(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        launcher = repo / "CHECK_LOCAL_SETUP.cmd"
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("python scripts\\operator_doctor.py", text)
        self.assertIn("demo\\out\\operator_doctor.html", text)
        self.assertIn("/nopause", text)
        self.assertNotIn("http://", text.lower())
        self.assertNotIn("https://", text.lower())
        self.assertNotIn("start ", text.lower())
        self.assertNotIn("powershell", text.lower())

    def test_windows_start_here_runs_setup_then_operator(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        launcher = repo / "START_HERE.cmd"
        text = launcher.read_text(encoding="utf-8")
        self.assertIn("call CHECK_LOCAL_SETUP.cmd /nopause %START_ARGS%", text)
        self.assertIn("call OPEN_LOCAL_OPERATOR.cmd %START_ARGS%", text)
        self.assertIn("call RUN_LOCAL_OPERATOR.cmd %START_ARGS%", text)
        self.assertIn("/nopause", text)
        self.assertIn("/noopen", text)
        self.assertIn("demo\\out\\operator.html", text)
        self.assertNotIn("http://", text.lower())
        self.assertNotIn("https://", text.lower())
        self.assertNotIn("powershell", text.lower())


if __name__ == "__main__":
    unittest.main()
