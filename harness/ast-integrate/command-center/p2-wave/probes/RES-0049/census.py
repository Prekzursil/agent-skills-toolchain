"""Live CI census for RES-0049.

Structured rail: parse the on-disk GitHub Actions inventory and this
worktree's .github/workflows tree. Does not fetch HTTP specs (probe2).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

INVENTORY_REL = (
    "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)
ACTIONS_API_REL = (
    "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
)

USES_RE = re.compile(r"uses:([^@\s]+)@")
GENERATOR_NEEDLES = (
    "attest-build-provenance",
    "actions/attest@",
    "actions/attest/",
    "slsa-github-generator",
    "in-toto",
    "intoto",
    "cosign",
    "sigstore",
    "slsa.dev",
)


def _find_line(text: str, needle: str) -> tuple[int, str] | None:
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i, line.strip()
    return None


def _scan_commands(inv: dict) -> tuple[list[str], list[dict], list[dict]]:
    uses: set[str] = set()
    gen_hits: list[dict] = []
    provenance_hits: list[dict] = []
    for wf in inv.get("workflows") or []:
        wfile = str(wf.get("file") or "")
        for job in wf.get("jobs") or []:
            for step in job.get("steps") or []:
                cmd = str(step.get("command") or "")
                name = str(step.get("name") or "")
                blob = f"{cmd} {name}".lower()
                for m in USES_RE.finditer(cmd):
                    uses.add(m.group(1))
                for needle in GENERATOR_NEEDLES:
                    if needle in blob:
                        gen_hits.append(
                            {
                                "file": wfile,
                                "job_id": job.get("job_id"),
                                "step_name": name,
                                "needle": needle,
                                "command": cmd[:240],
                            }
                        )
                if "provenance" in blob:
                    provenance_hits.append(
                        {
                            "file": wfile,
                            "job_id": job.get("job_id"),
                            "step_name": name,
                            "command": cmd[:240],
                        }
                    )
    return sorted(uses), gen_hits, provenance_hits


def _scan_live_workflows(repo: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Scan this worktree's .github/workflows for generator needles.

    Independent of the AUD-0041 inventory parse: catches workflows added
    after that inventory was frozen.
    """
    gh = repo / ".github" / "workflows"
    gen_hits: list[dict] = []
    provenance_hits: list[dict] = []
    live_anchors: list[dict] = []
    if not gh.is_dir():
        return gen_hits, provenance_hits, live_anchors
    files = sorted(
        p
        for p in gh.iterdir()
        if p.is_file() and p.suffix in {".yml", ".yaml"}
    )
    for path in files:
        rel = path.relative_to(repo).as_posix()
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        for needle in GENERATOR_NEEDLES:
            if needle.lower() not in low:
                continue
            found = _find_line(text, needle)
            if found is None:
                found = _find_line(low, needle.lower())
            gen_hits.append(
                {
                    "file": rel,
                    "job_id": None,
                    "step_name": None,
                    "needle": needle,
                    "command": (found[1][:240] if found else needle),
                    "line": found[0] if found else None,
                    "source": "live-worktree",
                }
            )
        if "provenance" in low:
            found = _find_line(text, "provenance")
            if found:
                provenance_hits.append(
                    {
                        "file": rel,
                        "job_id": None,
                        "step_name": None,
                        "command": found[1][:240],
                        "line": found[0],
                        "source": "live-worktree",
                    }
                )
    quality = repo / ".github" / "workflows" / "quality.yml"
    if quality.is_file():
        qtext = quality.read_text(encoding="utf-8")
        found = _find_line(qtext, "runs-on: ubuntu-latest")
        if found:
            live_anchors.append(
                {
                    "path": ".github/workflows/quality.yml",
                    "line": found[0],
                    "snippet": found[1],
                    "role": "live-quality-yml-runs-on",
                }
            )
        found = _find_line(qtext, "test_manifest_provenance.py")
        if found:
            live_anchors.append(
                {
                    "path": ".github/workflows/quality.yml",
                    "line": found[0],
                    "snippet": found[1],
                    "role": "live-quality-yml-provenance-test",
                }
            )
    return gen_hits, provenance_hits, live_anchors


def run_census(repo: Path) -> dict[str, Any]:
    gh = repo / ".github" / "workflows"
    worktree_files = []
    if gh.is_dir():
        worktree_files = sorted(
            p.relative_to(repo).as_posix()
            for p in gh.iterdir()
            if p.is_file()
        )
    inv_path = repo / INVENTORY_REL
    raw = inv_path.read_text(encoding="utf-8")
    inv = json.loads(raw)
    workflows = [
        str(w.get("file") or "")
        for w in (inv.get("workflows") or [])
        if isinstance(w, dict)
    ]
    uses, gen_hits, provenance_hits = _scan_commands(inv)
    live_gen, live_prov, live_anchors = _scan_live_workflows(repo)
    gen_hits = list(gen_hits) + live_gen
    provenance_hits = list(provenance_hits) + live_prov
    totals = inv.get("totals") or {}
    anchors = []
    for role, needle in (
        ("quality-yml-file", '".github/workflows/quality.yml"'),
        ("hook-manifest-provenance-test", "test_manifest_provenance.py"),
        ("inventory-workflow-count", '"workflow_files": 7'),
    ):
        found = _find_line(raw, needle)
        if found:
            anchors.append(
                {
                    "path": INVENTORY_REL,
                    "line": found[0],
                    "snippet": found[1],
                    "role": role,
                }
            )
    lines = raw.splitlines()
    q_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if '".github/workflows/quality.yml"' in line
        ),
        None,
    )
    if q_idx is not None:
        for i in range(q_idx, len(lines)):
            if '"runs_on": "ubuntu-latest"' in lines[i]:
                anchors.append(
                    {
                        "path": INVENTORY_REL,
                        "line": i + 1,
                        "snippet": lines[i].strip(),
                        "role": "quality-yml-runs-on",
                    }
                )
                break
    anchors.extend(live_anchors)
    quality = next(
        (w for w in (inv.get("workflows") or []) if w.get("file") == ".github/workflows/quality.yml"),
        None,
    )
    quality_jobs = []
    if isinstance(quality, dict):
        for job in quality.get("jobs") or []:
            quality_jobs.append(
                {
                    "job_id": job.get("job_id"),
                    "name": job.get("name"),
                    "runs_on": job.get("runs_on"),
                    "step_count": job.get("step_count"),
                }
            )
    return {
        "github_workflows_dir_present": gh.is_dir(),
        "worktree_workflow_files": worktree_files,
        "inventory_rel": INVENTORY_REL,
        "actions_api_rel": ACTIONS_API_REL,
        "inventory_workflow_files": workflows,
        "inventory_job_count": int(totals.get("jobs") or 0),
        "inventory_step_count": int(totals.get("steps") or 0),
        "inventory_workflow_count": int(totals.get("workflow_files") or len(workflows)),
        "uses_actions": uses,
        "attestation_generator_hits": gen_hits,
        "provenance_token_hits": provenance_hits,
        "quality_yml_jobs": quality_jobs,
        "cap_anchors": anchors,
        "measured_build_level": "L0",
        "why_not_l1": (
            "No provenance-generation step in any inventoried workflow; "
            "the only 'provenance' token is a hook-manifest unit test, "
            "not SLSA provenance."
        ),
        "max_without_hosted_builder": "L1",
        "next_level": "L2",
    }


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=1, sort_keys=True)
