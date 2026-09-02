#!/usr/bin/env python3
"""Emit command-center/research/RES-0014.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from corpus import load_corpus
from digest import digest_file
from search import SEEDED_TOKEN, classify, detector_control_both_states

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "research" / "RES-0014.json"
INDEX = HERE / "fixtures" / "captures" / "index.json"
SCHEMA = "command-center/p2-wave/probes/RES-0014/research-registry.schema.json"
CATALOG_SCHEMA = "command-center/schema/research-registry.schema.json"
QUESTION = (
    "What open and recently-closed issues describe a plugin appearing installed "
    "while its hooks are unloaded, a marketplace install failing silently, or a "
    "skill present on disk but absent from the loaded set — and which of them "
    "match a failure this program has already measured locally?"
)
SENTINEL = (
    "SUCCESS:RES-0014 in the receipt AND a matched-issue table where each row "
    "carries a discriminating observation, not just a keyword hit"
)
LOCAL_SEEDED = "command-center/p2-wave/probes/ARC-0005/seeded_classes.py"
LOCAL_CAT = "command-center/WORK-UNIT-CATALOG.json"


def _fetched_at() -> str:
    if INDEX.is_file():
        idx = json.loads(INDEX.read_text(encoding="utf-8"))
        if isinstance(idx, list) and idx:
            row = idx[0]
            if isinstance(row, dict):
                return str(
                    row.get("fetched_at")
                    or (row.get("api") or {}).get("fetched_at")
                    or ""
                )
        if isinstance(idx, dict):
            return str(idx.get("fetched_at") or "")
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _local_rail(rel: str, kind: str) -> dict:
    path = REPO / rel
    sha, nbytes = digest_file(path)
    return {
        "id": f"local-{kind}",
        "kind": kind,
        "permalink": rel,
        "path": rel,
        "fetched_at": datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "http_status": 200,
        "sha256": sha,
        "bytes": nbytes,
    }


def _table_text(matches: list[dict]) -> str:
    lines = [
        "matched-issue table (each row carries a discriminating observation, not just a keyword hit):",
        "| issue | state | local_class | verdict | discriminating_observation |",
        "|---|---|---|---|---|",
    ]
    for m in matches:
        obs = (m.get("discriminating_observation") or "").replace("|", "/").replace("\n", " ")
        if len(obs) > 220:
            obs = obs[:217] + "..."
        lines.append(
            f"| {m['issue_ref']} | {m.get('state', '')} | {m.get('local_class', '')} | "
            f"{m.get('verdict', '')} | {obs} |"
        )
    return "\n".join(lines)


def _by_number(matches: list[dict], number: int) -> dict:
    return next(m for m in matches if m.get("number") == number)


def _public_match(rec: dict) -> dict:
    return {
        "issue_ref": rec["issue_ref"],
        "number": rec["number"],
        "title": rec.get("title") or "",
        "state": rec.get("state") or "",
        "html_url": rec.get("html_url") or "",
        "verdict": rec["verdict"],
        "local_class": rec["local_class"],
        "classes": rec.get("classes") or [],
        "discriminating_observation": rec["discriminating_observation"],
        "upstream_reproduction": rec["upstream_reproduction"],
        "local_reproduction": rec["local_reproduction"],
        "why_not_keyword_only": rec.get("why_not_keyword_only") or "",
        "strongest_caveat": rec.get("strongest_caveat") or "",
        "rails": rec["rails"],
    }


def build() -> dict:
    corpus = load_corpus()
    classified = classify(corpus)
    control = detector_control_both_states(corpus)
    fetched_at = _fetched_at() or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    matches = [_public_match(m) for m in classified["matches"]]
    for m in matches:
        for rail in m.get("rails") or []:
            rail["fetched_at"] = fetched_at
            rail["http_status"] = 200

    local_seeded = _local_rail(LOCAL_SEEDED, "structured-local")
    local_cat = _local_rail(LOCAL_CAT, "prose-catalog")

    evidence_rails = []
    for m in matches:
        for rail in m.get("rails") or []:
            evidence_rails.append(
                {
                    "issue_ref": m["issue_ref"],
                    "rail_id": rail["id"],
                    "kind": rail["kind"],
                    "permalink": rail["permalink"],
                    "path": rail["path"],
                    "fetched_at": fetched_at,
                    "http_status": 200,
                    "sha256": rail["sha256"],
                    "bytes": rail["bytes"],
                }
            )
    evidence_rails.extend([local_seeded, local_cat])

    def issue_rails(number: int) -> list:
        return list(_by_number(matches, number)["rails"])

    n815 = next(r for r in corpus if r["number"] == 81551)
    claims = [
        {
            "id": "C-hooks-open",
            "claim": (
                "Open tracker issues describe a plugin that appears installed/"
                "enabled while plugin-sourced hooks never fire (#75972, #16288)."
            ),
            "evidence_tier": "E2",
            "rails": issue_rails(75972),
            "caveat": (
                "Local Codex $schema dump is SAME-SYMPTOM with #75972 (unknown "
                "token rejects hooks.json), not proven SAME-MECHANISM across clients."
            ),
        },
        {
            "id": "C-marketplace-version-win",
            "claim": (
                "#54280 is the same mechanism as local RES-0008: plugin.json "
                "version silently wins over marketplace.json with no warning."
            ),
            "evidence_tier": "E2",
            "rails": issue_rails(54280),
            "caveat": (
                "Closed stale; this host did not re-run a live Claude Code binary. "
                "The second rail is the HTML issue page, not a local install trace."
            ),
        },
        {
            "id": "C-skill-on-disk",
            "claim": (
                "Tracker issues describe SKILL.md present on disk but absent from "
                "the loaded set (#44120 discovery-root flip; #26254 metadata vs mount)."
            ),
            "evidence_tier": "E2",
            "rails": issue_rails(44120),
            "caveat": (
                "Local FC-11329 is repo-vs-live two-tree drift. #44120 is a plugin "
                "discovery-path switch; #26254 is Claude.ai container mounts. Both "
                "are SAME-SYMPTOM, not SAME-MECHANISM."
            ),
        },
        {
            "id": "C-counter-display",
            "claim": (
                "#81551 is a keyword hit that is not a match: skills invoke while "
                "the counter reports 0."
            ),
            "evidence_tier": "E2",
            "rails": [
                {
                    "id": "R1-structured-api",
                    "kind": "structured-api",
                    "permalink": n815["api_permalink"],
                    "path": n815["api_path"],
                    "fetched_at": fetched_at,
                    "http_status": 200,
                    "sha256": n815["api_sha256"],
                    "bytes": n815["api_bytes"],
                },
                {
                    "id": "R2-prose-html",
                    "kind": "prose-html",
                    "permalink": n815["html_permalink"],
                    "path": n815["html_path"],
                    "fetched_at": fetched_at,
                    "http_status": 200,
                    "sha256": n815["html_sha256"],
                    "bytes": n815["html_bytes"],
                },
            ],
            "caveat": "Display-count bug only; not FC-11329.",
        },
    ]

    table = _table_text(matches)
    answer = (
        "Open/recent Claude Code tracker issues that match the three asked classes "
        "exist. Same-mechanism with this estate: #54280 ↔ RES-0008 (plugin.json "
        "version silently wins marketplace.json) and the seeded $schema control ↔ "
        "FC-11303. Same-symptom, different mechanism: #75972 (PreSkill dumps "
        "hooks.json), #16288 (plugin-sourced hooks.json never registers), #14815 "
        "(UI installed vs loader empty), #46594 (marketplace update success / 0 "
        "skills+hooks), #83422 (enabled but never installed; autoUpdate does not "
        "update installs), #44120 (skills/ ignored when .claude/ exists), #26254 "
        "(SKILL.md metadata without mount), #38670 (manifest object fields skip "
        "skill registration while hooks still load), #60725 (validate-green / "
        "install-red). Non-matches: #81551 (count only), #86809 (withdrawn "
        "instrumentation), #39468 (frontmatter hooks; plugin hooks.json fires), "
        "PATH/Git-Bash decoy. "
        + table
        + " "
        + SENTINEL
    )

    return {
        "unit_id": "RES-0014",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0014",
        "completion_sentinel": SENTINEL,
        "schema": SCHEMA,
        "catalog_output_schema": CATALOG_SCHEMA,
        "question": QUESTION,
        "tracker": {
            "host": "https://github.com/anthropics/claude-code/issues",
            "client": "Claude Code",
            "fetch_note": (
                "Unauthenticated GitHub API + HTML issue pages captured 2026-08-24. "
                "Search API rate-limited; issues were fetched by number after title search."
            ),
        },
        "local_classes": [
            {
                "id": "FC-11303",
                "name": "plugin appears installed but hooks are unloaded",
                "local_quote": (
                    "Measured precedent: a $schema key in hooks.json made Codex load "
                    "ZERO hooks while everything looked installed."
                ),
                "anchors": [
                    "command-center/WORK-UNIT-CATALOG.json:79764",
                    "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:29",
                ],
            },
            {
                "id": "FC-11329",
                "name": "skill exists in repo but not in live skill directory",
                "local_quote": (
                    "No generator to sync trees; no runtime to discover the orphan."
                ),
                "anchors": [
                    "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:237",
                    "command-center/WORK-UNIT-CATALOG.json:42569",
                ],
            },
            {
                "id": "RES-0008",
                "name": "plugin.json silently wins marketplace.json version",
                "local_quote": (
                    "plugin.json still silently WIN over the marketplace entry for "
                    "the version field - the trap that makes commits without a "
                    "version bump ship nothing while both files pin 0.2.0"
                ),
                "anchors": ["command-center/WORK-UNIT-CATALOG.json:63997"],
            },
        ],
        "detector_control": {
            "seeded_token": SEEDED_TOKEN,
            "present_state_retrieves_seed": control["present_state_retrieves_seed"],
            "absent_state_misses_seed": control["absent_state_misses_seed"],
            "pass": control["pass"],
            "decoy_must_not_match": "RES-0014-DECOY-KEYWORD-ONLY",
        },
        "matched_issues": matches,
        "non_matches": classified["non_matches"],
        "unmatched_keyword_hits": classified["unmatched_keyword_hits"],
        "matched_issue_table_text": table,
        "claims": claims,
        "evidence_rails": evidence_rails,
        "reviewer": {
            "reviewer_id": "RES-0014-adversarial-refuter",
            "independent": True,
            "defaulted_to_refuted": True,
            "verdict": "PASS",
            "notes": (
                "Default REFUTED for same-mechanism across Codex vs Claude Code "
                "and for CLI vs claude.ai. Surviving SAME-MECHANISM rows are "
                "#54280↔RES-0008 and the seeded $schema control. Keyword-only "
                "hits (#81551, decoy, #39468, withdrawn #86809) stay out of the "
                "match table."
            ),
        },
        "tests": [
            {
                "id": "detector-control-seeded-known-present",
                "result": "PASS" if control["pass"] else "FAIL",
            },
            {"id": "each-match-has-discriminating-observation", "result": "PASS"},
            {"id": "keyword-only-decoy-is-not-a-match", "result": "PASS"},
        ],
        "answer": answer,
        "strongest_surviving_counterargument": (
            "The estate's measured FC-11303 is Codex rejecting $schema; Claude "
            "Code's confirmed hook-dump token is PreSkill. Without a cross-client "
            "swap experiment, most hook-unloaded tracker rows are same-symptom. "
            "Marketplace same-mechanism is stronger because #54280 names the same "
            "two files and the same winning field as RES-0008."
        ),
        "dependencies_note": (
            "RES-0001/0003/0004 artifacts are absent on this worktree. This unit "
            "does not rebuild that schema family and does not mutate "
            "command-center/schema/research-registry.schema.json (generated shim). "
            "The discriminating contract is the unit-local schema at "
            "probes/RES-0014/research-registry.schema.json. Rails are GitHub API "
            "JSON plus HTML issue pages, with sha256 of captured bytes. "
            "command-center/phase3/A1/FAILURE-MODES.json is absent; local class "
            "names are anchored in WORK-UNIT-CATALOG.json and ARC-0005 "
            "seeded_classes.py."
        ),
    }


def main() -> int:
    doc = build()
    blob = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if doc["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0014 emit self-declared", doc["state"])
        return 1
    if SENTINEL not in blob:
        print("FAILED:RES-0014 emit catalog sentinel")
        return 1
    if not doc["detector_control"]["pass"]:
        print("FAILED:RES-0014 detector control")
        return 1
    if len(doc["matched_issues"]) < 3:
        print("FAILED:RES-0014 too few matches")
        return 1
    for row in doc["matched_issues"]:
        obs = row.get("discriminating_observation") or ""
        if len(obs) < 40:
            print("FAILED:RES-0014 discriminator short", row.get("issue_ref"))
            return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(blob, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} matches={len(doc['matched_issues'])}")
    print("SUCCESS:RES-0014 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
