from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FORBIDDEN_PATH_PARTS = {
    ".venv",
    ".venv-ink",
    ".cache",
    "data/raw",
    "data/discord_exports",
    "repos",
}
IGNORED_GENERATED_PATH_PARTS = {"__pycache__", ".pytest_cache", "demo/out", ".git"}
IGNORED_GENERATED_PREFIXES = ("demo/out/", "sessions/")
FORBIDDEN_SUFFIXES = {".ckpt", ".pt", ".pth", ".safetensors", ".npy", ".tif", ".ppm"}
FORBIDDEN_TEXT_PATTERNS = [
    re.compile(r"C:\\Users\\", re.I),
    re.compile(r"data[/\\]discord_exports", re.I),
    re.compile(r"DiscordChatExporter", re.I),
    re.compile(r"PROJECT_AUDIT", re.I),
    re.compile(r"private\s+Discord\s+export", re.I),
    re.compile(r"Sources\s+checked\s*:", re.I),
    re.compile(r"Prize-Relevant\s+Hypothesis", re.I),
    re.compile(r"Most\s+Useful\s+Next\s+Work", re.I),
    re.compile(r"\bcf-[a-f0-9]{12,}\b", re.I),
    re.compile(r"public_claim_allowed[\"']?\s*[:=]\s*true", re.I),
    re.compile(r"target_inference_allowed[\"']?\s*[:=]\s*true", re.I),
    re.compile(r"\b(ink\s+found|title\s+found|letters?\s+found|reading\s+claim)\b", re.I),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|authorization|bearer)\b\s*[:=]"),
    re.compile(r"(?i)\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{20,}\b"),
]
FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"(^|/)PROJECT_AUDIT[^/]*\.md$", re.I),
    re.compile(r"(^|/)project-audit[^/]*\.md$", re.I),
]
REQUIRED_FILES = {
    "README.md",
    "CHECK_LOCAL_SETUP.cmd",
    "OPEN_LOCAL_OPERATOR.cmd",
    "RUN_LOCAL_DASHBOARD.cmd",
    "RUN_LOCAL_OPERATOR.cmd",
    "START_REVIEW_SESSION.cmd",
    "CHANGELOG.md",
    "LICENSE",
    "SECURITY.md",
    "PRIVACY.md",
    "RELEASE_CHECKLIST.md",
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
    "scripts/operator_doctor.py",
    "scripts/start_session.py",
    "scroll_review_tooling/common.py",
    "scroll_review_tooling/manifest_validation.py",
    "scroll_review_tooling/operator_doctor.py",
    "scroll_review_tooling/operator_app.py",
    "scroll_review_tooling/reports.py",
    "scroll_review_tooling/review_workflow.py",
    "scroll_review_tooling/release_audit.py",
    "scroll_review_tooling/sessions.py",
    "tests/test_check_release.py",
    "tests/test_dashboard.py",
    "tests/test_local_dashboard.py",
    "tests/test_launcher.py",
    "tests/test_operator_app.py",
    "tests/test_operator_doctor.py",
    "tests/test_output_contracts.py",
    "tests/test_public_docs.py",
    "tests/test_release_audit.py",
    "tests/test_review_workflow.py",
    "tests/test_sessions.py",
}
TEXT_SCAN_EXEMPT_FILES = {
    "scroll_review_tooling/release_audit.py",
}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def is_text(path: Path) -> bool:
    return path.suffix.lower() in {".py", ".md", ".json", ".toml", ".txt", ".yml", ".yaml"}


def is_ignored_generated(rel: str) -> bool:
    lower = rel.lower().replace("\\", "/")
    parts = set(lower.split("/"))
    if any(lower.startswith(prefix) for prefix in IGNORED_GENERATED_PREFIXES):
        return True
    return any(part in parts for part in IGNORED_GENERATED_PATH_PARTS - {"demo/out"})


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    findings: list[dict[str, Any]] = []
    files = [p for p in root.rglob("*") if p.is_file() and not is_ignored_generated(p.relative_to(root).as_posix())]
    existing = {p.relative_to(root).as_posix() for p in files}
    for required in sorted(REQUIRED_FILES - existing):
        findings.append({"severity": "blocker", "path": required, "reason": "missing-required-file"})
    for path in files:
        rel = path.relative_to(root).as_posix()
        lower = rel.lower()
        if any(pattern.search(rel) for pattern in FORBIDDEN_FILE_PATTERNS):
            findings.append({"severity": "blocker", "path": rel, "reason": "forbidden-strategic-audit-file"})
        if any(part in lower for part in FORBIDDEN_PATH_PARTS):
            findings.append({"severity": "blocker", "path": rel, "reason": "forbidden-path"})
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append({"severity": "blocker", "path": rel, "reason": "forbidden-heavy-or-raw-suffix"})
        if path.stat().st_size > 5 * 1024 * 1024:
            findings.append({"severity": "blocker", "path": rel, "reason": "file-over-5-mib"})
        if is_text(path) and path.stat().st_size < 1_000_000 and rel not in TEXT_SCAN_EXEMPT_FILES:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in FORBIDDEN_TEXT_PATTERNS:
                if pattern.search(text):
                    findings.append({"severity": "blocker", "path": rel, "reason": "forbidden-private-or-secret-pattern"})
                    break
    decision = "release-audit-pass" if not findings else "release-audit-blocked"
    return {
        "created": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "file_count": len(files),
        "finding_count": len(findings),
        "findings": findings,
        "claim_safety": "Release audit only; no OCR, no reading, no claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-json", default="demo/out/release_audit.json")
    args = parser.parse_args()
    result = audit(Path(args.root))
    write_json(Path(args.out_json), result)
    print(json.dumps(result, indent=2))
    if result["decision"] != "release-audit-pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
