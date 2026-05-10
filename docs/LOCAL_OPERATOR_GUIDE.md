# Local Operator Guide

This guide is for running the public-safe local demo and dashboard. It is not a
candidate-data workflow. Keep real evidence bundles, private notes, raw scans,
model artifacts, and candidate-specific material outside this public repo.

## Safe Entry Points

1. On Windows, double-click `OPEN_LOCAL_OPERATOR.cmd` to run the checks and
   open the generated operator page.
2. Or run:

```bash
python scripts/local_operator.py
```

3. If you used the Python command or `RUN_LOCAL_OPERATOR.cmd`, open:

```text
demo/out/operator.html
```

Use `RUN_LOCAL_OPERATOR.cmd` instead of `OPEN_LOCAL_OPERATOR.cmd` when you want
the command to print paths without opening a browser.

The operator page explains the local steps, safety boundary, current session,
and where to find the detailed dashboard.

The page is static. It includes local links to generated reports, but changing
inputs does not update the browser by itself. Rerun `RUN_LOCAL_OPERATOR.cmd` or
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

The dashboard is a static local file. It has no JavaScript, no server, no
telemetry, no external assets, and no network flow. The operator page follows
the same rule; its links point only to generated local files.

## Troubleshooting

- If Python is missing, install Python 3.10 or newer and run the command again.
- If the operator page is blocked, inspect `demo/out/local_operator.json` and
  confirm the release check and session validation passed.
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
