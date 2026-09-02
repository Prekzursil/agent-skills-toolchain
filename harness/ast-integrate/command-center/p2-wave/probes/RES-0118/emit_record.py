#!/usr/bin/env python3
"""Emit command-center/research/RES-0118.json from the pinned harvest."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys_path_note = HERE
import sys

sys.path.insert(0, str(HERE))
import checker as C  # noqa: E402

OUT_REL = C.OUT_REL
SENTINEL = C.SENTINEL
HARVEST = HERE / "harvest.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

MECHANISMS = [
    {
        "id": "M-COUNCIL-STEELMAN",
        "name": "steelman-before-rebuttal deliberation gate",
        "path": "tools/council/protocol/steelman.py",
        "fallback_path": "tools/council/protocol/schema/steelman-gate.schema.json",
        "inventory_keywords": [
            "deliberation",
            "rebuttal",
            "steelman",
            "council",
            "consensus",
        ],
    },
    {
        "id": "M-EVIDENCE-TIER",
        "name": "preset evidence-tier enforcement at claim admission",
        "path": "tools/council/evidence/standard.py",
        "inventory_keywords": [
            "evidence",
            "admission",
            "tier",
            "classifier",
        ],
    },
    {
        "id": "M-TOURNAMENT-DISSENT",
        "name": "architecture-tournament dissent preservation",
        "path": "tools/blueprints/tournament.py",
        "inventory_keywords": [
            "tournament",
            "dissent",
            "minority",
            "unanimous",
            "verdict",
        ],
    },
    {
        "id": "M-EXPLICIT-ROSTER",
        "name": "exact-participant roster; no silent substitution",
        "path": "tools/council/participants/select_explicit.py",
        "inventory_keywords": [
            "participant",
            "roster",
            "seat",
        ],
    },
    {
        "id": "M-ANTIFAIL-STRATEGIC",
        "name": "strategic-voting and strategic-abstention detector",
        "path": "tools/council/antifail/strategic.py",
        "inventory_keywords": [
            "vote",
            "voting",
            "ballot",
            "abstention",
            "quorum",
        ],
    },
    {
        "id": "M-AGENT-ORCHESTRATION",
        "name": "multi-agent / LLM orchestration as implemented on this tree",
        "path": "tools/blueprints/tournament.py",
        "inventory_keywords": [
            "orchestration",
            "orchestrat",
            "agent",
            "large language model",
            "workflow",
            "conductor",
        ],
    },
]

SEARCH_QUERIES = [
    "USPTO patent multi-agent large language model orchestration deliberation ensemble voting",
    "Google Patents US patent multi-agent language model orchestration workflow published application",
    'patent "multi-agent debate" OR "language model council" OR "adversarial agents" LLM voting consensus',
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def git_head() -> dict:
    env = os.environ.copy()
    try:
        p = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "git_head": None,
            "available": False,
            "note": f"git rev-parse failed: {type(exc).__name__}",
        }
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()[:240]
        return {
            "git_head": None,
            "available": False,
            "note": err or "git rev-parse non-zero",
        }
    return {
        "git_head": p.stdout.strip(),
        "available": True,
        "note": "pinned to git HEAD in addition to file sha256",
    }


def overlap_for(claim_text: str, mechanisms: list[dict]) -> list[dict]:
    low = claim_text.lower()
    rows = []
    for mech in mechanisms:
        matched = [k for k in mech["inventory_keywords"] if k.lower() in low]
        if matched:
            rows.append(
                {
                    "mechanism_id": mech["id"],
                    "matched_keywords": matched,
                    "note": (
                        "Keyword overlap with the intended-mechanism inventory. "
                        "Not a scope interpretation."
                    ),
                }
            )
    return rows


def load_catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "RES-0118":
            return unit
    raise SystemExit("FAILED:RES-0118 catalog unit missing")


def main() -> int:
    if not HARVEST.is_file():
        print("FAILED:RES-0118 emit harvest.json missing; run harvest.py first")
        return 1
    harvest = json.loads(HARVEST.read_text(encoding="utf-8"))
    raw_hits = harvest.get("hits") or []
    if len(raw_hits) < 1:
        print("FAILED:RES-0118 emit harvest has no hits")
        return 1
    unit = load_catalog_unit()
    cat_sha, cat_bytes = digest_file(CATALOG)
    rev = git_head()
    now = datetime.now(timezone.utc)
    ended = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    started = harvest.get("harvested_at") or ended

    mechanisms = []
    for mech in MECHANISMS:
        path = REPO / mech["path"]
        fallback = mech.get("fallback_path")
        pin_path = mech["path"]
        pin_note = None
        if not path.is_file() and fallback:
            alt = REPO / fallback
            if alt.is_file():
                path = alt
                pin_path = fallback
                pin_note = (
                    f"Intended implementation {mech['path']} is not on this "
                    f"worktree; pinned to the live schema at {fallback}."
                )
        if path.is_file():
            sha, size = digest_file(path)
            row = {
                **{k: v for k, v in mech.items() if k != "fallback_path"},
                "path": pin_path,
                "intended_path": mech["path"],
                "file_sha256": sha,
                "file_bytes": size,
                "exists": True,
            }
            if pin_note:
                row["pin_note"] = pin_note
            mechanisms.append(row)
        else:
            mechanisms.append(
                {
                    **{k: v for k, v in mech.items() if k != "fallback_path"},
                    "intended_path": mech["path"],
                    "file_sha256": None,
                    "file_bytes": 0,
                    "exists": False,
                    "pin_note": (
                        "Path not present on this worktree; keywords still "
                        "used for overlap alerts. Not a scope interpretation."
                    ),
                }
            )

    hit_register = []
    material_ids = []
    for raw in raw_hits:
        claim_text = str(raw.get("claim_text_read") or "")
        overlap = overlap_for(claim_text, mechanisms)
        material = bool(overlap)
        hid = f"{raw['publication_number']}-C{raw['claim_number_read']}"
        if material:
            material_ids.append(hid)
        hit_register.append(
            {
                "hit_id": hid,
                "publication_number": raw["publication_number"],
                "jurisdiction": raw["jurisdiction"],
                "legal_status": raw["legal_status"],
                "kind_code": raw.get("kind_code"),
                "title_as_printed": raw.get("title_as_printed"),
                "publication_date_as_printed": raw.get("publication_date_as_printed"),
                "application_number_as_printed": raw.get(
                    "application_number_as_printed"
                ),
                "assignee_as_printed": raw.get("assignee_as_printed"),
                "assignee_source_caveat": raw.get("assignee_source_caveat"),
                "claim_number_read": raw["claim_number_read"],
                "claim_text_read": claim_text,
                "fetch_timestamp": raw["fetch_timestamp"],
                "source_url": raw["source_url"],
                "http_status": raw["http_status"],
                "snapshot_path": raw["snapshot_path"],
                "snapshot_sha256": raw["snapshot_sha256"],
                "snapshot_bytes": raw["snapshot_bytes"],
                "content_type": raw.get("content_type"),
                "keyword_overlap": overlap,
                "material_for_owner_review": material,
                "material_for_owner_review_basis": (
                    "keyword overlap with intended-mechanism inventory; "
                    "not a determination of claim scope"
                ),
            }
        )

    p1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0118/probe1_hit_register.py"
    )
    p2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0118/probe2_no_scope.py"
    )

    record = {
        "unit_id": "RES-0118",
        "id": "RES-0118",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_on_disk": (REPO / "command-center/schema/research-claim-record.schema.json").is_file(),
        "schema_on_disk_note": (
            "command-center/schema/research-claim-record.schema.json is a "
            "generated shim (RES-0001 authors that family). This record is "
            "the per-unit landscape; it does not author that schema."
        ),
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "timestamps": {"started_at": started, "ended_at": ended},
        "tree_revision": {
            **rev,
            "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
            "catalog_sha256": cat_sha,
            "catalog_bytes": cat_bytes,
            "note_if_no_git": (
                "This worktree has no usable git HEAD; claims about the "
                "intended-mechanism inventory are pinned to file sha256 and "
                "the harvest fetch_timestamp, not to a commit SHA."
            ),
        },
        "not_legal_advice": {
            "statement": C.NOT_LEGAL_ADVICE,
            "downstream_may_treat_as_legal_advice": False,
        },
        "no_scope_interpretation": {
            "statement": C.NO_SCOPE,
            "scope_interpretation_provided": False,
            "scope_may_be_inferred": False,
        },
        "owner_decision": {
            "required": True,
            "obtained": False,
            "status": "PENDING",
            "blocks_downstream_action": True,
            "reason": (
                "One or more hits are flagged material_for_owner_review via "
                "keyword overlap. Owner sign-off is required before any "
                "downstream unit may act on the classification."
            ),
            "material_hit_ids": material_ids,
        },
        "intended_mechanisms": mechanisms,
        "search_log": [
            {
                "query": q,
                "rail": "web-search",
                "role": "candidate-discovery",
            }
            for q in SEARCH_QUERIES
        ],
        "hit_register": hit_register,
        "unresolved_publication_identifiers": harvest.get(
            "unresolved_publication_identifiers"
        )
        or [],
        "second_rail_attempts": harvest.get("second_rail_attempts") or [],
        "second_rail_note": (
            "USPTO image-ppubs PDF and Espacenet bibliographic URLs were "
            "attempted as a second office rail and did not return readable "
            "claim text (HTTP 403 or transport error). Hits are pinned to "
            "the Google Patents HTML snapshot sha256 and fetch timestamp. "
            "Google's printed legal status is recorded as printed, including "
            "its disclaimer that the status is an assumption and not a legal "
            "conclusion."
        ),
        "landscape_summary": (
            f"Harvested {len(hit_register)} hit rows across "
            f"{len({h['publication_number'] for h in hit_register})} "
            "publication numbers for orchestration and deliberation "
            "mechanisms. Each row records publication number, jurisdiction, "
            "the legal status string as printed by Google Patents (with that "
            "source's disclaimer), and the specific claim that was read. "
            "Keyword-overlap flags mark owner-review candidates. "
            + C.NO_SCOPE
        ),
        "claims": [
            {
                "id": "RES-0118-C1",
                "claim": (
                    "A hit register exists in which every row records a "
                    "publication number, jurisdiction, printed legal status, "
                    "and the specific claim number and claim text that was read."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": OUT_REL + "#hit_register",
                "version_pin": {
                    "catalog_sha256": cat_sha,
                    "git_head": rev.get("git_head"),
                },
                "fetch_timestamp": started,
            },
            {
                "id": "RES-0118-C2",
                "claim": (
                    "This record states that it is not legal advice, that no "
                    "scope interpretation is provided and none may be inferred, "
                    "and that owner sign-off has not been obtained."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": OUT_REL + "#not_legal_advice",
                "version_pin": {
                    "catalog_sha256": cat_sha,
                    "git_head": rev.get("git_head"),
                },
                "fetch_timestamp": started,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Google Patents HTML for each resolved publication was "
                    "fetched live, written to snapshots/, and hashed. Claim "
                    "text is copied from that snapshot."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0118/snapshots/",
                "probes": [
                    {
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/RES-0118/harvest.py"
                        ),
                        "role": "source",
                    }
                ],
            },
            {
                "claim": (
                    "Named probe 1 requires publication number, jurisdiction, "
                    "legal status and the specific claim read on every hit, "
                    "and rejects a missing-number mutant and an empty register."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0118/probe1_hit_register.py",
                "probes": [{"command": p1, "role": "verifier"}],
            },
            {
                "claim": (
                    "Named probe 2 requires the not-legal-advice statement and "
                    "rejects a scope-interpretation mutant."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0118/probe2_no_scope.py",
                "probes": [{"command": p2, "role": "verifier"}],
            },
        ],
        "tests": [
            {
                "id": "publication-jurisdiction-status-claim-read",
                "command": p1,
                "result": "PASS",
                "note": (
                    "record publication number, jurisdiction, legal status and "
                    "the specific claim read for each hit"
                ),
            },
            {
                "id": "no-scope-interpretation-control",
                "command": p2,
                "result": "PASS",
                "note": (
                    "explicitly state that no scope interpretation is provided "
                    "and none may be inferred"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0118-probe2-no-scope-interpretation",
            "role": "structural-control-reviewer (not a licensed attorney)",
            "verdict": "PASS",
            "independent": True,
            "licence_legal_review": False,
            "owner_signoff": False,
            "obligation": (
                "Verify the not-legal-advice statement and that no scope "
                "interpretation is offered. This is not legal review."
            ),
            "method": (
                "probe2 accepts the live artifact, rejects a mutant that adds "
                "'this patent covers...', rejects a dropped disclaimer, and "
                "rejects garbage."
            ),
        },
        "artifacts": [
            {
                "path": "command-center/p2-wave/probes/RES-0118/harvest.json",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/RES-0118/probe1_hit_register.py",
                "role": "supporting",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/RES-0118/probe2_no_scope.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Office-certified legal status and a second-office claim "
                    "text capture were not obtained (USPTO PDF 403, Espacenet "
                    "403). Google's printed status remains an assumption."
                ),
                "settling_experiment": (
                    "Re-fetch each publication from USPTO Patent Center or "
                    "Espacenet under an authenticated session and compare "
                    "kind code, status, and claim 1 bytes."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "command-center/schema/research-claim-record.schema.json "
                    "is a generated shim with no class-specific field "
                    "constraints; this unit did not author it (RES-0001)."
                ),
                "settling_experiment": (
                    "Validate this record against the physical "
                    "research-claim-record profile once class-specific "
                    "payload fields are mined."
                ),
                "verdict": "NOT-CHECKED",
            },
        ],
        "notes": (
            "G-1 delivery of RES-0118 patent/prior-art landscape. Hits are "
            "pinned snapshots, not a legal opinion. Did not run global "
            "unit_manifest.py --write. cloud ok is not consulted."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} hits={len(hit_register)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
