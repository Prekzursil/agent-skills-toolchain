"""BuildBackend adapter over the built harness submit/poll/harvest (CSIE-DESIGN §4). Self-contained:
submit writes the payload it submits. NOTE: the live two-tier loop (rerouting run_E through this) is
DEFERRED — this is the unit-tested contract, not yet wired into run_E (Roadmap)."""

from __future__ import annotations

import json
from pathlib import Path

from backends.base import Job
from harness import build_batch, submit
from harness.contract import RAIL, Unit


class DatabricksBuildBackend:
    def __init__(self, run_cmd, workdir: Path | None = None):
        self.run_cmd = run_cmd
        self.workdir = Path(workdir) if workdir else Path.cwd()

    def submit(self, units: list[Unit], meta: dict) -> Job:
        name = meta.get("name", "batch")
        build_batch.write_batch(
            build_batch.build_batch(units, name), self.workdir / "batch.json"
        )
        payload = submit.build_payload(
            len(units), meta.get("batch_dbfs", ""), meta.get("result_dir", "")
        )
        pf = self.workdir / "payload.json"
        pf.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        run_id = submit.submit(pf, self.run_cmd)
        return Job(
            backend="databricks",
            ref=str(run_id) if run_id else "",
            meta={"name": name, "n": len(units)},
        )

    def poll(self, job: Job) -> str:
        _, out, _ = self.run_cmd(
            ["databricks", "jobs", "get-run", job.ref, "--profile", RAIL["profile"]]
        )
        try:
            return (json.loads(out).get("state") or {}).get("life_cycle_state", "?")
        except json.JSONDecodeError:
            return "?"

    def harvest(self, job: Job, dest: Path) -> dict[str, Path]:
        return {}  # per-unit harvest stays in run_E.fetch until the live-loop refactor (Roadmap)

    def cancel(self, job: Job) -> None:
        self.run_cmd(
            ["databricks", "jobs", "cancel-run", job.ref, "--profile", RAIL["profile"]]
        )

    def teardown(self, job: Job) -> None:
        return None  # ephemeral job cluster auto-terminates
