# Release Checklist

Use this checklist before pushing or sharing a release candidate.

- Run `python scripts/run_demo.py`.
- Run `python -m unittest discover -s tests`.
- Run `python -m scroll_review_tooling.release_audit --root . --out-json demo/out/release_audit.json`.
- Confirm the repository contains only synthetic demo data.
- Confirm there are no private collaboration exports, local absolute paths, secrets, CT files, model checkpoints, or generated model outputs.
- Confirm generated folders such as `demo/out/`, `__pycache__/`, and `.pytest_cache/` are not committed.
- Keep the first GitHub repository private until an external reviewer has checked the scope and wording.
