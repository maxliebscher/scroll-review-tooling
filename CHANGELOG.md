# Changelog

## Unreleased

- Added `python scripts/package_check.py` as a dry-run ZIP-readiness check. It
  inspects tracked and unignored package candidates, blocks generated outputs,
  raw scan suffixes, model/checkpoint files, and credential-like text, and does
  not create an archive.
- Clarified the desktop operator wording so advanced local data actions are
  described as bounded small-chunk steps rather than a full-volume data flow.
- Added explicit public-adapter readiness fields so source cards distinguish
  built-in demo readiness, optional adapter setup, credential requirements,
  fetch support, and full-volume blocking.

## v1.0.0 Local Interactive Operator

- Added `RUN_LOCAL_APP.cmd` and `python scripts/operator_server.py` as a local
  interactive operator on `127.0.0.1`.
- Added buttons for setup check, dashboard generation, and opening generated
  reports from one screen.
- Kept report files as shareable outputs while moving day-to-day use into the
  local app.
- Kept the same no-claim boundary: no OCR, no transcription, no reading, no
  inference, no upload, and no public or prize claim.

## v0.8.0 Local Operator Usability

- Added `START_HERE.cmd` and `START_HERE.md` as the beginner-facing local
  Windows entry point over the setup doctor and operator launcher.
- Added `CHECK_LOCAL_SETUP.cmd` and `python scripts/operator_doctor.py` so a
  local operator can verify Python, required files, session validation, and
  generated-output permissions before using the dashboard.
- Added `local-operator-doctor-v1` JSON, Markdown, and HTML outputs.
- Added `operator_tasks` to the operator JSON and Guided Flow table so setup,
  session, release, dashboard, and sharing states are visible without reading
  raw JSON.
- Kept the operator line local-only and no-claim: no OCR, no transcription, no
  reading, no inference, no network calls, and no public or prize claim.

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
