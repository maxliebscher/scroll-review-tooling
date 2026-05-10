# Operator App Roadmap

The operator app line is a local usability layer over the no-claim review
toolkit. It should help a non-expert understand what to run, what is blocked,
and which controlled private next step is supported by existing summaries.

It is not a scroll reader, model runner, evidence finder, public claim system,
or submission generator.

## Current Direction

- Keep the CLI and JSON contracts as the stable core.
- Add a local operator start page for first-run explanation and step guidance.
- Add a local launcher path where users can drag JSON reviewer
  responses only.
- Keep generated HTML self-contained: no scripts, no external assets, no upload,
  no telemetry, and no network calls.
- Allow local relative links between generated reports so non-experts can move
  from the operator page to the dashboard and JSON summaries.
- Load only session manifests and existing JSON summaries in the public demo.
- Treat real private evidence as external to this repository.

## Intended Flow

1. Start locally with `OPEN_LOCAL_OPERATOR.cmd`, `RUN_LOCAL_OPERATOR.cmd`, or
   `python scripts/local_operator.py`.
2. Optionally pass or drag in a local session manifest.
3. Read the short operator explanation and click the local dashboard link.
4. Confirm the synthetic session and release checks are ready.
5. Open `demo/out/dashboard.html` for readiness, blockers, handoff, and priority.
6. Share `demo/out/operator_summary.md` and the dashboard when reviewers need
   status and next-step context.
7. Use `START_REVIEW_SESSION.cmd` when a reviewer needs a fresh local session
   folder with isolated outputs.

## Future Work

- Keep `OPEN_LOCAL_OPERATOR.cmd` as the noob path until a packaged app exists.
- Improve the operator start page with richer blocked-state guidance.
- Add a local workspace selector later, but only for session manifests.
- Add a real one-window workflow later only after local-link navigation is
  stable and audited.
- Expand the share summary into a richer reviewer handoff only after its
  no-claim contract is stable.
- Add a private-side adapter later, outside the public demo path, for internal
  review sessions that already produce sanitized JSON summaries.
- Consider a zipped Windows bundle only after the session and operator contracts
  are stable and audited.

## Boundaries

- No OCR, transcription, reading, or inference.
- No publication, public claim, title claim, or prize workflow.
- No raw CT, model weights, checkpoints, private notes, collaboration exports,
  coordinates, secrets, or heavy generated artifacts.
- No arbitrary file serving; future private views must use manifest allowlists.
