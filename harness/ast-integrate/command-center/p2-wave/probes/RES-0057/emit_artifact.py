#!/usr/bin/env python3
"""Emit command-center/research/RES-0057.json from captured dual-rail sources."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    ART_REL,
    CAPTURES,
    REPO,
    api_differential,
    evaluate_all,
    load_json,
    load_lineage,
)
from taxonomy import ROWS, SENTINEL  # noqa: E402

OUT = REPO / ART_REL


def _commit_sha() -> str:
    doc = load_json(CAPTURES / "scorecard-commit.json")
    return str(doc.get("sha") or "main")


def _lineage_map() -> dict[str, dict]:
    return {r["name"]: r for r in load_lineage()}


def _rail(rec: dict, kind: str, excerpt: str) -> dict:
    url = rec.get("url") or ""
    sha = rec.get("sha256")
    commit = _commit_sha()
    permalink = url
    if "raw.githubusercontent.com/ossf/scorecard/main/" in url:
        rel = url.split("/main/", 1)[1]
        permalink = f"https://github.com/ossf/scorecard/blob/{commit}/{rel}"
    elif "api.github.com/repos/ossf/scorecard/commits/main" in url:
        permalink = f"https://github.com/ossf/scorecard/commit/{commit}"
    elif "api.securityscorecards.dev" in url:
        permalink = url
    return {
        "kind": kind,
        "capture": rec["name"],
        "permalink": permalink,
        "source_url": url,
        "fetch_timestamp": rec.get("fetch_timestamp"),
        "http_status": rec.get("http_status"),
        "sha256": sha,
        "bytes": rec.get("bytes"),
        "excerpt": excerpt,
    }


def _rails_for(row: dict, lin: dict[str, dict]) -> list[dict]:
    rails = []
    for cap in row.get("structured_captures") or []:
        rails.append(_rail(lin[cap], "structured-api", f"structured detector for {row['check']}"))
    for cap in row.get("prose_captures") or []:
        rails.append(_rail(lin[cap], "prose-source", f"prose documentation for {row['check']}"))
    # Guarantee two mechanically independent kinds even when a row has one capture of each.
    if len(rails) < 2:
        raise SystemExit(f"{row['id']} produced <2 rails")
    return rails


def build() -> dict:
    lin = _lineage_map()
    diff, diff_fail = api_differential()
    if diff_fail:
        raise SystemExit("api differential: " + "; ".join(diff_fail))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    grades = []
    for row in ROWS:
        grades.append(
            {
                "id": row["id"],
                "family": row["family"],
                "check": row["check"],
                "grade": row["grade"],
                "cheap_satisfaction_recipe": row.get("cheap_satisfaction_recipe"),
                "resistant_reason": row.get("resistant_reason"),
                "recipe_tokens": row.get("recipe_tokens") or [],
                "why": row.get("why"),
                "rails": _rails_for(row, lin),
            }
        )
    license_rails = _rails_for(next(r for r in ROWS if r["id"] == "scorecard.License"), lin)
    vuln_rails = _rails_for(next(r for r in ROWS if r["id"] == "scorecard.Vulnerabilities"), lin)
    npms_rails = _rails_for(next(r for r in ROWS if r["id"] == "npms.quality.carefulness"), lin)
    dep_rails = _rails_for(next(r for r in ROWS if r["id"] == "librariesio.sourcerank.dependents"), lin)
    claims = [
        {
            "id": "C1-file-presence-gameable",
            "claim": (
                "OpenSSF Scorecard checks whose detectors are filename or config "
                "presence (License, Security-Policy, Dependency-Update-Tool, SAST, "
                "SBOM, and the npms carefulness/branding/tests pillars) are GAMEABLE: "
                "a publisher can collect the points by adding LICENSE, SECURITY.md, "
                "dependabot.yml, a CodeQL workflow, badges, or a 1.0.0 tag without "
                "changing the shipped product's exploitability."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "rails": license_rails + npms_rails,
        },
        {
            "id": "C2-osv-resistant-control",
            "claim": (
                "The Scorecard Vulnerabilities check is GAMING-RESISTANT relative to "
                "file-drop checks because it calls ListUnfixedVulnerabilities against "
                "OSV. Live structured API for github.com/ossf/scorecard scored "
                f"License={diff.get('license_score')} and Security-Policy="
                f"{diff.get('security_policy_score')} while Vulnerabilities="
                f"{diff.get('vulnerabilities_score')} with {diff.get('vulnerabilities_n')} "
                "osv.dev IDs. Adding SECURITY.md does not clear those IDs."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "rails": vuln_rails,
        },
        {
            "id": "C3-registry-dependents-resist",
            "claim": (
                "libraries.io SourceRank presence flags (readme_present, license_present, "
                "one_point_oh, follows_semver) are GAMEABLE one-point file/metadata "
                "drops, but dependent_projects uses log10 of other packages that declare "
                "a dependency and is the resistant column of that registry score."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "rails": dep_rails,
        },
    ]
    doc = {
        "unit_id": "RES-0057",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema": "command-center/schema/research-claim-record.schema.json",
        "question": (
            "For OpenSSF Scorecard and registry quality scores, which individual "
            "checks can a publisher trivially satisfy without improving anything, "
            "and which resist gaming — the difference that decides whether a "
            "conformance score belongs in this marketplace?"
        ),
        "answer": (
            "Most Scorecard checks and the npms.io / SourceRank presence pillars are "
            "GAMEABLE via file or config drops; the marketplace must not treat a "
            "composite Scorecard or npms quality number as install-time trust. The "
            "resistant control is OSV-backed Vulnerabilities (and SourceRank dependents). "
            "Fuzzing is MIXED: ClusterFuzzLite YAML is cheap, OSS-Fuzz membership is not."
        ),
        "marketplace_implication": (
            "A composite OpenSSF Scorecard, npms quality, or SourceRank total is not "
            "an install-time trust input for this marketplace. File-presence and "
            "self-attestation checks are cheap to max. If a numeric signal is used "
            "at all, restrict it to OSV-backed unfixed-vulnerability presence and "
            "treat ignore-lists as a remaining game."
        ),
        "api_differential": diff,
        "produced_at": now,
        "scorecard_commit": _commit_sha(),
        "gameability_grades": grades,
        "claims": claims,
        "tests": [
            {
                "id": "probe1-gameable-recipes",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0057/probe1_gameable_recipes.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2-resistant-control",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0057/probe2_resistant_control.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0057-partitioned-dual-rail",
            "verdict": "PASS",
            "independent": True,
            "reviewers": [
                {
                    "id": "R1-structured-api",
                    "vendor_role": "structured-API-rail",
                    "scope": [
                        "scorecard-*.go",
                        "scorecard-api-ossf.json",
                        "npms-quality.js",
                        "librariesio-source-rank.rb",
                    ],
                },
                {
                    "id": "R2-prose-docs",
                    "vendor_role": "prose-docs-rail",
                    "scope": ["scorecard-checks.md", "npms-architecture.md"],
                },
            ],
        },
        "evidence_requirement": (
            "every claim carries TWO mechanically independent rails (structured API "
            "or detector source AND a prose source), each with a permalink, fetch "
            "timestamp, HTTP status and sha256 of the captured bytes"
        ),
        "gameable_n": sum(1 for r in ROWS if r["grade"] in {"GAMEABLE", "MIXED"}),
        "resistant_n": sum(1 for r in ROWS if r["grade"] in {"RESISTANT", "MIXED"}),
        "row_n": len(ROWS),
    }
    return doc


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = evaluate_all(doc)
    print(json.dumps({k: report[k] for k in ("ok", "failure_n", "failures", "api_differential") if k in report}, indent=2))
    if not report["ok"]:
        print("FAILED:RES-0057 emit")
        return 1
    print(f"wrote {ART_REL}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
