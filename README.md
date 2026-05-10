# Scroll Review Tooling

A small, reproducible review-gate toolkit for blind-first candidate
assessment. It validates reviewer responses, records second-check
decisions, and emits attention signals only when a controlled next step
is supported.

Its unique public role is review readiness: it helps teams decide whether a
candidate path is controlled, reviewable, reproducible, and claim-safe enough
for a separate private next step. It does not identify content, read source
material, or create new evidence.

The runnable demo fixture is intentionally synthetic and data-free.
A review repository may also include real example outputs under
`docs/examples/` so reviewers can see the workflow in context. Those
examples are illustrative artifacts only: no OCR, no transcription, no
reading, and no public or prize claim.

Current release-candidate line: `v0.6.0`. See `CHANGELOG.md` for the public-safe
change summary, `docs/LOCAL_OPERATOR_GUIDE.md` for the local dashboard flow,
and `docs/OPERATOR_APP_ROADMAP.md` for the noob-friendly local operator line.

## ELI5: How It Works

Think of this tool as a careful checklist and status board for scroll-review
work. It does not look at a scroll and tell you what it says. Instead, it looks
at small JSON summary files that already exist and asks: is this review package
complete, controlled, safe to discuss, and ready for the next private step?

A new user can first check whether the local setup is usable:

```bash
python scripts/operator_doctor.py
```

On Windows, double-click `CHECK_LOCAL_SETUP.cmd`. It writes
`demo/out/operator_doctor.html`, a plain setup report that says whether Python,
the required local files, the session manifest, and the generated-output folder
are ready.

Then start the local operator page:

```bash
python scripts/local_operator.py
```

On Windows, double-click `OPEN_LOCAL_OPERATOR.cmd` for the closest current
one-click flow: it runs the local checks and opens the generated operator page.
If you prefer a launcher that does not open a browser, use
`RUN_LOCAL_OPERATOR.cmd`. It writes
`demo/out/operator.html`, a plain-language start page, and
`demo/out/dashboard.html`, the detailed status board. It also writes
`demo/out/operator_summary.md`, a short no-claim share summary for reviewers or
maintainers.

You can pass a local session manifest to either Windows launcher, or drag a
session manifest onto it:

```text
OPEN_LOCAL_OPERATOR.cmd demo\session_manifest.json
```

For a local review-session folder, use the session starter:

```text
START_REVIEW_SESSION.cmd
```

You may drag JSON reviewer responses onto it. The starter writes an ignored
`sessions/...` folder with an inbox template, validation outputs, second-check
status, attention status, and `session_summary.md`. It accepts JSON review
responses only; it is not a raw-data importer.

The current operator page is static. It has local links to generated reports,
but it does not run checks from inside the browser. If a session file or JSON
summary changes, rerun the command and refresh the page.

The lower-level dashboard command remains available:

```bash
python scripts/local_dashboard.py
```

That command runs the synthetic demo checks, validates the manifests, runs the
release audit, and writes a local dashboard to `demo/out/dashboard.html`. On
Windows, double-clicking `RUN_LOCAL_DASHBOARD.cmd` runs the same local flow.

The dashboard then shows the important bits in plain language:

- whether the current bundle passed the no-claim safety checks;
- which readiness stage it reached, such as `surface-ready`,
  `preflight-ready`, `review-ready`, or `handoff-ready`;
- which blockers still need human attention;
- which controlled private next step is suggested by the existing summaries.

So the tool is not a reading machine. It is the local operator layer around the
reading work: it helps a team avoid messy handoffs, missing controls, unsafe
claims, and wasted review effort before private research work continues
elsewhere.

## What It Does

- Creates a blind review response template from a bundle manifest.
- Validates reviewer responses against required acknowledgements and
  score ranges.
- Separates ambiguous review outcomes from controlled-next-step support.
- Validates public-safe review-pack, surface/VC3D, and full-volume
  preflight manifests without running inference.
- Emits no-claim review dossiers from existing workflow outputs.
- Inspects existing JSON outputs into a compact no-claim readiness summary.
- Rolls existing outputs into a public-safe evidence readiness ladder:
  `manifest-valid`, `surface-ready`, `preflight-ready`, `review-ready`, and
  `release-ready`.
- Validates review-to-reading handoff manifests for controlled private next
  steps such as surface continuity review, VC3D sheet-switch review, model
  evaluation, high-resolution rescan priority, or private review.
- Prioritizes existing readiness and handoff JSONs into a deterministic
  no-claim next-step queue.
- Checks the local setup with an operator doctor so non-experts can see whether
  Python, required files, output permissions, and session validation are ready.
- Renders a local operator start page that explains the safe steps before a
  reviewer opens the detailed dashboard. The page links only to generated local
  files.
- Renders a local static HTML dashboard from existing JSON outputs so a reviewer
  can inspect status, blockers, and priority without reading raw JSON.
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

Run the local setup doctor first if this is a new machine:

```bash
python scripts/operator_doctor.py
```

On Windows, double-click `CHECK_LOCAL_SETUP.cmd`; then run the operator entry
point:

```bash
python scripts/local_operator.py
```

On Windows, double-click `OPEN_LOCAL_OPERATOR.cmd` to run the same safe local
checks and open `demo/out/operator.html`. Use `RUN_LOCAL_OPERATOR.cmd` when you
want the command to print paths without opening a browser.
Open `demo/out/operator.html` first. It explains the current status and links
to the generated dashboard, JSON summaries, and share summary. It is a static
local page, not a browser app that runs checks itself.

To use a different local session manifest:

```bash
python scripts/local_operator.py --session demo/session_manifest.json
```

To create an isolated local review-session folder:

```bash
python scripts/start_session.py --demo
```

For the lower-level dashboard flow:

```bash
python scripts/local_dashboard.py
```

On Windows, you can also double-click `RUN_LOCAL_DASHBOARD.cmd`. It runs the
same local command and then prints the dashboard path.

It runs the demo, strict inspect gate, unit tests, release audit, and internal
leak scan, writes `demo/out/release_check.json`, and confirms the local
dashboard exists. By default it uses `demo/session_manifest.json`, a synthetic
session file that lists the JSON summaries to show in the dashboard. If a check
fails, the command exits non-zero after writing the release summary.

After it passes, open `demo/out/dashboard.html` locally. The dashboard is a
static file generated from existing JSON outputs. It has no server, no upload,
no telemetry, no external assets, and no candidate-data import path.

For automation, the lower-level release gate remains available:

```bash
python scripts/check_release.py --out-json demo/out/release_check.json --out-md demo/out/release_check.md
```

Release-check summaries use the same no-claim safety fields as the manifest
validators. Each check row includes a stable `check_id`, and the summary itself
is versioned as `release-check-v1`.

Session-based dashboard rendering is also available directly:

```bash
python -m scroll_review_tooling.review_workflow dashboard --session demo/session_manifest.json
```

Individual workflow commands remain available for debugging or demos:

```bash
python -m scroll_review_tooling.review_workflow init-template --bundle demo/bundle_manifest.json --out demo/inbox/response_template.json
python -m scroll_review_tooling.review_workflow validate --template demo/inbox/response_template.json --inbox demo/inbox --out-json demo/out/review_status.json --out-tsv demo/out/review_status.tsv
python -m scroll_review_tooling.review_workflow second-check --review-status demo/out/review_status.json --out-json demo/out/second_check.json
python -m scroll_review_tooling.review_workflow attention --second-check demo/out/second_check.json --state demo/out/attention_state.json --out-json demo/out/attention.json
python -m scroll_review_tooling.release_audit --root . --out-json demo/out/release_audit.json
python -m scroll_review_tooling.review_workflow validate-pack --manifest demo/review_pack_manifest.json --out-json demo/out/review_pack_status.json --out-md demo/out/review_pack_status.md
python -m scroll_review_tooling.review_workflow surface-review --manifest demo/surface_review_manifest.json --out-json demo/out/surface_review_status.json --out-md demo/out/surface_review_status.md
python -m scroll_review_tooling.review_workflow preflight-manifest --manifest demo/full_volume_preflight_manifest.json --out-json demo/out/full_volume_preflight_status.json --out-md demo/out/full_volume_preflight_status.md
python -m scroll_review_tooling.review_workflow dossier --bundle demo/bundle_manifest.json --review-status demo/out/review_status.json --second-check demo/out/second_check.json --release-audit demo/out/release_audit.json --out-json demo/out/dossier.json --out-md demo/out/dossier.md
python -m scroll_review_tooling.review_workflow handoff --manifest demo/handoff_manifest.json --out-json demo/out/handoff_status.json --out-md demo/out/handoff_status.md
python -m scroll_review_tooling.review_workflow inspect --input-json demo/out/review_status.json demo/out/review_pack_status.json demo/out/surface_review_status.json demo/out/full_volume_preflight_status.json demo/out/dossier.json --out-json demo/out/inspect_summary.json --out-md demo/out/inspect_summary.md
python -m scroll_review_tooling.review_workflow prioritize --input-json demo/out/handoff_status.json demo/out/dossier.json --out-json demo/out/path_priority.json --out-md demo/out/path_priority.md
python -m scroll_review_tooling.review_workflow dashboard --input-json demo/out/review_pack_status.json demo/out/surface_review_status.json demo/out/full_volume_preflight_status.json demo/out/dossier.json demo/out/handoff_status.json demo/out/inspect_gate.json demo/out/path_priority.json --out-html demo/out/dashboard.html
python -m unittest discover -s tests
```

For release gating, `inspect` can require every inspected JSON file with an
explicit `status_ok` field to be ready:

```bash
python -m scroll_review_tooling.review_workflow inspect --input-json demo/out/review_pack_status.json demo/out/surface_review_status.json demo/out/full_volume_preflight_status.json demo/out/dossier.json --out-json demo/out/inspect_gate.json --out-md demo/out/inspect_gate.md --require-status-ok
```

This mode only summarizes existing outputs. It does not run inference or create
new evidence.

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

This repository is suitable for reviewing the tooling pattern.
It is not the full research workspace and intentionally excludes
research data, private notes, collaboration exports, local caches,
models, and generated candidate outputs.









<!-- REAL_OUTPUT_EXAMPLES_START -->
## Real Output Examples

The images below are real review-gate example artifacts. They show the
shape of materials a human reviewer might inspect: blind CT sheets,
control/model references, decision synthesis, and preflight render
context. They are not OCR, not a transcription, not a reading, and not a
public claim.

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
