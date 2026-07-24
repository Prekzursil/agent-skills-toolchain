"""2-unit real Databricks round trip: build+submit+poll+harvest+5-clause gate. Small real spend.
Units emit a >=1200-byte report so DONE is reachable."""

from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1])
)  # repo root (contains harness/)
from harness.contract import Unit, RAIL
from harness import build_batch, submit, poll, harvest


def run_cmd(argv):
    p = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    return p.returncode, p.stdout, p.stderr


DBFS = "dbfs:/tmp/fanout-smoke"
POSIX = "/dbfs/tmp/fanout-smoke"


def main():
    units = [
        Unit(
            id=f"smoke-{i}",
            lane="smoke",
            prompt=(
                f"Write a report of AT LEAST 1200 characters to {POSIX}/results/smoke-{i}.md. "
                f"It MUST contain a line 'echo: hello from smoke {i}' plus enough descriptive "
                f"prose to exceed 1200 bytes, and its FINAL line must be exactly "
                f"'UNIT-COMPLETE: smoke-{i}'. Do not stop short of 1200 bytes."
            ),
            artifact=f"{POSIX}/results/smoke-{i}.md",
        )
        for i in (0, 1)
    ]
    bp = build_batch.write_batch(
        build_batch.build_batch(units, "smoke"),
        Path(__file__).parent / "_smoke_batch.json",
    )
    for d in (DBFS, f"{DBFS}/results"):
        run_cmd(["databricks", "fs", "mkdirs", d, "--profile", RAIL["profile"]])
    run_cmd(
        [
            "databricks",
            "fs",
            "cp",
            str(bp),
            f"{DBFS}/batch.json",
            "--overwrite",
            "--profile",
            RAIL["profile"],
        ]
    )  # local->DBFS cp is fine
    pf = Path(__file__).parent / "_smoke_payload.json"
    pf.write_text(
        json.dumps(
            submit.build_payload(2, f"{POSIX}/batch.json", f"{POSIX}/results"), indent=2
        ),
        encoding="utf-8",
    )
    run_id = submit.submit(pf, run_cmd)
    assert run_id, "submit failed"
    print(f"run_id={run_id}")
    dest = Path(__file__).parent / "_smoke_results"

    def fetch(u):
        h = harvest.harvest(f"{DBFS}/results", dest, [u], run_cmd)
        p = dest / Path(u.artifact).name
        return p if (h[u.id][0] == "harvested" and p.exists()) else None

    t0 = time.time()
    while time.time() - t0 < 1800:
        rc, out, _ = run_cmd(
            ["databricks", "jobs", "get-run", str(run_id), "--profile", RAIL["profile"]]
        )
        state = "?"
        try:
            state = (json.loads(out).get("state") or {}).get("life_cycle_state", "?")
        except json.JSONDecodeError:
            pass
        if state in poll._TERMINAL:
            v = {}
            for _ in range(3):  # grace re-harvest for DBFS eventual consistency
                v = {u.id: poll.classify(state, u, fetch(u)) for u in units}
                if all(x == "DONE" for x in v.values()):
                    break
                time.sleep(20)
            if all(x == "DONE" for x in v.values()):
                print("SUCCESS:smoke 2/2 DONE")
                return 0
            print(f"FAILED:smoke {v}")
            return 1
        print(f"  {state} ...", flush=True)
        time.sleep(30)
    print("FAILED:smoke timeout")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
