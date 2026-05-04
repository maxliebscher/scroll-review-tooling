# Private GitHub Push Instructions

Target repository: `github.com/maxliebscher/scroll-review-tooling`
Required visibility: private

Do not push from the main research workspace. Push only from this directory.

```bash
git init
git add .
git commit -m "Initial private review tooling release candidate"
gh repo create maxliebscher/scroll-review-tooling --private --source . --remote origin --push
```

Before pushing, re-run:

```bash
python scripts/run_demo.py
python -m unittest discover -s tests
python -m scroll_review_tooling.release_audit --root . --out-json demo/out/release_audit.json
```

Do not include `demo/out/`, `__pycache__/`, `.pytest_cache/`, private collaboration exports, CT data, model checkpoints, model outputs, secrets, or local absolute paths.


Private showcase note:
This local repository includes `docs/private_examples/` and a
`Private Real Output Examples` section in `README.md`. Keep the GitHub
repository private while these files are present. Before making the
repository public, remove that folder and section, then re-run the
demo, tests, and release audit.
