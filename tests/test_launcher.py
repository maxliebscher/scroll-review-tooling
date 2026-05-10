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


if __name__ == "__main__":
    unittest.main()
