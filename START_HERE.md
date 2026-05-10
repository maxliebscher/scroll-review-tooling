# Start Here

Use this repository as a local review-readiness tool. It does not read scroll
material, run OCR, run transcription, run inference, upload data, or authorize
public or prize claims.

## Windows

Double-click:

```text
START_HERE.cmd
```

It checks the local setup, builds the static operator page, and opens
`demo/out/operator.html`.

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
python scripts/operator_doctor.py
python scripts/local_operator.py
```

Then open:

```text
demo/out/operator.html
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
