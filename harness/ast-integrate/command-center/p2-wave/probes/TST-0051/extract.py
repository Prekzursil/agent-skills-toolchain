"""Extract policy-declared vs tooling-enforced release gates from a tree."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contract import CANONICAL_IDS, canonical_ids, empty_record

CHECKLIST_REL = "command-center/RELEASE-CHECKLIST.md"
CONTRACT_REL = "command-center/phase4/contracts/ARC-0097.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
WORKFLOW_GLOBS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "ci/workflows/*.yml",
    "ci/workflows/*.yaml",
)
# Job/step keys that are YAML structure, not gate ids.
_NOT_JOB = frozenset(
    {
        "name",
        "runs-on",
        "steps",
        "needs",
        "if",
        "permissions",
        "defaults",
        "env",
        "concurrency",
        "outputs",
        "strategy",
        "timeout-minutes",
        "continue-on-error",
        "uses",
        "with",
        "run",
        "shell",
        "id",
        "working-directory",
        "on",
        "jobs",
        "defaults",
    }
)
_GATE_LINE = re.compile(
    r"^\s*-\s*\[[ xX]\]\s+`?([a-z][a-z0-9._-]{2,})`?",
    re.MULTILINE,
)
_GATE_HEADING = re.compile(
    r"^#{1,3}\s+(?:gate[:\s]+)?`?([a-z][a-z0-9._-]{2,})`?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_GATE_FIELD = re.compile(
    r"^\s*gate(?:_id| id)?\s*:\s*`?([a-z][a-z0-9._-]{2,})`?",
    re.MULTILINE | re.IGNORECASE,
)
_RUN_GATE_PY = re.compile(
    r"(?:python3?\s+-B\s+|python3?\s+)(\S*?([a-z0-9._-]*gate[a-z0-9._-]*)\.py)",
    re.IGNORECASE,
)
_JOB_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$")
_TOP = re.compile(r"^[A-Za-z0-9_-]+:\s*$")

# Libraries that exist but are not wired as a pull_request / release job.
LIBRARY_ONLY_GATES = {
    "tools/marketplace/secret_gate.py": "secret-scan-bundle",
    "tools/plugin/gate.py": "diverged-file-act-gate",
}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


_NOT_GATE_ID = frozenset(
    {
        "release",
        "checklist",
        "gates",
        "release-checklist",
        "command-center",
    }
)


def parse_checklist(text: str) -> list[str]:
    """Harvest kebab-case gate ids only.

    Live RELEASE-CHECKLIST.md is prose with checkboxes that start with ordinary
    words (`python`, `the`, `fires`). Fixtures quote real gate ids
    (`ci-green-pr-head`). Requiring a hyphen keeps those two shapes apart.
    """
    found: list[str] = []
    for rx in (_GATE_LINE, _GATE_HEADING, _GATE_FIELD):
        for m in rx.finditer(text or ""):
            gid = m.group(1).strip().lower()
            if gid in _NOT_GATE_ID or "-" not in gid:
                continue
            if gid not in found:
                found.append(gid)
    return found


def parse_contract_json(doc: Any) -> list[str]:
    ids: list[str] = []
    if not isinstance(doc, dict):
        return ids
    for key in ("gates", "gate_set", "required_gates", "policy_gates"):
        raw = doc.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    ids.append(item.strip())
                elif isinstance(item, dict) and item.get("id"):
                    ids.append(str(item["id"]).strip())
    body = doc.get("gate_set_required_to_release")
    if isinstance(body, dict):
        for item in body.get("gates") or []:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]).strip())
            elif isinstance(item, str):
                ids.append(item.strip())
    out: list[str] = []
    for gid in ids:
        g = gid.lower()
        if g and g not in out:
            out.append(g)
    return out


def workflow_jobs(text: str) -> list[str]:
    jobs: list[str] = []
    in_jobs = False
    for line in (text or "").splitlines():
        if re.match(r"^jobs:\s*(?:#.*)?$", line):
            in_jobs = True
            continue
        if in_jobs:
            m = _JOB_KEY.match(line)
            if m:
                key = m.group(1)
                if key not in _NOT_JOB and key not in jobs:
                    jobs.append(key)
                continue
            if line and not line.startswith(" ") and not line.startswith("\t"):
                if _TOP.match(line) and not line.startswith("jobs:"):
                    in_jobs = False
    return jobs


def workflow_gate_scripts(text: str) -> list[str]:
    ids: list[str] = []
    for m in _RUN_GATE_PY.finditer(text or ""):
        stem = Path(m.group(1)).stem
        gid = stem.replace("_", "-")
        if gid not in ids:
            ids.append(gid)
    return ids


def _glob_files(root: Path, pattern: str) -> list[Path]:
    return sorted(p for p in root.glob(pattern) if p.is_file())


def extract_policy(root: Path, *, include_canonical: bool) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    ids: list[str] = []
    if include_canonical:
        for gid in canonical_ids():
            if gid not in ids:
                ids.append(gid)
        sources.append(
            {
                "kind": "tdd-canonical",
                "path": "command-center/p2-wave/probes/TST-0051/contract.py",
                "ids": list(canonical_ids()),
            }
        )
    checklist = root / CHECKLIST_REL
    cl_text = _read(checklist) if checklist.is_file() else ""
    cl_ids = parse_checklist(cl_text) if cl_text else []
    sources.append(
        {
            "kind": "release-checklist",
            "path": CHECKLIST_REL,
            "present": checklist.is_file(),
            "ids": cl_ids,
        }
    )
    for gid in cl_ids:
        if gid not in ids:
            ids.append(gid)
    contract_path = root / CONTRACT_REL
    c_ids: list[str] = []
    if contract_path.is_file():
        try:
            c_ids = parse_contract_json(json.loads(contract_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            c_ids = []
    sources.append(
        {
            "kind": "arc-0097-contract",
            "path": CONTRACT_REL,
            "present": contract_path.is_file(),
            "ids": c_ids,
        }
    )
    for gid in c_ids:
        if gid not in ids:
            ids.append(gid)
    return {"ids": ids, "sources": sources}


def extract_tooling(root: Path) -> dict[str, Any]:
    ids: list[str] = []
    workflows: list[dict[str, Any]] = []
    invoked: list[str] = []
    for pattern in WORKFLOW_GLOBS:
        for path in _glob_files(root, pattern):
            rel = path.relative_to(root).as_posix()
            text = _read(path)
            jobs = workflow_jobs(text)
            scripts = workflow_gate_scripts(text)
            workflows.append({"path": rel, "jobs": jobs, "scripts": scripts})
            for gid in jobs + scripts:
                g = gid.replace("_", "-")
                if g not in ids:
                    ids.append(g)
                if g in scripts or g.endswith("-gate") or "gate" in g:
                    if g not in invoked:
                        invoked.append(g)
            for s in scripts:
                if s not in invoked:
                    invoked.append(s)
                if s not in ids:
                    ids.append(s)
    library_only: list[dict[str, Any]] = []
    for rel, gid in LIBRARY_ONLY_GATES.items():
        present = (root / rel).is_file()
        wired = gid in ids
        library_only.append({"path": rel, "id": gid, "present": present, "wired_as_release_job": wired})
        # Presence of a library is not enforcement.
    return {
        "ids": ids,
        "workflows": workflows,
        "invoked_from_workflow": invoked,
        "library_only": library_only,
        "orchestrator_present": _orchestrator_present(root),
    }


def _orchestrator_present(root: Path) -> bool:
    """True only if a runner exists that fails closed on unrun policy gates."""
    candidates = [
        "tools/release/orchestrator.py",
        "tools/release/run_gates.py",
        "tools/command-center/release_gates.py",
        "command-center/p2-wave/release_gates.py",
    ]
    return any((root / p).is_file() for p in candidates)


def live_snapshot(root: Path, *, include_canonical: bool = True) -> dict[str, Any]:
    policy = extract_policy(root, include_canonical=include_canonical)
    tooling = extract_tooling(root)
    pol = list(policy["ids"])
    tool = list(tooling["ids"])
    # A workflow job is "run" for a PR only if it is actually a required job.
    # We treat tooling ids as the set that *would* run when their workflow fires.
    # Policy ids with no tooling counterpart were never run.
    ran = [g for g in tool]
    records: dict[str, Any] = {}
    for gid in sorted(set(pol) | set(tool)):
        rec = empty_record(gid)
        rec["required"] = gid in pol
        if gid in tool:
            rec["status"] = "TOOLING-PRESENT"
            rec["evidence"] = "workflow-or-gate-script"
        else:
            rec["status"] = "NEVER-RUN"
            rec["evidence"] = ""
        if gid == "sc13-substitute-or-waiver":
            rec["unsatisfiable"] = True
            rec["waiver_id"] = "OQ-9" if include_canonical else ""
            rec["status"] = "WAIVED" if rec["waiver_id"] else rec["status"]
        if gid == "pr-only-no-marketplace-publish":
            rec["status"] = "POLICY-DECLARED"
            rec["evidence"] = "OQ-3 in WORK-UNIT-CATALOG.json owner_questions"
        records[gid] = rec
    allow_release = not tooling["orchestrator_present"]
    return {
        "policy_declared": pol,
        "tooling_enforced": tool,
        "ran": ran,
        "allow_release": allow_release,
        "release_mode": "PR-ONLY",
        "records": records,
        "policy_sources": policy["sources"],
        "tooling_meta": {
            "workflows": tooling["workflows"],
            "invoked_from_workflow": tooling["invoked_from_workflow"],
            "library_only": tooling["library_only"],
            "orchestrator_present": tooling["orchestrator_present"],
        },
        "include_canonical": include_canonical,
        "canonical_ids": sorted(CANONICAL_IDS),
    }


def set_difference(snapshot: dict[str, Any]) -> dict[str, Any]:
    pol = set(snapshot.get("policy_declared") or [])
    tool = set(snapshot.get("tooling_enforced") or [])
    policy_minus_tooling = sorted(pol - tool)
    tooling_minus_policy = sorted(tool - pol)
    return {
        "policy_minus_tooling": policy_minus_tooling,
        "tooling_minus_policy": tooling_minus_policy,
        "both_directions_printed": True,
        "sets_equal": not policy_minus_tooling and not tooling_minus_policy,
        "policy_count": len(pol),
        "tooling_count": len(tool),
        "symmetric_count": len(policy_minus_tooling) + len(tooling_minus_policy),
    }
