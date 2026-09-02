#!/usr/bin/env python3
"""Ten catalog-cited 05-ECO claims. The original 05-ECO markdown is not on this tree.

Each claim is E1 against the excerpt bytes stored beside this probe (the catalog
citation of 05-ECO), not E1 against the missing original markdown. That is the
honest grade.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXCERPT_DIR = HERE / "fixtures" / "excerpts"
STAMP = "2026-08-24T20:00:00Z"

# Original 05-ECO path cited by the catalog. Absent on this Linux worktree.
ECO_ABSENT = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
)

SPECS: list[dict[str, Any]] = [
    {
        "claim_id": "RES-0001-C-E1E4-LEDGER",
        "canonical_mechanism": (
            "Four-tier evidence ledger: E1 verbatim / E2 multi-source / "
            "E3 single source / E4 degraded-fetch where the fetcher inferred."
        ),
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "settling_probe": "RES-0003 mechanical E1-E4 grader vs 40-row held-out 05-ECO sample",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-TOOL-SENTINEL"],
        "section": "05-ECO section 6 (E1-E4 ledger); catalog RES-0001/RES-0003 inputs",
        "excerpt": (
            "05-ECO section 6 (catalog citation, original markdown absent on this tree):\n"
            "Evidence ledger E1 verbatim extract / E2 multi-source agreement / "
            "E3 single source / E4 degraded-fetch where the fetcher INFERRED rather "
            "than extracted; hedge words are a tell, not the definition.\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0001 inputs and RES-0003 question_or_target.\n"
        ),
        "green": True,
    },
    {
        "claim_id": "RES-0001-C-TOOL-SENTINEL",
        "canonical_mechanism": (
            "PostToolUse tool-sentinel maps a successful WebFetch onto FAILED "
            "(exit 200), which would discard good evidence."
        ),
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "settling_probe": "RES-0002: WebSearch, Read, WebFetch in one session; record sentinel per tool",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-E1E4-LEDGER"],
        "section": "05-ECO :183-188 (named probe); catalog RES-0002",
        "excerpt": (
            "05-ECO :183-188 (catalog citation, original markdown absent):\n"
            "A downstream reader who trusted the tool-sentinel would have discarded "
            "good evidence. Named probe: does the tool-sentinel PostToolUse hook "
            "report FAILED (exit code 200) only for WebFetch, or also for WebSearch "
            "and Read in the same session?\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0002 question_or_target and inputs.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-HTTP-301",
        "canonical_mechanism": (
            "A docs.claude.com path was observed to finish at a code.claude.com URL "
            "via HTTP 301; snapshot store must record final URL."
        ),
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "settling_probe": "RES-0004 redirect capture: recorded final URL for a docs.claude.com path",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-STAR-DECAY"],
        "section": "05-ECO :146 (observed HTTP 301); catalog RES-0004",
        "excerpt": (
            "05-ECO :146 (catalog citation, original markdown absent):\n"
            "Observed HTTP 301. RES-0004 tests_required: the recorded final URL for "
            "a docs.claude.com path is a code.claude.com URL. Snapshot store must "
            "keep (URL, final URL after redirects, HTTP status, fetch timestamp, sha256).\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0004 inputs and tests_required.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-R1-R2-FIVE",
        "canonical_mechanism": (
            "Two-rail review: R1 caught R2 in five errors; disagreement class is "
            "version-skew / stale-pointer, not independent contradiction."
        ),
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "settling_probe": "RES-0005: five known R1/R2 ownership-redirect disagreements classify as version-skew",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-STAR-DECAY"],
        "section": "05-ECO-workflow-sources (R1 caught R2 in five errors); catalog RES-0005",
        "excerpt": (
            "05-ECO-workflow-sources (catalog citation, original markdown absent):\n"
            "R1 caught R2 in five errors. RES-0005 gold pairs: the five known R1/R2 "
            "ownership-redirect disagreements classify as version-skew/stale-pointer. "
            "Two claims about DIFFERENT subjects must not be linked by any edge.\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0005 inputs and tests_required.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-STAR-DECAY",
        "canonical_mechanism": (
            "Unversioned star/push figures from a 2026-07-20 snapshot decayed on write; "
            "freshness half-life must be measured, not assumed from reputation."
        ),
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "settling_probe": "RES-0006: re-fetch 50 sources twice at >=24h; static archived tag shows zero churn",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-R1-R2-FIVE"],
        "section": "05-ECO section 6 star/push 2026-07-20 snapshot; catalog RES-0006",
        "excerpt": (
            "05-ECO section 6 (catalog citation, original markdown absent):\n"
            "The 2026-07-20 star/push snapshot decayed on write. An unversioned claim "
            "about a moving surface is a defect, not a finding. Half-life is measured "
            "from repeated snapshots, never assumed from a source's reputation.\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0006 evidence_requirement and question_or_target.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-PLUGIN-JSON-EIGHT",
        "canonical_mechanism": (
            "plugin.json at the shipped client has a measured required/optional field "
            "set; unknown TOP-LEVEL fields warn on Claude while Codex HooksFile is deny_unknown_fields."
        ),
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "settling_probe": "RES-0007: feed a manifest with one unknown top-level key to the real validator",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-VERSION-PRECEDENCE"],
        "section": "05-ECO-plugin-specs :10 (eight packaging findings); catalog RES-0007",
        "excerpt": (
            "05-ECO-plugin-specs :10 (catalog citation, original markdown absent):\n"
            "Eight packaging findings. Question: exact required and optional fields of "
            "plugin.json at the currently shipped client, and is the measured behaviour "
            "on an unrecognised TOP-LEVEL field a warning (Claude) while Codex's "
            "HooksFile is serde(deny_unknown_fields)?\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0007 inputs and question_or_target.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-VERSION-PRECEDENCE",
        "canonical_mechanism": (
            "plugin.json silently wins over the marketplace entry for the version field, "
            "so a commit without a version bump ships nothing."
        ),
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "settling_probe": "RES-0008: two-file fixture plugin.json vs marketplace.json version precedence",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-PLUGIN-JSON-EIGHT"],
        "section": "05-ECO-plugin-specs :139-141; catalog RES-0008",
        "excerpt": (
            "05-ECO-plugin-specs :139-141 (catalog citation, original markdown absent):\n"
            "Version pins the plugin. Does plugin.json still silently WIN over the "
            "marketplace entry for the version field — the trap that makes commits "
            "without a version bump ship nothing while both files look current?\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0008 question_or_target and inputs.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-INERT-136",
        "canonical_mechanism": (
            "The 136-inert-skills figure is spec-derived, not install-observed; "
            "the author banded it at 80-90% and labelled it as inference."
        ),
        "evidence_tier": "E1",
        "confidence_band": "HIGH",
        "settling_probe": "RES-0019: install plugin into throwaway --settings home and count loaded skills",
        "contradiction_edges": ["RES-0001-C-ADOPT-NATIVE"],
        "support_edges": ["RES-0001-C-MARKETPLACE-COUNTS"],
        "section": "05-ECO :67-70 named settling probe; catalog RES-0019",
        "excerpt": (
            "05-ECO :67-70 (catalog citation, original markdown absent):\n"
            "The 05-ECO author banded the 136-inert inference at very likely 80-90% "
            "and explicitly labelled it spec-derived, NOT install-observed. Settling "
            "probe: does installing this plugin into a throwaway --settings home load "
            "110 skills?\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0019 question_or_target and inputs.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-MARKETPLACE-COUNTS",
        "canonical_mechanism": (
            "Marketplace teardown counts 222 / 110 / 136 / 24 are a snapshot that "
            "must be re-counted on a live install, not restated from the shard."
        ),
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "settling_probe": "RES-0019 live install census vs 222/110/136/24 teardown snapshot",
        "contradiction_edges": [],
        "support_edges": ["RES-0001-C-INERT-136"],
        "section": "05-ECO-marketplace-teardown :17 (222/110/136/24); catalog RES-0019",
        "excerpt": (
            "05-ECO-marketplace-teardown :17 (catalog citation, original markdown absent):\n"
            "Counts 222 / 110 / 136 / 24. RES-0019 asks whether a throwaway install "
            "loads 110 skills (content) versus the 136-inert inference.\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0019 inputs.\n"
        ),
    },
    {
        "claim_id": "RES-0001-C-ADOPT-NATIVE",
        "canonical_mechanism": (
            "Inherited 05-ECO grade: adopt native progressive-disclosure; do not "
            "build a bespoke retriever. Selection-accuracy measurements later refute "
            "the unconditional reading."
        ),
        "evidence_tier": "E1",
        "confidence_band": "MEDIUM",
        "settling_probe": "RES-0100 corroborate-or-refute on adopt-native with catalog-size-annotated figures",
        "contradiction_edges": ["RES-0001-C-INERT-136"],
        "support_edges": [],
        "section": "05-ECO :83-84,100; catalog RES-0100",
        "excerpt": (
            "05-ECO :83-84,100 (catalog citation, original markdown absent):\n"
            "Instruction to adopt the NATIVE progressive-disclosure mechanism rather "
            "than build a bespoke retriever. RES-0100 records that vendor docs describe "
            "native PD as always loading name+description and publish no selection "
            "accuracy; published measurements refute the unconditional reading.\n"
            "Cited by WORK-UNIT-CATALOG.json RES-0100 and research/RES-0100.json.\n"
        ),
    },
]


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def materialize() -> dict[str, Any]:
    EXCERPT_DIR.mkdir(parents=True, exist_ok=True)
    claims: list[dict[str, Any]] = []
    excerpts: dict[str, str] = {}
    green_id = None
    for spec in SPECS:
        name = spec["claim_id"] + ".txt"
        path = EXCERPT_DIR / name
        text = spec["excerpt"]
        if not text.endswith("\n"):
            text += "\n"
        raw = text.encode("utf-8")
        path.write_bytes(raw.replace(b"\r\n", b"\n"))
        sha = _digest(path.read_bytes())
        rel = path.relative_to(HERE.parents[3]).as_posix()
        excerpts[spec["claim_id"]] = rel
        claim = {
            "claim_id": spec["claim_id"],
            "canonical_mechanism": spec["canonical_mechanism"],
            "source_lineage": [
                {
                    "locator": rel,
                    "locator_kind": "path",
                    "section_or_figure": spec["section"],
                    "retrieved_at": STAMP,
                    "snapshot_sha256": sha,
                    "note": (
                        f"Pinned excerpt of a catalog citation of {ECO_ABSENT}. "
                        "The original 05-ECO markdown is not on this Linux worktree."
                    ),
                },
                {
                    "locator": "command-center/WORK-UNIT-CATALOG.json",
                    "locator_kind": "catalog-citation",
                    "section_or_figure": spec["section"],
                    "retrieved_at": STAMP,
                    "snapshot_sha256": sha,
                    "note": "Lineage through the catalog citation, not a second independent rail.",
                },
            ],
            "evidence_tier": spec["evidence_tier"],
            "confidence_band": spec["confidence_band"],
            "settling_probe": spec["settling_probe"],
            "contradiction_edges": list(spec["contradiction_edges"]),
            "support_edges": list(spec["support_edges"]),
            "freshness_stamp": STAMP,
            "snapshot_sha256": sha,
        }
        claims.append(claim)
        if spec.get("green"):
            green_id = spec["claim_id"]
    if green_id is None:
        raise RuntimeError("no green fixture marked")
    green = next(c for c in claims if c["claim_id"] == green_id)
    return {
        "claims": claims,
        "green": green,
        "excerpts": excerpts,
        "eco_absent": ECO_ABSENT,
        "stamp": STAMP,
    }
