# Continuation Guide

This file is for future chats or agents continuing the public
`scroll-review-tooling` repository.

## Current Baseline

- `master` includes the v0.6 local dashboard toolkit.
- `codex/v0.7-operator-flow` adds the static operator page and local
  one-click launcher line.
- v0.8 usability work adds a local setup doctor and explicit operator task
  list over the same no-claim JSON contracts.
- v0.9 usability work adds `START_HERE.cmd` and `START_HERE.md` as the
  beginner-facing local entry point.
- Package version: `0.6.0`.
- Core scope: public-safe no-claim review readiness, synthetic demo manifests,
  local dashboard, release audit, leak scan, and generated reports.
- Current next line: local operator usability, not research inference.

## Start Here

Run these checks before editing:

```bash
git status --short --branch
python -m unittest discover -s tests
python scripts/operator_doctor.py
python scripts/check_release.py --out-json demo/out/release_check.json --out-md demo/out/release_check.md
python -m scroll_review_tooling.release_audit --root . --out-json demo/out/release_audit.json
```

Then inspect:

- `README.md`
- `docs/LOCAL_OPERATOR_GUIDE.md`
- `docs/MANIFESTS.md`
- `docs/OPERATOR_APP_ROADMAP.md`
- `OPEN_LOCAL_OPERATOR.cmd`
- `CHECK_LOCAL_SETUP.cmd`
- `START_HERE.cmd`
- `START_HERE.md`
- `RUN_LOCAL_OPERATOR.cmd`
- `START_REVIEW_SESSION.cmd`
- `scripts/local_dashboard.py`
- `scripts/local_operator.py`
- `scripts/operator_doctor.py`
- `scroll_review_tooling/reports.py`
- `scroll_review_tooling/operator_app.py`
- `scroll_review_tooling/operator_doctor.py`
- `tests/test_output_contracts.py`

## Guardrails

- No OCR, no transcription, no reading, no public claim.
- Do not add OCR, transcription, reading, title, prize, or public-claim logic.
- Do not add private data, raw scan data, model artifacts, local absolute paths,
  collaboration exports, candidate coordinates, tokens, or private strategy.
- Keep demo data synthetic and generated outputs under `demo/out/`.
- Keep public outputs no-claim with `public_claim_allowed: false` and
  `target_inference_allowed: false`.
- Keep local operator surfaces self-contained: no scripts, no external assets,
  no network calls, and no upload path.
- Local relative links between generated files are allowed; external links are
  not allowed in generated operator/dashboard HTML.

## Recommended Branches

- `codex/v0.6.1-release-hardening` for small docs, audit, and test fixes.
- `codex/v0.7-operator-flow` for operator usability work.
- `codex/v0.7-manifest-contracts` for protocol/schema changes.

## Next Useful Work

- Make `demo/out/operator.html` clearer when sessions are blocked.
- Keep `demo/out/operator_doctor.html` as the first-stop setup report for
  normal local operators.
- Keep `START_HERE.cmd` as the obvious Windows first click while it remains a
  thin wrapper over the setup doctor and operator launcher.
- Keep `operator_tasks` stable so future UI layers can render the same flow.
- Preserve `demo/out/operator_summary.md` as the short no-claim share handoff.
- Keep `operator_guidance` current as blocked states become more specific.
- Preserve `sessions/` as ignored generated local output.
- Add a local workspace selector later, but only for session manifests.
- Add output-folder summaries so non-experts know what to share and why.
- Add screenshot-based review of the operator page before any public release.
- Consider a ZIP or one-command Windows bundle only after the operator contract
  has stable tests and release-audit coverage.
