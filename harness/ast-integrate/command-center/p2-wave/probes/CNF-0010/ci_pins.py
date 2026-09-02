"""CI-pinned formatter / linter / interpreter versions from the AUD-0041 inventory."""

from __future__ import annotations

import json
import re
from pathlib import Path

from contract import INVENTORY_REL

RUFF_RE = re.compile(r"ruff==([0-9][0-9.]*)")
BASED_RE = re.compile(r"basedpyright==([0-9][0-9.]*)")
JSONSCHEMA_RE = re.compile(r"jsonschema==([0-9][0-9.]*)")
PY_RE = re.compile(r"python-version=([0-9.]+)")
NODE_RE = re.compile(r"node-version=([0-9.]+)")


def load_inventory(repo: Path) -> dict:
    path = repo / INVENTORY_REL
    return json.loads(path.read_text(encoding="utf-8"))


def extract_pins(repo: Path) -> dict:
    inv = load_inventory(repo)
    ruff: dict[str, str] | None = None
    based: dict[str, str] | None = None
    jsonschema: dict[str, str] | None = None
    py_pins: list[str] = []
    node_pins: list[str] = []
    for wf in inv.get("workflows") or []:
        file_name = str(wf.get("file") or "")
        for job in wf.get("jobs") or []:
            job_name = str(job.get("name") or job.get("job_id") or "")
            for step in job.get("steps") or []:
                cmd = str(step.get("command") or "")
                step_name = str(step.get("name") or "")
                src = f"{file_name} job={job_name} step={step_name or step.get('index')}"
                m = RUFF_RE.search(cmd)
                if m and ruff is None:
                    ruff = {
                        "name": "ruff",
                        "pinned_version": m.group(1),
                        "role": "formatter",
                        "source_step": src + f" `{cmd[:80]}`",
                    }
                m = BASED_RE.search(cmd)
                if m and based is None:
                    based = {
                        "name": "basedpyright",
                        "pinned_version": m.group(1),
                        "role": "typechecker",
                        "source_step": src + f" `{cmd[:80]}`",
                    }
                m = JSONSCHEMA_RE.search(cmd)
                if m and jsonschema is None:
                    jsonschema = {
                        "name": "jsonschema",
                        "pinned_version": m.group(1),
                        "role": "linter",
                        "source_step": src + f" `{cmd[:80]}`",
                    }
                for hit in PY_RE.findall(cmd):
                    if hit not in py_pins:
                        py_pins.append(hit)
                for hit in NODE_RE.findall(cmd):
                    if hit not in node_pins:
                        node_pins.append(hit)
    formatters = [row for row in (ruff, based) if row]
    # jsonschema is a validator pin used by the p2-delivery gate, not a
    # formatter; keep it under interpreters-adjacent extras, not the
    # formatter/linter equality table.
    interpreters = []
    if py_pins:
        interpreters.append(
            {"name": "python", "pinned_version": py_pins[0], "all_seen": py_pins}
        )
    if node_pins:
        interpreters.append(
            {"name": "node", "pinned_version": node_pins[0], "all_seen": node_pins}
        )
    return {
        "source": INVENTORY_REL,
        "formatters_and_linters": formatters,
        "interpreters": interpreters,
        "jsonschema_pin": jsonschema,
        "inventory_totals": inv.get("totals"),
    }
