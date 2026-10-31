---
title: dbx_p1-pow-deadline
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/dbx-p1-pow-deadline
---

# P1 PoW Deadline — CRCP

## Summary

Implemented a bounded, fail-closed Sentinel proof-of-work path. PoW solving now has a monotonic wall-clock deadline, a process-wide bounded semaphore, and cooperative cancellation shared by all active worker threads. The default deadline is 25 seconds and the default process concurrency is one solve.

Configuration is available through `deadline_seconds` / `pow_deadline_seconds`, `CRCP_POW_DEADLINE_SECONDS`, and `CRCP_POW_MAX_CONCURRENT_SOLVES`. Time spent waiting for the process-wide solve slot counts against the deadline. A deadline expiry raises `TimeoutError`, stops retries, signals workers, cancels work that has not started, and waits only for running workers to observe the stop signal.

`send_message` now fails closed for both automatic Sentinel failures and manual calls with insufficient Sentinel credentials. These returns contain `ok=False`, `success=False`, and a blocker classification. No conversation POST or legacy fallback is attempted. A finalized Sentinel chat token is accepted as an alternative to the prepare-token/proof-token pair.

## Files

- `/dbfs/tmp/crcp-e2e-full/results/sentinel.py` — complete module with deadline, semaphore, cooperative cancellation, and hard-stop retry behavior.
- `/dbfs/tmp/crcp-e2e-full/results/write_path.py` — complete module with deadline forwarding and fail-closed credential checks.
- `/dbfs/tmp/crcp-e2e-full/results/p1-pow-deadline.md` — this implementation report.

## Wiring into existing modules

- Replace `crcp/sentinel.py` with the delivered `sentinel.py`.
- Replace `crcp/write_path.py` with the delivered `write_path.py`.
- Existing callers remain compatible because all new parameters are optional.
- `write_path.send_message(..., pow_deadline_seconds=N)` forwards the per-call limit to `sentinel.acquire_sentinel_tokens`, which passes it to `solve_proof_token`.
- Calls using `auto_sentinel=False` must provide either a finalized chat-requirements token or both a prepare token and proof token; otherwise they return before `post_conversation`.

## Self-tests

Executed locally against the assembled result tree using only Python stdlib:

- `py_compile` passed for both complete modules.
- Trivial solvable PoW returned a correctly prefixed proof and nonce.
- An impossible digest prefix hit the configured 30 ms wall-clock deadline and returned within the bounded cancellation allowance.
- Two concurrent solve calls observed peak process-wide solve concurrency of exactly one.
- Simulated Sentinel timeout returned `ok=False` / `sentinel_pow_failed` with zero conversation POST calls.
- `auto_sentinel=False` without credentials returned `ok=False` / `sentinel_tokens_missing` with zero conversation POST calls.

No live service calls were made and no credential material was emitted.

UNIT-COMPLETE: p1-pow-deadline