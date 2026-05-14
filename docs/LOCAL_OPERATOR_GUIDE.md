# Local Operator Guide

This guide is for running the public-safe local app and generated reports. It
is not a candidate-data workflow. Keep real evidence bundles, private notes,
raw scans, model artifacts, and candidate-specific material outside this public
repo.

## Safe Entry Points

For the simplest desktop/Windows path, double-click `START_HERE.cmd`. It is the
primary noob entry point: it runs the setup doctor and starts the local app on
`127.0.0.1`.
It also checks that Python is available, warns if the default app port is
already busy, and writes a small start log to `demo/out/start_here.log`.

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

The local app is organized around the wizard at the top of the first screen:

```text
Setup -> Workspace -> Choose data -> Limit chunk -> Save locally -> Create summary -> Review
```

Above the wizard, the **Data Journey** panel explains the actual data flow:

```text
Public source -> Catalog scan label -> Small chunk preset -> Local workspace -> Readiness summary -> Review report
```

This is the key mental model. The app does not ask you to browse endless scroll
data by eye. It asks you to pick a public source, a catalog scan label, and a
small preset, then it stores that bounded chunk in your local workspace and
creates a no-claim readiness report. The UI shows why the default source is
safe, what the selected preset is for, how large the chunk is expected to be,
and what remains blocked.

Use it from left to right. The left rail shows ready, waiting, review, or
blocked status for every step. The middle panel explains the active step and
shows the next safe button to click. The inspector on the right explains
blockers in plain language and lists generated output files.

The sections below the wizard are supporting views: **Help** explains the tool
and **Reports** opens generated files. Queue and Kanban are folded into
**Operator board (optional)** so the first screen stays focused. The step log,
individual source/check/fetch buttons, and raw diagnostics are folded into
**Advanced step details and manual controls**. Most users should leave those
optional areas closed unless a step is blocked.

In first-run mode, the app keeps the main screen even smaller: explanation,
active wizard step, one primary next button, and the local/no-claim safety note.
Readiness meters and report links are hidden until generated outputs exist.

The **Choose public data** panel in the active wizard step is the guided data
path. Use it when you want the app to start from public scan data instead of
already-generated JSON summaries:

1. Click **Use suggested workspace and check**. This selects a local workspace
   beside the repo and checks write permissions.
2. Click **Check public catalog**.
3. Click **Create chunk plan**.
4. Click **Save chunk locally**.
5. Click **Create readiness summary**.
6. Open **Review reports** when the wizard reaches Review.

The compact selection panel explains which source is active, which scan label
is selected, which preset limits the chunk, the estimated size, where bytes
will be stored, and what gets generated next. The optional Vesuvius public
adapter remains visible as a yellow setup-needed source when it is unavailable;
keep the built-in public demo selected until that adapter is installed. The
catalog cards also show whether planning is allowed, whether fetching is
enabled in this public build, and that credentials and full-volume requests are
not part of the local operator flow. More detailed catalog cards stay inside
**Advanced step details and manual controls**.

Preset choice should stay simple:

- `tiny-preview`: prove that the app, workspace, storage, checksum, and reports
  work.
- `small-review`: prepare a small public chunk for controlled readiness review.
- `manual-bounds`: use only when a separate controlled workflow already chose
  bounds; this public app does not discover candidates.

The app runs the safe step and stops at the first blocker. Open
**Advanced step details and manual controls** only when you want to see exactly
which lower-level step is blocked.

This flow is intentionally small-chunk only. It blocks full-volume downloads,
private credentials, unsafe workspaces, and raw chunk storage under `demo/out/`.
Raw chunks live only in the selected workspace. Generated summaries and reports
live under ignored `demo/out/`. The generated dashboard still reads JSON
summaries only.

Its main noob-friendly control surface is the wizard. Use the readiness summary,
traffic-light colors, result panel, and optional Operator board only after the
active wizard step is clear.

Click **Info** if you need the short plain-language explanation first. It says
what the app is for, how it works, and what it will not do. The **Theme** button
switches between the default dark violet view and the light Operator Studio
view. The source-code link is intentionally separated from the main workflow in
the utility area of the left rail.

It also writes `demo/out/operator_summary.md`. Share that short no-claim
summary with a reviewer or maintainer when they need the status and next-step
context without private evidence.

If something is blocked, the optional Operator board can keep it visible instead
of hiding it behind a polished report.

The generated report pages are static. If you are using the local app, click
**Build demo dashboard** again after changing a session JSON. If you are using
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
The server also rejects non-local browser requests and requires a per-run local
action nonce for button clicks, so another site cannot silently trigger local
operator actions while the app is open.

## Packaging Direction

For now, the supported noob path is a ZIP-style folder plus Python 3.10 or
newer. The folder must include the repo files, `START_HERE.cmd`, and the demo
manifests; generated outputs stay ignored under `demo/out/`. A bundled app or
embedded Python runtime should only be considered after the wizard, operator
flow check, and release audit stay green.

Before sharing a ZIP-style folder, run:

```bash
python scripts/package_check.py --out-json demo/out/package_check.json
```

That command is a dry-run only. It checks the files that would be included and
blocks generated outputs, raw scan files, model/checkpoint files, and
credential-like text; it does not create a ZIP archive.

## Troubleshooting

- If you are unsure where to begin, use `START_HERE.cmd`.
- If Python is missing, install Python 3.10 or newer and run
  `CHECK_LOCAL_SETUP.cmd` again.
- If `START_HERE.cmd` says port `8765` is busy, close the existing local app
  window or run `python scripts/operator_server.py --port 8766`.
- If the launcher closes too quickly, inspect `demo/out/start_here.log`.
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
