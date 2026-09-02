#!/usr/bin/env python3
"""Inventory advisory-database-dependent gates and stored greens for CNF-0153."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_QUALITY = REPO / ".github/workflows/quality.yml"
HIST_YAML = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
HIST_API = REPO / "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
RISK = REPO / "command-center/RISK-REGISTER.md"
OSV_TOML = REPO / "osv-scanner.toml"

LIVE_QUERY_RX = re.compile(
    r"osv-scanner|gate-deps|trivy|dependabot|pip-audit|npm audit|snyk|grype|advisory",
    re.IGNORECASE,
)


def live_workflow_text() -> str:
    if not LIVE_QUALITY.is_file():
        return ""
    return LIVE_QUALITY.read_text(encoding="utf-8")


def live_advisory_gates() -> list[dict]:
    text = live_workflow_text()
    hits = sorted(set(LIVE_QUERY_RX.findall(text)))
    present = bool(hits)
    return [
        {
            "id": "live-quality-yml",
            "path": ".github/workflows/quality.yml",
            "present": LIVE_QUALITY.is_file(),
            "advisory_tokens": hits,
            "contains_osv_scanner": "osv-scanner" in text.lower(),
            "contains_gate_deps": "gate-deps" in text.lower() or "osv-scanner" in text.lower(),
            "definition_present": present,
            "live_query": present,
        }
    ]


def historical_gate_deps_definition() -> dict:
    empty = {
        "present": False,
        "workflow": None,
        "job_id": None,
        "name": None,
        "command": None,
    }
    if not HIST_YAML.is_file():
        return empty
    data = json.loads(HIST_YAML.read_text(encoding="utf-8"))
    for wf in data.get("workflows") or []:
        if not isinstance(wf, dict):
            continue
        for job in wf.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            name = str(job.get("name") or "")
            jid = str(job.get("job_id") or "")
            if "gate-deps" in name.lower() or jid == "deps":
                cmd = None
                for step in job.get("steps") or []:
                    if isinstance(step, dict) and "osv-scanner" in str(step.get("command") or ""):
                        cmd = step.get("command")
                        break
                return {
                    "present": True,
                    "workflow": wf.get("file"),
                    "job_id": jid,
                    "name": name,
                    "command": cmd,
                    "source": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
                }
    return empty


def stored_gate_deps_result() -> dict:
    empty = {
        "present": False,
        "conclusion": None,
        "run_id": None,
        "advisory_ids": [],
        "snapshot_id": None,
        "query_timestamp": None,
    }
    if not HIST_API.is_file():
        return empty
    data = json.loads(HIST_API.read_text(encoding="utf-8"))
    for run in data.get("runs") or []:
        if not isinstance(run, dict):
            continue
        for job in run.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            name = str(job.get("name") or "")
            if "gate-deps" not in name.lower():
                continue
            return {
                "present": True,
                "conclusion": job.get("conclusion"),
                "run_id": run.get("run_id"),
                "workflow": run.get("workflow"),
                "name": name,
                "advisory_ids": [],
                "snapshot_id": None,
                "query_timestamp": None,
                "source": "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json",
                "note": (
                    "Actions job conclusion only; no advisory list, no database "
                    "snapshot id, no query timestamp. Stored green cannot measure decay."
                ),
            }
    return empty


def inputs_status() -> dict:
    return {
        "risk_register_md": {
            "path": "command-center/RISK-REGISTER.md",
            "present": RISK.is_file(),
        },
        "osv_scanner_toml": {
            "path": "osv-scanner.toml",
            "present": OSV_TOML.is_file(),
        },
        "historical_yaml_inventory": {
            "path": str(HIST_YAML.relative_to(REPO)),
            "present": HIST_YAML.is_file(),
        },
        "historical_actions_api": {
            "path": str(HIST_API.relative_to(REPO)),
            "present": HIST_API.is_file(),
        },
    }


def estate_lockfiles() -> list[Path]:
    roots = [
        HERE / "inputs" / "package-lock.json",
        HERE / "inputs" / "current" / "package-lock.json",
        HERE / "inputs" / "tools" / "mcp" / "hacktricks-mcp-server" / "package-lock.json",
        HERE / "inputs" / "current" / "tools" / "mcp" / "hacktricks-mcp-server" / "package-lock.json",
    ]
    seen: set[str] = set()
    out: list[Path] = []
    for path in roots:
        if not path.is_file():
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        out.append(path)
    return out


def control_lockfiles() -> dict[str, Path]:
    return {
        "known_vulnerable": HERE / "known-vulnerable" / "package-lock.json",
        "known_clean": HERE / "known-clean" / "package-lock.json",
        "exploratory_lodash_4_17_21": HERE / "exploratory-lodash-4.17.21" / "package-lock.json",
    }
