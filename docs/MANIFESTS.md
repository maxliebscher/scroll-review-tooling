# Public Manifest Guide

These manifests describe review readiness. They do not execute inference and
do not authorize OCR, transcription, reading, public claims, or prize claims.

All public demo manifests are synthetic. Real review materials should stay in a
separate evidence bundle and use this package only to validate workflow status.

Validator JSON outputs include both `violations` and `violation_categories`.
The categories are stable machine-readable buckets such as
`protocol-version`, `missing-required-field`, `manifest-shape`,
`claim-safety`, `surface-review-schema`, `preflight-execution`, and
`output-policy`.

## Readiness Ladder

The public outputs use a small evidence readiness ladder. These stages do not
create evidence; they only summarize whether existing artifacts are structured
well enough for review.

- `manifest-valid`: a review pack is structurally valid and no-claim safe.
- `surface-ready`: a surface/VC3D manifest has the expected metrics and no
  declared blocker fields.
- `preflight-ready`: a full-volume preflight manifest is specified for review
  and explicitly does not execute.
- `review-ready`: a dossier combines bundle, review status, second-check, and
  release-audit outputs into a no-claim package.
- `handoff-ready`: existing readiness files and reviewer requirements are
  packaged for a controlled private next step.
- `release-ready`: an inspect or release-check gate sees the required public
  stages and all checks pass.
- `blocked`: machine-readable `readiness_blockers` explain why the next review
  step is not ready.

In practice, this lets private research work use the public tooling as a
discipline layer: it asks whether a path is controlled, reproducible, and safe
to review next, not what the material contains.

## Review Pack

Use `validate-pack` for a compact review-bundle manifest.

Required fields:

- `review_pack_protocol_version`: must be `review-pack-v1`
- `review_type`: one of `blind_signal`, `surface_vc3d`, `full_volume_preflight`, or `claim_safety`
- `scroll_id`, `segment_id`, `coordinate_frame`
- `source_control_split` with non-empty string lists for `source` and `controls`
- `training_overlap_statement`, `render_command`, `claim_safety`
- either `scale_um_per_px` or `scale_source`

Minimal valid example:

```json
{
  "review_pack_protocol_version": "review-pack-v1",
  "review_type": "blind_signal",
  "scroll_id": "synthetic-scroll",
  "segment_id": "synthetic-segment",
  "coordinate_frame": "synthetic-local-pixels",
  "scale_um_per_px": 7.9,
  "source_control_split": {
    "source": ["D01"],
    "controls": ["D02"]
  },
  "training_overlap_statement": "Synthetic fixture only.",
  "render_command": "python scripts/run_demo.py",
  "claim_safety": "No OCR, no transcription, no reading, no public claim."
}
```

Typical invalid example:

```json
{
  "review_pack_protocol_version": "old",
  "review_type": "blind_signal",
  "source_control_split": {
    "source": "D01",
    "controls": ["D02"]
  },
  "claim_safety": "Synthetic fixture."
}
```

This produces protocol, split-shape, missing-field, scale, and claim-safety
violations.

## Surface / VC3D

Use `surface-review` when the main question is surface quality or sheet-switch
risk. The manifest must include the review-pack fields plus:

- `surface_review_protocol_version`: must be `surface-vc3d-review-v1`
- `surface_metrics`: includes `tifxyz_continuity`, `valid_coverage`,
  `neighbor_jump_p95`, and `layer_triplet_stability`
- `surface_review_fields`: includes `sheet_switch_visible`,
  `layer_continuity_blocker`, `boundary_or_crop_bias`,
  `compressed_region_risk`, and `needs_vc3d_surface_review`

Any true sheet-switch or continuity blocker produces a no-claim blocked status.

Minimal valid example:

```json
{
  "review_pack_protocol_version": "review-pack-v1",
  "surface_review_protocol_version": "surface-vc3d-review-v1",
  "review_type": "surface_vc3d",
  "scroll_id": "synthetic-scroll",
  "segment_id": "synthetic-segment",
  "coordinate_frame": "synthetic-tifxyz",
  "scale_source": "synthetic fixture",
  "source_control_split": {
    "source": ["surface-demo-source"],
    "controls": ["surface-demo-control"]
  },
  "training_overlap_statement": "Synthetic fixture only.",
  "render_command": "python scripts/run_demo.py",
  "claim_safety": "No OCR, no transcription, no reading, no public claim.",
  "surface_metrics": {
    "tifxyz_continuity": "present",
    "valid_coverage": 0.98,
    "neighbor_jump_p95": 1.2,
    "layer_triplet_stability": "stable"
  },
  "surface_review_fields": {
    "sheet_switch_visible": false,
    "layer_continuity_blocker": false,
    "boundary_or_crop_bias": false,
    "compressed_region_risk": false,
    "needs_vc3d_surface_review": false
  }
}
```

Typical invalid example:

```json
{
  "review_pack_protocol_version": "review-pack-v1",
  "surface_review_protocol_version": "surface-vc3d-review-v1",
  "review_type": "surface_vc3d",
  "surface_review_fields": {
    "sheet_switch_visible": true
  }
}
```

This produces missing-field violations and a no-claim sheet-switch blocker.

## Full-Volume Preflight

Use `preflight-manifest` to check whether a future full-volume run is specified
well enough for review. This command is preflight-only and never executes
inference. `execute: true` is a validation failure.

Required fields include `preflight_protocol_version`, `volume_id`,
`chunk_source`, `data_metadata`, `coordinate_frame`, `model_hash`,
`protocol_hash`, `control_panel`, `budget`, `output_path_policy`,
`stop_rules`, and `claim_safety`.

Minimal valid example:

```json
{
  "preflight_protocol_version": "full-volume-preflight-v1",
  "volume_id": "synthetic-volume",
  "chunk_source": "synthetic fixture",
  "data_metadata": {
    "format": "synthetic-zarr"
  },
  "coordinate_frame": "synthetic-volume-xyz",
  "model_hash": "sha256:synthetic-model-hash",
  "protocol_hash": "sha256:synthetic-protocol-hash",
  "control_panel": ["synthetic-control-01"],
  "budget": {
    "disk_mib": 64
  },
  "output_path_policy": {
    "allowlist": ["demo/out"]
  },
  "stop_rules": ["preflight-only"],
  "claim_safety": "No OCR, no transcription, no reading, no public claim.",
  "execute": false
}
```

Typical invalid example:

```json
{
  "preflight_protocol_version": "full-volume-preflight-v1",
  "volume_id": "synthetic-volume",
  "execute": true,
  "claim_safety": "Synthetic fixture."
}
```

This fails because preflight manifests cannot execute and because required
review metadata is missing.

## Dossier

Use `dossier` to combine bundle, review-status, second-check, and release-audit
outputs into a short JSON/Markdown summary. Dossiers remain no-claim summaries.

## Review-to-Reading Handoff

Use `handoff` to validate a public-safe package for a controlled private next
step. It reads existing readiness JSONs and manifest metadata only. It does not
open source imagery, run models, execute preflight manifests, or authorize any
claim.

Required fields:

- `handoff_protocol_version`: must be `review-to-reading-handoff-v1`
- `source_readiness_files`: non-empty list of existing readiness JSON files
- `next_private_step_type`: one of `surface-continuity-review`,
  `vc3d-sheet-switch-review`, `ink-model-eval`, `high-res-rescan-priority`, or
  `private-reading-review`
- `surface_risk_summary`: includes `surface_ready`, `sheet_switch_risk`, and
  `compressed_region_risk`
- `control_requirements`: includes `controls_present` and `control_count`
- `reviewer_requirements`: includes `required_review_count`
- `claim_safety`

Minimal valid example:

```json
{
  "handoff_protocol_version": "review-to-reading-handoff-v1",
  "source_readiness_files": [
    "demo/out/review_pack_status.json",
    "demo/out/surface_review_status.json",
    "demo/out/full_volume_preflight_status.json",
    "demo/out/dossier.json"
  ],
  "next_private_step_type": "vc3d-sheet-switch-review",
  "surface_risk_summary": {
    "surface_ready": true,
    "sheet_switch_risk": false,
    "compressed_region_risk": false
  },
  "control_requirements": {
    "controls_present": true,
    "control_count": 1
  },
  "reviewer_requirements": {
    "required_review_count": 1,
    "reviewer_summary": "Synthetic reviewer handoff."
  },
  "claim_safety": "No OCR, no transcription, no reading, no public claim."
}
```

Typical invalid example:

```json
{
  "handoff_protocol_version": "review-to-reading-handoff-v1",
  "source_readiness_files": ["demo/out/surface_review_status.json"],
  "next_private_step_type": "vc3d-sheet-switch-review",
  "surface_risk_summary": {
    "surface_ready": false,
    "sheet_switch_risk": true,
    "compressed_region_risk": false
  },
  "control_requirements": {
    "controls_present": false,
    "control_count": 0
  },
  "reviewer_requirements": {
    "required_review_count": 1
  },
  "claim_safety": "No OCR, no transcription, no reading, no public claim."
}
```

This produces no-claim blockers such as `missing-controls`,
`surface-readiness`, `missing-preflight`, or `review-insufficient`.

## Inspect

Use `inspect` to summarize existing JSON outputs without producing new research
evidence. It reports decisions, `status_ok`, violation counts, blocker counts,
readiness stages, readiness blockers, and claim-safety flags. It does not read
source imagery, run models, or execute preflight manifests.

Add `--require-status-ok` when using `inspect` as a release gate. In that mode,
any inspected file with `status_ok: false` produces
`inspect-summary-blocked-no-claim` and a non-zero CLI exit. Missing `status_ok`
remains allowed for older workflow outputs that predate the manifest validators.
Inspect summaries also roll up `violation_categories`, `blockers`,
`readiness_stages`, and `readiness_blockers` from the input files so CI and
reviewers can see the reason for a blocked no-claim status without parsing
individual validator outputs. When the inspected files include valid review
pack, surface, preflight, and dossier stages, the gated inspect summary reports
`release-ready-no-claim`.

When a valid handoff output is included, inspect reports `handoff-ready-no-claim`
and `readiness_stage: handoff-ready`.

## Prioritize

Use `prioritize` to rank existing readiness or handoff JSON files into a
deterministic no-claim next-step queue. Ready handoffs sort first, then files
with fewer blockers, then files with explicit surface and control readiness.

The output uses `path-priority-v1` and decisions
`path-priority-ready-no-claim`, `path-priority-blocked-no-claim`, or
`path-priority-risk-detected`. It does not produce new evidence and does not
perform inference.

## Dashboard

Use `dashboard` to render existing JSON outputs into one local static HTML file:

```bash
python -m scroll_review_tooling.review_workflow dashboard --session demo/session_manifest.json
```

The dashboard is display-only. It reads JSON summaries, escapes their display
values, and writes a self-contained HTML report with readiness stages, blockers,
safety flags, handoff status, and priority rows. It has no JavaScript, no
external assets, no network calls, no server mode, no upload flow, and no
private data importer.

The output uses `local-dashboard-html-v1` internally and reports decisions such
as `dashboard-handoff-ready-no-claim`, `dashboard-release-ready-no-claim`,
`dashboard-blocked-no-claim`, or `dashboard-risk-detected`.

## Local Session Manifest

Use a session manifest to name a local dashboard session and list the JSON
summaries it should display. A session file is a workflow wrapper, not an
evidence importer.

Minimal valid example:

```json
{
  "session_protocol_version": "local-review-session-v1",
  "session_name": "Synthetic local dashboard session",
  "dashboard_inputs": [
    "demo/out/handoff_status.json",
    "demo/out/path_priority.json"
  ],
  "dashboard_output": "demo/out/dashboard.html",
  "claim_safety": "No OCR, no transcription, no reading, no public claim."
}
```

Session validation blocks missing inputs, non-JSON inputs, external URLs,
absolute paths, candidate-like fields, private-path fields, unsafe claim flags,
and missing no-claim language.

For the simplest local flow, run:

```bash
python scripts/local_dashboard.py --session demo/session_manifest.json
```

This wrapper runs the release gate, writes `demo/out/local_dashboard.json`, and
prints the generated `demo/out/dashboard.html` path. Its output uses
`local-dashboard-launch-v1` and remains no-claim.

On Windows, `RUN_LOCAL_DASHBOARD.cmd` is a thin double-click wrapper around the
same command. It does not launch a browser, start a server, or contact the
network.

## Release Check Output

Use `python scripts/check_release.py --out-json demo/out/release_check.json --out-md demo/out/release_check.md`
as the canonical local gate before sharing or committing. The JSON output uses
`release-check-v1`, includes the standard no-claim safety fields, reports
`readiness_stage`, and lists each check with a stable `check_id`, human label,
status, command, and return code.

The release check does not inspect source imagery, run models, execute
preflight manifests, or authorize public claims. It only runs existing public
tooling checks and summarizes their status.

## Negative Fixtures

Synthetic invalid examples live under `demo/invalid/`:

- `bad_review_pack_protocol.json`
- `bad_review_pack_split.json`
- `bad_surface_sheet_switch.json`
- `bad_preflight_execute.json`
- `bad_claim_safety.json`
- `bad_handoff_missing_controls.json`
- `bad_handoff_claim_safety.json`

They are intentionally invalid and are used by the test suite to keep common
failure modes visible.
