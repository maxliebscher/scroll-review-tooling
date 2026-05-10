# Operator App Roadmap

The operator app line is a local usability layer over the no-claim review
toolkit. It should help a non-expert understand what to run, what is blocked,
and which controlled private next step is supported by existing summaries.

It is not a scroll reader, model runner, evidence finder, public claim system,
or submission generator.

## Current Direction

- Keep the CLI and JSON contracts as the stable core.
- Add a local operator start page for first-run explanation and step guidance.
- Keep generated HTML self-contained: no scripts, no external assets, no upload,
  no telemetry, and no network calls.
- Load only session manifests and existing JSON summaries in the public demo.
- Treat real private evidence as external to this repository.

## Intended Flow

1. Start locally with `RUN_LOCAL_OPERATOR.cmd` or `python scripts/local_operator.py`.
2. Read the short operator explanation.
3. Confirm the synthetic session and release checks are ready.
4. Open `demo/out/dashboard.html` for readiness, blockers, handoff, and priority.
5. Share only generated no-claim summaries with reviewers.

## Future Work

- Improve the operator start page with clearer blocked-state guidance.
- Add a local workspace selector that accepts only session manifests.
- Add explicit output-folder summaries for generated reports.
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
