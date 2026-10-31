---
title: reframe-contract
type: note
permalink: dqverify-repo-20261013/skills/reframe-scrollshot-markdown/references/reframe-contract
---

# Reframe scrollshot integration contract

Read this reference when implementing, reviewing, automating, or verifying the
Reframe scrollshot workflow. Ordinary UI use needs only `SKILL.md`.

## Native RPC and job lifecycle

Request:

```json
{
  "method": "scrollshot.exportMarkdown",
  "params": {
    "videoId": "library-video-id",
    "title": "Optional document title",
    "language": "eng",
    "assurance": "high"
  }
}
```

`path` may replace `videoId` at the sidecar boundary. The immediate result is a
job receipt, not the artifact payload:

```json
{"jobId":"...","kind":"scrollshot.exportMarkdown"}
```

Use the existing `job.progress`, `job.done`, and `job.cancel` contracts. The
worker must check cancellation during decode, graph construction, OCR, render,
and immediately before publish. Progress is monotonic and reaches 100 only
after final artifacts have been reopened and verified.

The terminal successful result is compact:

```json
{
  "schemaVersion": "reframe.scrollshot-result/v1",
  "runId": "sha256-derived-id",
  "verdict": "RECORDED_SPAN_COMPLETE",
  "markdownPath": ".../document.md",
  "panoramaPaths": [".../panorama.png"],
  "manifestPath": ".../manifest.json",
  "reviewRequired": false,
  "warnings": []
}
```

Large diagnostics remain in the bundle.

## Reconstruction invariants

- Nodes are sharp, deduplicated frame observations with index, timestamp, crop,
  regime, pixel/file hashes, and rejection reason where applicable.
- Candidate edges cover temporal neighbors, short skips, and revisited regions.
  Each accepted edge retains raw displacement, overlap, cue measurements,
  ambiguity, cycle residual, and evidence reference.
- Solve one-dimensional document coordinates globally with robust residual
  handling and deterministic integer refinement. Timestamp order is never used
  as document order.
- Coverage is the interval union of usable placed observations. Report connected
  components, gaps, observation depth, residual bounds, and independently proven
  top/bottom anchors.
- Sticky chrome stays fixed in viewport coordinates while document content
  moves. Cursor/tooltip/animation candidates are temporal conflicts. Do not crop
  either class without a positive detector demonstrated against a negative
  control.
- Same-document boxes with incompatible stable text become semantic conflicts;
  do not median-merge or ask an LLM to invent a winner.

## Transaction and provenance

The run ID binds the source content hash, canonical options JSON, and algorithm
profile version. The source path is metadata and must not affect content identity.
Write all output below a validated sibling temporary directory, hash it, write a
canonical manifest plus detached digest, reopen and verify, then atomically
publish the directory. Error or cancellation removes only that validated temp
directory. The source stays byte-identical.

Minimum evidence files are `document.md`, panorama/tile image(s),
`manifest.json`, `manifest.sha256`, `graph.json`, `placements.json`,
`coverage.json`, `conflicts.json`, `source-map.json`, and `ocr/raw.json`.

## Required adversarial gates

Exercise both states for normal scrolling and a false overlap, duplicate frames,
reverse/oscillating scroll, recoverable and unrecoverable jumps, repeated rows,
sticky chrome present/absent, transient cursor present/absent, dynamic text
conflicts, unproven terminals, a missing middle span, viewport regime changes,
missing capabilities, corrupt/truncated media, cancellation at every stage,
Markdown/HTML injection strings, and mutations of source/options/output/manifest
bytes.

The focused Python gate must report 100% line and branch coverage for every
changed executable module. Renderer changes must appear in V8 coverage at 100%
lines, branches, functions, and statements. Coverage is necessary but not a
substitute for the real generated-H.264 mini-E2E and known-broken mutation
controls.

<!-- UNIT-COMPLETE: reframe-scrollshot-contract-20260819 -->