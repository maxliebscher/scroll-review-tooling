# Scroll Review Tooling

A small, reproducible review-gate toolkit for blind-first candidate
assessment. It validates reviewer responses, records second-check
decisions, and emits attention signals only when a controlled next step
is supported.

The runnable demo fixture is intentionally synthetic and data-free.
A review repository may also include real example outputs under
`docs/examples/` so reviewers can see the workflow in context. Those
examples are illustrative artifacts only: no OCR, no transcription, no
reading, and no public or prize claim.

## What It Does

- Creates a blind review response template from a bundle manifest.
- Validates reviewer responses against required acknowledgements and
  score ranges.
- Separates ambiguous review outcomes from controlled-next-step support.
- Runs a release audit for repository scope, secrets, heavyweight
  artifacts, and generated outputs.

## Sample Review Pack

The included images are synthetic fixtures. They show the intended
review format without carrying any real Scroll data.

![Synthetic blind review sample pack](docs/figures/demo_contact_sheet.jpg)

The workflow is deliberately conservative: a reviewer can support a
controlled next step, but the tooling does not authorize transcription,
OCR, a public claim, or a prize submission.

![Review-gate workflow](docs/figures/review_gate_workflow.png)

## Why Synthetic Images?

The synthetic demo is what makes the code path easy to test and audit.
Real example outputs can be added separately under `docs/examples/`
when the repository is being used for team review or public presentation.

If a team wants to review candidate material, keep the full evidence
bundle separate and use this repository to validate the response and
second-check workflow around that bundle.

## Interface

This release candidate is CLI-first. It does not include the internal
Scroll Autopilot GUI used during local exploration. That GUI controls
many project-specific pipelines and still contains internal workflow
assumptions, so it should be scrubbed and redesigned separately before
it is shared as a user-facing app.

## Demo

```bash
python -m scroll_review_tooling.review_workflow init-template --bundle demo/bundle_manifest.json --out demo/inbox/response_template.json
python -m scroll_review_tooling.review_workflow validate --template demo/inbox/response_template.json --inbox demo/inbox --out-json demo/out/review_status.json --out-tsv demo/out/review_status.tsv
python -m scroll_review_tooling.review_workflow second-check --review-status demo/out/review_status.json --out-json demo/out/second_check.json
python -m scroll_review_tooling.review_workflow attention --second-check demo/out/second_check.json --state demo/out/attention_state.json --out-json demo/out/attention.json
python -m scroll_review_tooling.release_audit --root . --out-json demo/out/release_audit.json
python -m unittest discover -s tests
```

Or run the same workflow with:

```bash
python scripts/run_demo.py
```

A supportive review creates an attention signal for a controlled next
internal method step. It never authorizes OCR, transcription, or a
public claim.

## Release Status

This is a review-tooling package, not a research result. Any real
ScrollPrize candidate still needs independent expert review, provenance,
scale, 3D position, reproducibility, and separate claim-safety approval.

## Repository Scope

This repository is suitable for private review of the tooling pattern.
It is not the full research workspace and intentionally excludes
research data, private notes, collaboration exports, local caches,
models, and generated candidate outputs.









<!-- REAL_OUTPUT_EXAMPLES_START -->
## Real Output Examples

The images below are real local review artifacts from the candidate
pipeline. They show what a human reviewer would inspect: blind CT
sheets, control/model references, decision synthesis, and preflight
render context. They are not OCR, not a transcription, not a reading,
and not a public claim.

The overview flow uses cropped excerpts so that the content remains
legible in GitHub's README view. The full review sheets are embedded
underneath.

![Real-output review flow](docs/examples/real_review_output_flow.jpg)

### Blind-first CT Review

![Blind control review pack](docs/examples/real_blind_control_review_pack.jpg)

### Control/Model Reference

![Control model reference](docs/examples/real_control_model_reference.jpg)

### Gate Decision Synthesis

![Decision synthesis](docs/examples/real_decision_synthesis.jpg)

### Preflight Render Context

![Preflight render example](docs/examples/real_preflight_render_example.jpg)
<!-- REAL_OUTPUT_EXAMPLES_END -->


