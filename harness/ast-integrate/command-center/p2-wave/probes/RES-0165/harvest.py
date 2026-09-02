#!/usr/bin/env python3
"""Harvest distinct finding strings from this estate's recorded research.

Dedicated multi-researcher transcripts for the two named run shapes
(broad landscape scan vs targeted question) are not on this worktree.
Claim texts below are computed from delivered research artifacts and
from IMP-0187's recorded ensemble members — not recalled.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _load(rel: str) -> Any:
    path = REPO / rel
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _row(fid: str, text: str, source: str, family: str) -> dict[str, str]:
    return {
        "id": fid,
        "text": text.strip(),
        "source": source,
        "family": family,
    }


def harvest_research_findings() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    r57 = _load("command-center/research/RES-0057.json")
    if isinstance(r57, dict):
        for grade in r57.get("gameability_grades") or []:
            if not isinstance(grade, dict):
                continue
            gid = str(grade.get("id") or "").strip()
            g = str(grade.get("grade") or "").strip()
            check = str(grade.get("check") or gid)
            if gid and g:
                rows.append(
                    _row(
                        gid,
                        f"{check} Scorecard-or-registry check grades {g}",
                        "command-center/research/RES-0057.json",
                        "targeted-scorecard-gameability",
                    )
                )

    r39 = _load("command-center/research/RES-0039.json")
    if isinstance(r39, dict):
        for cls in r39.get("attack_class_table") or []:
            if not isinstance(cls, dict):
                continue
            cid = str(cls.get("id") or "").strip()
            name = str(cls.get("name") or cid)
            if cid:
                rows.append(
                    _row(
                        f"mcp-{cid}",
                        f"MCP attack class {name} is in the threat table",
                        "command-center/research/RES-0039.json",
                        "landscape-mcp-threats",
                    )
                )

    r75 = _load("command-center/research/RES-0075.json")
    if isinstance(r75, dict):
        for claim in r75.get("claims") or r75.get("rules") or []:
            if not isinstance(claim, dict):
                continue
            mech = str(claim.get("canonical_mechanism") or "").strip()
            cid = str(claim.get("id") or mech)
            text = str(claim.get("text") or claim.get("claim") or mech).strip()
            if mech and text:
                rows.append(
                    _row(
                        cid or mech,
                        text[:240],
                        "command-center/research/RES-0075.json",
                        "landscape-delphi",
                    )
                )

    r93 = _load("command-center/research/RES-0093.json")
    if isinstance(r93, dict):
        seen_bench: set[str] = set()
        for bench in r93.get("benchmark_register") or []:
            if not isinstance(bench, dict):
                continue
            bid = str(bench.get("benchmark_id") or "").strip()
            verdict = str(bench.get("applicability_verdict") or "").strip()
            if bid and bid not in seen_bench:
                seen_bench.add(bid)
                rows.append(
                    _row(
                        f"bench-{bid}",
                        f"Agent benchmark {bid} applicability={verdict or 'recorded'}",
                        "command-center/research/RES-0093.json",
                        "landscape-benchmarks",
                    )
                )

    r66 = _load("command-center/research/RES-0066.json")
    if isinstance(r66, dict):
        for proj in r66.get("projects") or []:
            if not isinstance(proj, dict):
                continue
            pid = str(proj.get("id") or "").strip()
            lic = str(proj.get("license") or proj.get("license_id") or "").strip()
            if pid:
                rows.append(
                    _row(
                        f"lic-{pid}",
                        f"Multi-agent project {pid} license recorded as {lic or 'see-body'}",
                        "command-center/research/RES-0066.json",
                        "landscape-licenses",
                    )
                )

    r84 = _load("command-center/research/RES-0084.json")
    if isinstance(r84, dict):
        bs = r84.get("blind_spot") or {}
        if isinstance(bs, dict) and bs.get("id"):
            rows.append(
                _row(
                    str(bs["id"]),
                    str(bs.get("name") or bs["id"]),
                    "command-center/research/RES-0084.json",
                    "landscape-unique-ideas",
                )
            )

    # Dedup by id, keep first
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        if row["id"] in seen or not row["text"]:
            continue
        seen.add(row["id"])
        out.append(row)
    return out


def harvest_imp0187() -> dict[str, Any]:
    """Live ensemble fan-out: correlated members are not N independent findings."""
    sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/IMP-0187"))
    import ensemble as E  # noqa: E402

    correlated = E.load_fixture("correlated")
    independent = E.load_fixture("independent")
    corr_runs = [E.run_member(m, correlated["payload"]) for m in correlated["members"]]
    indep_runs = [E.run_member(m, independent["payload"]) for m in independent["members"]]
    corr_ind = E.assess_independence(corr_runs)
    indep_ind = E.assess_independence(indep_runs)
    corr_outputs = {r["output_hash"] for r in corr_runs}
    indep_outputs = {r["output_hash"] for r in indep_runs}
    return {
        "source": "command-center/p2-wave/probes/IMP-0187",
        "correlated": {
            "n_agents": len(corr_runs),
            "unique_output_hashes": len(corr_outputs),
            "independence": corr_ind.get("verdict"),
            "raw_n": corr_ind.get("raw_n"),
            "effective_n": corr_ind.get("effective_n"),
            "member_ids": [r["id"] for r in corr_runs],
        },
        "independent": {
            "n_agents": len(indep_runs),
            "unique_output_hashes": len(indep_outputs),
            "independence": indep_ind.get("verdict"),
            "raw_n": indep_ind.get("raw_n"),
            "effective_n": indep_ind.get("effective_n"),
            "member_ids": [r["id"] for r in indep_runs],
        },
        "note": (
            "IMP-0187 is a recorded ensemble fan-out on this estate. Shared "
            "briefing collapses unique outputs; disjoint probes do not. This "
            "is local evidence that agent count is not finding count."
        ),
    }


def census() -> dict[str, Any]:
    findings = harvest_research_findings()
    by_family: dict[str, int] = {}
    for row in findings:
        by_family[row["family"]] = by_family.get(row["family"], 0) + 1
    return {
        "n_findings": len(findings),
        "by_family": by_family,
        "sources_present": sorted({r["source"] for r in findings}),
        "dedicated_landscape_vs_targeted_transcripts": False,
        "substitution": (
            "Claim texts harvested from delivered research artifacts; "
            "researcher assignment is a constructed recorded-run with known "
            "overlap because dedicated fan-out transcripts for the two named "
            "run shapes are absent on this worktree."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(census(), indent=2, sort_keys=True))
    print("n_findings", census()["n_findings"])
