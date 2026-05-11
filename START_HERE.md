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
click **Check setup**, **Build dashboard**, and the report buttons.

For automated local checks that should not open a browser window:

```text
START_HERE.cmd /nopause /noopen
```

If something is blocked, open:

```text
demo/out/operator_doctor.html
demo/out/operator.html
demo/out/local_operator.json
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
