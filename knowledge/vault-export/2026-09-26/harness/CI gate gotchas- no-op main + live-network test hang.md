---
title: 'CI gate gotchas: no-op main + live-network test hang'
type: guide
permalink: main/harness/ci-gate-gotchas-no-op-main-live-network-test-hang
tags:
- ci
- gotcha
- gates
- testing
- github-actions
---

# CI gate gotchas: no-op `python -m` gates + live-network test hang (2026-07-17)

**valid_as_of: 2026-07-17.** Both found on PrimariRo; both generalize.

## 1. A module run as a CI gate via `python -m X` is a NO-OP without `if __name__ == "__main__"`
It imports + exits 0, validating NOTHING. PrimariRo's `provenance_gate` + `dual_source` + `output_allowlist` were all invoked as `python -m` in ci.yml but had no `main()` → the "content-validated provenance" gate was **theater** (green CI, zero enforcement; no `data/snapshots/` on disk despite every cell citing a `snapshot_hash`). ALWAYS wire a real `main()` that walks the actual data and fails closed. A DIVERGE fan-out (fresh-context reviewer) caught this where self-review missed it — fresh-context review beats self-review on "is the gate REAL". Ties to [[Agentic repair reliability]] (done-signal is a gameable proxy).

## 2. A LIVE-network test in the fast CI unit suite HANGS the runner
`bec30.verify_remote_provenance` `urlopen`-fetches 30 sources ×2 from prezenta.roaep.ro inside a pytest; on the GitHub runner those stall to the **20-min job timeout** (fast locally = fast network). Fix: **mark live tests** (`@pytest.mark.live` + register the marker under `--strict-markers`), run the fast gate with `-m "not live"`, and run live checks as a **separate scheduled NON-blocking job**. Hermetic CI = block egress + verify against a committed snapshot store, not a live source.

## 3. GitHub Pages on a PRIVATE repo needs a paid plan (Pro+)
Works on Pro; the published site is PUBLIC regardless of repo visibility (fine when data is non-PII by design). Enable via `gh api -X POST repos/<o>/<r>/pages -f build_type=workflow`.