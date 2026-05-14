# Start Here

Use this repository as a local review-readiness tool. It does not read scroll
material, run OCR, run transcription, run inference, upload data, or authorize
public or prize claims.

## Windows

Double-click:

```text
START_HERE.cmd
```

It checks the local setup and starts the local app at `127.0.0.1`. In the app,
use the wizard at the top of the screen:

```text
Public source -> Scan label -> Small chunk -> Local workspace -> Readiness summary -> Review report
```

That **Data Journey** panel is the plain-language picture of the flow. You are
not asking the app to read a scroll. You are choosing a small public/demo data
path, storing it safely in a local workspace, and creating a no-claim report
that says whether the path is organized enough for review.

1. **Setup** checks Python and local generated-output folders.
2. **Workspace** offers **Use suggested workspace and check**. This creates or
   verifies a local folder beside the repo, not inside it.
3. **Choose data** checks the public catalog and shows the selected source,
   scan label, preset, estimated size, and why that choice is safe.
4. **Limit chunk** creates a tiny public chunk plan.
5. **Save locally** stores only that limited chunk in your workspace.
6. **Create summary** writes a no-claim readiness summary.
7. **Review** opens the generated reports.

The middle of the wizard always shows the next button to click. The right side
explains blockers and generated output files. Raw chunk files stay in the local
workspace folder beside the repo; generated JSON/HTML/Markdown summaries stay
under `demo/out/`.

The launcher also checks that Python is available, stops with a plain message
if port `8765` is already busy, and writes a small log to
`demo/out/start_here.log`.
If the browser does not open automatically, go to:

```text
http://127.0.0.1:8765/
```

On a first run, the app intentionally shows only the explanation, active wizard
step, one primary button, and local/no-claim safety note. Reports, Queue/Kanban,
manual controls, and diagnostics are supporting areas; open them only after the
main step is clear or a blocker needs inspection.

For automated local checks that should not open a browser window:

```text
START_HERE.cmd /nopause /noopen
```

If something is blocked, open:

```text
demo/out/operator_doctor.html
demo/out/operator.html
demo/out/local_operator.json
demo/out/scan_data_readiness.md
```

## Python

```bash
python scripts/operator_server.py
```

Then open, if your browser does not open automatically:

```text
http://127.0.0.1:8765/
```

For report-only operation:

```bash
python scripts/operator_doctor.py
python scripts/local_operator.py
```

## What To Share

When the operator is ready, share only generated no-claim summaries such as:

```text
demo/out/operator_summary.md
demo/out/dashboard.html
demo/out/local_operator.json
demo/out/release_check.json
```

Keep private evidence, raw scans, model artifacts, collaboration exports,
candidate coordinates, and reading attempts outside this public repository.
