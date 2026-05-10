# Changelog

## v0.6.0 Release Candidate

- Added public-safe manifest validation for review packs, surface/VC3D review,
  full-volume preflight, and review-to-reading handoff summaries.
- Added no-claim dossier, inspect, path-priority, and local dashboard outputs.
- Added a synthetic session manifest so local operators can render the dashboard
  from a single session file.
- Added `python scripts/local_dashboard.py` and `RUN_LOCAL_DASHBOARD.cmd` as
  local-only dashboard entry points.
- Hardened release audit, leak scan, dashboard safety checks, and generated
  output hygiene.

This release candidate remains a local review-readiness toolkit. It does not
run OCR, transcription, inference, reading, hosted services, upload flows, or
public claim workflows.
