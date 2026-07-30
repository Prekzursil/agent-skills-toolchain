"""Count MY active fan-out runs — not the workspace's.

This is a shared Bolt production workspace: `databricks jobs list-runs --active-only`
returns fraud_driver, payment_method_payments, business_payment and friends. Gating a
wave on workspace-wide idleness therefore NEVER releases, and counting workspace runs
reports someone else's production workload as our fan-out progress. Both mistakes were
made on 2026-07-26 before this existed.

Our runs are named `codex-fanout-n<N>-c<C>` by harness/submit.py:build_payload.

Prints a single integer to stdout. On any failure prints -1: the caller must treat an
unknown count as "not safe to proceed", never as zero.
"""

from __future__ import annotations

import json
import os
import subprocess

MARKER = "codex-fanout"
ACTIVE = {"PENDING", "RUNNING", "TERMINATING", "QUEUED", "BLOCKED"}


def main() -> int:
    try:
        env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
        p = subprocess.run(
            [
                "databricks",
                "jobs",
                "list-runs",
                "--active-only",
                "-o",
                "json",
                "--profile",
                "bolt-datascience",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            env=env,
        )
        if p.returncode != 0:
            print(-1)
            return 1
        data = json.loads(p.stdout or "{}")
        runs = data.get("runs", []) if isinstance(data, dict) else (data or [])
        n = 0
        for r in runs:
            if MARKER not in (r.get("run_name") or ""):
                continue
            state = (r.get("state") or {}).get("life_cycle_state", "")
            # An unrecognised state counts as active: fail closed, do not stack waves.
            if state in ACTIVE or state == "":
                n += 1
        print(n)
        return 0
    except Exception:  # noqa: BLE001 — any failure is an UNKNOWN count, not zero
        print(-1)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
