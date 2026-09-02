#!/usr/bin/env python3
"""Materialise estate workflow YAML from the AUD-0041 step inventory.

This worktree has no .github/workflows/. AUD-0041 already parsed the estate
CI into a job/step table; WFA-0052 reconstructs YAML so the adapter reads
raw YAML rather than the inventory JSON. That reconstruction is declared in
the report (not claimed to be byte-identical to the missing files).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INVENTORY = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
OUT_DIR = HERE / "fixtures" / "estate"


def _parse_uses(command: str) -> dict:
    rest = command[5:]
    if " with[" in rest:
        uses, _, tail = rest.partition(" with[")
        inner = tail[:-1] if tail.endswith("]") else tail
        with_map: dict[str, str] = {}
        # inventory truncates some with[] values; keep parseable keys
        for part in re.split(r",(?=[A-Za-z_][\w-]*=)", inner):
            if "=" in part:
                k, _, v = part.partition("=")
                with_map[k.strip()] = v.strip()
        step = {"uses": uses.strip()}
        if with_map:
            step["with"] = with_map
        return step
    return {"uses": rest.strip()}


def inventory_step_to_yaml(step: dict) -> dict:
    out: dict = {}
    if step.get("name"):
        out["name"] = step["name"]
    cmd = step.get("command") or ""
    if cmd.startswith("uses:"):
        out.update(_parse_uses(cmd))
    else:
        out["run"] = cmd
        if step.get("shell"):
            out["shell"] = step["shell"]
    if step.get("conditional_on"):
        out["if"] = step["conditional_on"]
    if step.get("continue_on_error") is True:
        out["continue-on-error"] = True
    return out


def workflow_to_doc(wf: dict) -> dict:
    jobs: dict = {}
    for job in wf.get("jobs") or []:
        jid = str(job.get("job_id") or "job")
        body: dict = {"runs-on": job.get("runs_on") or "ubuntu-latest"}
        if job.get("name"):
            body["name"] = job["name"]
        if job.get("needs"):
            body["needs"] = job["needs"]
        if job.get("job_if"):
            body["if"] = job["job_if"]
        legs = job.get("matrix_legs") or [{}]
        if len(legs) > 1 or (len(legs) == 1 and legs[0] not in ({}, None)):
            # estate inventory has only singleton empty legs; skip fake matrix
            if not (len(legs) == 1 and legs[0] in ({}, None)):
                axes: dict[str, set] = {}
                for leg in legs:
                    if isinstance(leg, dict):
                        for k, v in leg.items():
                            axes.setdefault(k, set()).add(v)
                if axes:
                    body["strategy"] = {
                        "matrix": {k: sorted(v, key=lambda x: str(x)) for k, v in axes.items()}
                    }
        body["steps"] = [inventory_step_to_yaml(s) for s in (job.get("steps") or [])]
        jobs[jid] = body
    triggers = wf.get("triggers") or ["push"]
    on: dict | list
    if isinstance(triggers, list) and triggers:
        on = {t: {} for t in triggers}
    else:
        on = ["push"]
    return {"name": wf.get("name") or "unnamed", "on": on, "jobs": jobs}


def main() -> int:
    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for wf in inv.get("workflows") or []:
        file_name = Path(str(wf.get("file") or "workflow.yml")).name
        doc = workflow_to_doc(wf)
        dest = OUT_DIR / file_name
        dest.write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120),
            encoding="utf-8",
        )
        written.append(file_name)
    print("rebuilt", len(written), "estate workflows:", ", ".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
