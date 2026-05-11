# Local Operator Guide

This guide is for running the public-safe local app and generated reports. It
is not a candidate-data workflow. Keep real evidence bundles, private notes,
raw scans, model artifacts, and candidate-specific material outside this public
repo.

## Safe Entry Points

For the simplest Windows path, double-click `START_HERE.cmd`. It runs the setup
doctor and starts the local app on `127.0.0.1`.

0. On a new machine, double-click `CHECK_LOCAL_SETUP.cmd` if you only want the
   setup report. It writes
   `demo/out/operator_doctor.html` and tells you whether Python, required
   local files, the session manifest, and `demo/out/` are ready.
1. On Windows, double-click `RUN_LOCAL_APP.cmd` to open the interactive local
   app.
2. For report-only mode, double-click `OPEN_LOCAL_OPERATOR.cmd` to run the checks and
   open the generated operator page.
   You can also drag a local session manifest onto `OPEN_LOCAL_OPERATOR.cmd`.
3. Or run:

```bash
python scripts/operator_server.py
```

4. If you use report-only mode, open:

```text
demo/out/operator.html
```

Use `RUN_LOCAL_OPERATOR.cmd` instead of `OPEN_LOCAL_OPERATOR.cmd` when you want
the command to print paths without opening a browser. Both Windows launchers
accept an optional session manifest path.

For a fresh local review-session folder, double-click `START_REVIEW_SESSION.cmd`
or drag JSON reviewer responses onto it. It writes an ignored `sessions/...`
folder with review validation outputs and `session_summary.md`. It accepts JSON
review responses only; it is not a raw-data importer.

The local app has buttons for setup, dashboard generation, and report viewing.
The generated operator page explains the local steps, safety boundary, current
session, and where to find the detailed dashboard.

Its "Guided Flow" table is the main noob-friendly control surface: it shows
setup, session validation, release gate, dashboard, and safe sharing as
separate tasks with a status, an action, and the generated file to inspect.

It also writes `demo/out/operator_summary.md`. Share that short no-claim
summary with a reviewer or maintainer when they need the status and next-step
context without private evidence.

If something is blocked, the operator page shows a "What Needs Attention"
section with the state, plain-language meaning, and next local step.

The generated report pages are static. If you are using the local app, click
**Build dashboard** again after changing a session JSON. If you are using
report-only mode, rerun `RUN_LOCAL_OPERATOR.cmd` or
`python scripts/local_operator.py`, then refresh `demo/out/operator.html`.

The lower-level dashboard entry point remains available:

1. On Windows, double-click `RUN_LOCAL_DASHBOARD.cmd`.
2. Or run:

```bash
python scripts/local_dashboard.py --session demo/session_manifest.json
```

3. After the command passes, open:

```text
demo/out/dashboard.html
```

The dashboard is a static local file. The interactive app uses small inline
browser controls for buttons and talks only to the local server on `127.0.0.1`.
It has no upload, telemetry, external assets, or remote data flow.

## Troubleshooting

- If you are unsure where to begin, use `START_HERE.cmd`.
- If Python is missing, install Python 3.10 or newer and run
  `CHECK_LOCAL_SETUP.cmd` again.
- If the setup doctor is blocked, open `demo/out/operator_doctor.html`; it
  lists each failed local check and the next local step.
- If the operator page is blocked, inspect `demo/out/local_operator.json` and
  confirm the release check and session validation passed.
- If a reviewer asks what to inspect, start with `demo/out/operator_summary.md`
  and `demo/out/dashboard.html`.
- If the release gate fails, inspect `demo/out/release_check.json` and rerun
  `python scripts/check_release.py --out-json demo/out/release_check.json --out-md demo/out/release_check.md`.
- If the session is blocked, inspect `demo/out/local_dashboard.json` and confirm
  that `demo/session_manifest.json` references only generated JSON summaries.
- If generated files appear in `git status`, confirm `demo/out/` is ignored with
  `git status --short --branch --ignored demo/out`.

## Boundaries

The local dashboard summarizes existing JSON outputs only. It does not inspect
source imagery, execute models, read text, import private folders, or authorize
public claims.
