# PROPOSAL — CI outage canary (private-repo allocator probe)

**Status:** proposed · **Date:** 2026-09-06 · **Author:** curator session  
**Evidence:** `docs/GRIND-STATUS.md` §0 (Aug confirm + Sept re-measure); probe run
[`34029776290`](https://github.com/Prekzursil/agent-skills-toolchain/actions/runs/34029776290)
(`ci-probe-runner`, 3s, **steps=0**); public control `Reframe` still green.

## Problem

When private-repo Actions minutes are exhausted (or spending limit is unset), every
workflow on this repo fails in ~3 seconds with **steps=0**. That signature is
indistinguishable from a content failure in the PR checks UI, so agents and humans
chase red gates that never ran. The outage has now recurred after a monthly reset
(last green `2026-09-02T09:11:40Z`, break `09:28:39Z`).

## Evidence

| signal | reading |
|---|---|
| Private repo job duration | 3–5s, steps=0 across all workflows |
| Public sibling (`Reframe`) | success after private break |
| Billing API to agent token | 403 (owner-only) |
| Local mcp-audit on PR #322 HEAD | 28/28 PASS (content not the cause) |

## Plan (3 tiers)

### T0 — already landed (this session)

Minimal `.github/workflows/ci-probe-runner.yml`: one echo step, no checkout,
`workflow_dispatch` + push to the maintainer branch. A green run = allocator
recovered; steps=0 = still refused.

### T1 — scheduled canary (build after owner unblocks minutes)

- Cron every 6h on `main`: same one-step probe.
- On failure with duration &lt; 15s and steps=0, open/refresh a **single** issue
  labeled `ci-allocator-outage` (idempotent; do not spam).
- Companion script `command-center/ci/allocator_canary_classify.py` with
  both-states control: fixture run JSON with steps=0 → OUTAGE; steps≥1 failure →
  CONTENT; success → OK.

### T2 — status surface

- `docs/GRIND-STATUS.md` §0 auto-stamp from the canary (last OUTAGE/OK timestamp).
- Optional: public gist or Actions status badge that does **not** require making
  this repo public.

## Risk of NOT doing it

Every future minutes exhaustion looks like "the estate went red," burns agent
hours on false content bugs, and blocks merge attestation for all open PRs
(currently 12 + this session's #323).

## Owner decision needed

1. **Unblock now:** set a non-zero Actions spending limit (or confirm Sept private
   minutes). Without this, T1 cannot be proven in CI.
2. **Approve T1** cron canary + single sticky issue after minutes restore.
3. Do **not** make this repository public to "fix" CI.

## Reversibility

T0 probe is inert (echo only). T1 is a new workflow + classifier with both-states
tests; deleting the workflow removes the canary. No gate weakening.
