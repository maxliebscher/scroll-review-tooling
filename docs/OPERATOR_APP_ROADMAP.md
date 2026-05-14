# Operator App Roadmap

The operator app line is a local usability layer over the no-claim review
toolkit. It should help a non-expert understand what to run, what is blocked,
and which controlled private next step is supported by existing summaries.

It is not a scroll reader, model runner, evidence finder, public claim system,
or submission generator.

## Current Direction

- Keep the CLI and JSON contracts as the stable core.
- Start the beginner path with `START_HERE.cmd` so the user gets a local app,
  Python/port diagnostics, and a log under `demo/out/start_here.log`, not only
  a generated report.
- Use the Operator Studio layout as the current app direction: one-click start,
  readiness meters, traffic-light status, priority queue, optional Kanban, and
  generated-report links.
- Add a guided public scan-chunk path so a non-expert can choose a public
  source, small preset, and local workspace, then produce no-claim readiness
  summaries without full-volume downloads.
- Show public source cards with adapter status, suggested scan/preset, size
  limit, and reason for the starting point.
- Shape the interactive app around the current seven-step wizard:
  Setup, Workspace, Choose data, Limit chunk, Save locally, Create summary,
  and Review. Queue, Kanban, reports, and diagnostics are supporting views.
- Keep a visible Info control and dark-by-default theme toggle so first-time
  users can understand the local tool before clicking workflow actions. Keep
  the source-code link available, but visually separated from the main workflow
  navigation.
- Keep `CHECK_LOCAL_SETUP.cmd` available as a plain setup report.
- Keep generated reports as shareable outputs, not as the primary UI.
- Add a local launcher path where users can drag JSON reviewer
  responses only.
- Keep generated reports self-contained. The app may use local inline controls
  and `127.0.0.1` actions, but no upload, telemetry, external assets, or remote
  calls.
- Keep public data loading small and rights-aware: public unauthenticated
  sources only, explicit user workspace, no repo-local raw chunk storage, no
  OCR, no inference, and no claim workflow.
- Allow local relative links between generated reports so non-experts can move
  from the operator page to the dashboard and JSON summaries.
- Load only session manifests and existing JSON summaries in the public demo.
- Treat real private evidence as external to this repository.

## Intended Flow

1. On Windows, start with `START_HERE.cmd`.
2. In the local app, follow the highlighted wizard step.
3. Click **Use suggested workspace and check**, **Check public catalog**,
   **Create chunk plan**, **Save chunk locally**, **Create readiness summary**,
   then **Open review reports**.
4. Use the queue and Kanban view only after the active wizard step is clear.
5. Check local setup directly with `CHECK_LOCAL_SETUP.cmd` or
   `python scripts/operator_doctor.py`.
6. Use report-only mode with `OPEN_LOCAL_OPERATOR.cmd`, `RUN_LOCAL_OPERATOR.cmd`, or
   `python scripts/local_operator.py`.
7. Optionally pass or drag in a local session manifest for report-only workflows.
8. Confirm the setup, synthetic session, release checks, and dashboard are ready.
9. Share `demo/out/operator_summary.md` and the dashboard when reviewers need
   status and next-step context.
10. Use `START_REVIEW_SESSION.cmd` when a reviewer needs a fresh local session
   folder with isolated outputs.

## Future Work

- Keep `START_HERE.cmd` as the noob path until a packaged app exists.
- Keep the HTTP Operator flow check as the regression guard for real app
  behavior: server, nonce, setup, workspace, catalog, chunk plan, local fetch,
  readiness summary, reports, workspace marker, and chunk file.
- Preserve the setup doctor and `operator_tasks` as the contract for future UI.
- Improve the Operator Studio workspace guidance with richer blocked-state
  explanations only when they map to stable machine-readable blockers.
- Add a local workspace selector later, but only for session manifests.
- Add a real one-window workflow later only after local-link navigation is
  stable and audited.
- Expand the share summary into a richer reviewer handoff only after its
  no-claim contract is stable.
- Add a private-side adapter later, outside the public demo path, for internal
  review sessions that already produce sanitized JSON summaries.
- Consider a zipped Windows bundle only after the session and operator contracts
  are stable and audited.
- Packaging default: ZIP-style folder plus Python first; embedded runtime only
  after the local operator flow check is stable across machines.
- Use `python scripts/package_check.py --out-json demo/out/package_check.json`
  as the ZIP-readiness dry run. It inspects the package candidate set but does
  not create an archive.

## Boundaries

- No OCR, transcription, reading, or inference.
- No publication, public claim, title claim, or prize workflow.
- No raw CT, model weights, checkpoints, private notes, collaboration exports,
  coordinates, secrets, or heavy generated artifacts.
- No arbitrary file serving; future private views must use manifest allowlists.
