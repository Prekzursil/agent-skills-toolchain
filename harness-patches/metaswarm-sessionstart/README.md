# metaswarm SessionStart latency gate — fix receipt (2026-09-19)

## Symptom

Session start at any **non-metaswarm** cwd (incl. `~`) blocked ~2m20s behind
SessionStart hooks ("Fermenting… 7/8 · 1m 43s"). First user message sat queued
the whole time.

## Diagnosis (disk-verified)

Per-hook durations from the session transcript
(`~/.claude/projects/C--Users-Prekzursil/c5ee81e0-2095-40ab-8bf3-0cbc4a087c6e.jsonl`,
`attachment.type=hook_success` entries carry `durationMs`):

| Hook | Duration | Notes |
|---|---|---|
| superpowers session-start | 3.0s | fine |
| remember session-start-hook.sh | 8.6s | fine |
| local `_dispatch` sessionstart (git-hygiene, wire-check, …) | 28.8s | inside its documented 30s budget — NOT the problem |
| **metaswarm `session-start.sh`** (marketplace 0.12.0) | **140.5s** | the culprit |

All 8 SessionStart hooks start concurrently, so wall-clock = max = metaswarm.

Root cause inside `hooks/session-start.sh` (Phase 1 "BEADS dedup check"):

1. `find` over **two** plugin caches — `~/.claude/plugins/cache` **and**
   `~/.codex/plugins/cache` — matching `.claude-plugin` + `.codex-plugin`
   layouts. Measured: 24.7s + 9.5s, **529 plugin.json files** (347 + 182).
2. **One `jq` process spawn per plugin.json** (529 spawns) to read `.name`.
3. One `node` spawn for JSON escaping.

**The scan is dead work in non-metaswarm cwds**: `beads_standalone` is only
read by Phase 4's `bd prime` branch, which requires `new_project=false`
(`.metaswarm/project-profile.json` present). Phase 1 runs *before* Phase 2's
cheap `-f` check that would have skipped it.

Cold-cost split is inferred (≈200ms/spawn under the session-start 8-hook
storm back-computed from 140.5s; warm jq spawn measured 55ms); the structure
(two finds + 529 spawns + sole consumer gated on `new_project=false`) is
verified from the script text and live measurements.

## Fix

Gate Phase 1 behind the same project check Phase 2 uses — see
`session-start-latency-gate.patch` (11 added lines: comment + `if` + `fi`).
Applied to the live marketplace copy
`~/.claude/plugins/cache/metaswarm-marketplace/metaswarm/0.12.0/hooks/session-start.sh`
(marker `METASWARM-PATCH: sessionstart-latency-gate v1`).

Deliberately NOT done (regression avoidance):

- No `timeout` added to metaswarm's `hooks/hooks.json` — a 10s timeout would
  kill the hook mid-scan (~35–65s) at **real** metaswarm projects.
- Legacy npm copy `~/.claude/plugins/metaswarm/` left untouched (not loaded by
  current Claude Code; slated for `/metaswarm:migrate`, owner action).
- No `settings.json` changes; local `_dispatch` hooks unchanged.

## Verification (both states)

- **Fast path** (cwd `~`, no `.metaswarm/`): 140.5s → **0.305s**; output
  content identical to pre-patch (same two context messages).
- **Slow path** (temp dir with `.metaswarm/project-profile.json`): 64.6s,
  exit 0 — gate opens, scan + self-heal + `bd prime` all still run. No
  behavior change for real metaswarm projects.
- `bash -n` clean; output JSON parses via jq.

## Reapply after plugin updates

Plugin cache updates overwrite the patched file. Run:

```
python harness-patches/metaswarm-sessionstart/reapply.py          # live caches
python harness-patches/metaswarm-sessionstart/reapply.py --dry-run
```

Idempotent (marker check), backs up before writing, and **fails loudly**
(exit 2) if upstream moved the anchor lines — it never guesses.

## Upstream

Patch ready for a PR to dsifry/metaswarm (same fix, plus suggested
batched-`jq`/direct-path-probe improvement). NOT submitted — public fork+PR
is an outward-facing action, awaiting owner approval. Preferred upstream
shape: reorder Phase 1 after Phase 2 rather than the duplicate `-f` check.
