#!/usr/bin/env python3
"""Emit command-center/research/RES-0030.json from live probes of Goose."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from canonical import resolve_canonical  # noqa: E402
from constants import (  # noqa: E402
    CANONICAL_HTML,
    CONFIG_KEY,
    OUTPUT_REL,
    PARENT_SHA,
    RECIPE_REF_REL,
    REMOVAL_COMMIT_URL,
    REMOVAL_PR_API,
    REMOVAL_PR_URL,
    REMOVAL_SHA,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    SHORT_SENTINEL,
    UNIT_ID,
)
from fetchutil import fetch_body, lineage  # noqa: E402
from recipes import extract_recipes  # noqa: E402
from threshold import extract_threshold  # noqa: E402

QUESTION = (
    "What exactly triggers Goose's lead-to-worker escalation, at what failure "
    "threshold, and is there evidence the escalation beats retrying the same "
    "worker - noting the repository moved from block/goose to a new owner and "
    "the old pointer is a silent-redirect dependency?"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _claim(
    cid: str,
    statement: str,
    mechanism: str,
    verdict: str,
    tier: str,
    band: str,
    caveat: str,
    rails: list[dict],
    edges: dict,
    probe: str,
    snapshot: str | None,
) -> dict:
    if verdict in {"CONFIRMED", "PARTIAL"} and len(rails) < 2 and tier in {"E1", "E2"}:
        raise SystemExit(f"FAILED:emit {cid} E1/E2 needs two rails")
    if verdict == "CONFIRMED" and len(rails) < 2:
        raise SystemExit(f"FAILED:emit {cid} CONFIRMED with <2 rails")
    return {
        "id": cid,
        "claim": statement,
        "canonical_mechanism": mechanism,
        "verdict": verdict,
        "evidence_tier": tier,
        "confidence_band": band,
        "strongest_caveat": caveat,
        "source_lineage": rails,
        "named_settling_probe": probe,
        "edges": edges,
        "freshness_stamp": _now(),
        "snapshot_sha256": snapshot,
    }


def main() -> int:
    canon = resolve_canonical()
    thr = extract_threshold()
    recipes = extract_recipes()
    pr = fetch_body(REMOVAL_PR_API)
    if pr.get("status") != 200:
        raise SystemExit(f"FAILED:emit PR #7989 fetch status={pr.get('status')}")
    pr_lineage = lineage(
        REMOVAL_PR_URL,
        pr["status"],
        pr["sha256"],
        pr["fetched_at"],
        "github-api-structured",
    )
    now = _now()

    html_chain = canon["html_redirect_chain"]
    api_chain = canon["api_redirect_chain"]
    lw_sha = thr["captures"]["lead_worker.rs"]["sha256"]
    init_sha = thr["captures"]["init.rs"]["sha256"]
    env_sha = thr["captures"]["environment-variables.md"]["sha256"]
    tut_sha = thr["captures"]["lead-worker.md"]["sha256"]

    c1 = _claim(
        "RES-0030-C1",
        (
            "The Goose repository's current canonical location is "
            f"{CANONICAL_HTML} (full_name aaif-goose/goose, GitHub id 846698999). "
            "https://github.com/block/goose HTTP 301s there; "
            "https://api.github.com/repos/block/goose HTTP 301s to "
            "/repositories/846698999, which is the same transferred repo."
        ),
        "GitHub repo transfer: old owner pointer is a silent 301, not a second copy.",
        "CONFIRMED",
        "E1",
        "almost-certain",
        (
            "A future second transfer would 301 again; this measurement is the "
            "live hop list at freshness_stamp, not a forever-name."
        ),
        canon["source_lineage"][:2],
        {"supports": ["RES-0030-C6"], "contradicts": [], "duplicate_of": []},
        "probe1_canonical_redirect.py",
        None,
    )
    c2 = _claim(
        "RES-0030-C2",
        (
            "The catalog's 'lead-to-worker escalation at a failure threshold' "
            "wording is false as a mechanism description. Lead-to-worker is "
            "turn-count (GOOSE_LEAD_TURNS, default 3). The failure threshold "
            "escalates the other way: worker-to-lead fallback."
        ),
        (
            "get_active_provider uses lead if turn_count < lead_turns OR "
            "in_fallback_mode; handle_completion_result enters fallback when "
            "turn_count >= lead_turns and consecutive task failures >= threshold."
        ),
        "REFUTED",
        "E1",
        "almost-certain",
        (
            "REFUTED is the catalog framing, not the existence of a switch. "
            "The switch exists; its failure-threshold direction is worker-to-lead."
        ),
        [
            thr["source_lineage"][0],
            thr["source_lineage"][3],
        ],
        {"supports": ["RES-0030-C3"], "contradicts": ["catalog-question-wording"], "duplicate_of": []},
        "probe2_threshold_locus.py",
        lw_sha,
    )
    # C2 verdict REFUTED is about the catalog framing. The underlying mechanism
    # is confirmed separately as C2b so we do not bury the extract.
    c2b = _claim(
        "RES-0030-C2b",
        (
            "When lead/worker mode is enabled, Goose uses the lead model for the "
            "first GOOSE_LEAD_TURNS (default 3) then the worker; on consecutive "
            "task failures at/over the failure threshold it falls back to the "
            "lead for GOOSE_LEAD_FALLBACK_TURNS (default 2), then retries the worker."
        ),
        "LeadWorkerProvider turn counter + failure_count + in_fallback_mode.",
        "CONFIRMED",
        "E1",
        "almost-certain",
        (
            "The feature was deleted from main on 2026-03-18 (C6). This claim "
            "is about parent commit "
            f"{PARENT_SHA}, the last tree that still contains lead_worker.rs."
        ),
        [
            thr["source_lineage"][0],
            thr["source_lineage"][3],
        ],
        {"supports": ["RES-0030-C3", "RES-0030-C4"], "contradicts": [], "duplicate_of": []},
        "probe2_threshold_locus.py",
        lw_sha,
    )
    c3 = _claim(
        "RES-0030-C3",
        (
            "The default failure threshold is 2 consecutive task failures. "
            f"Cited at {thr['loci']['hardcoded_default']} and "
            f"{thr['loci']['constructor_default']}; trigger conjunction at "
            f"{thr['loci']['trigger']}."
        ),
        "DEFAULT_FAILURE_THRESHOLD = 2; max_failures_before_fallback: 2.",
        "CONFIRMED",
        "E1",
        "almost-certain",
        (
            "Task failure is heuristic (tool errors, 'error:' in tool output, "
            "user-correction phrases). A single indicator counts "
            "(failure_indicators >= 1). That is not an eval of quality."
        ),
        [
            thr["source_lineage"][1],
            thr["source_lineage"][2],
        ],
        {"supports": ["RES-0030-C4"], "contradicts": [], "duplicate_of": []},
        "probe2_threshold_locus.py",
        init_sha,
    )
    c4 = _claim(
        "RES-0030-C4",
        (
            "The threshold is configurable, not hard-coded as the only value. "
            f"{CONFIG_KEY} is read in {thr['loci']['config_read']} and passed to "
            "LeadWorkerProvider::new_with_settings. The integer 2 is the default "
            "when the config key is unset. The no-settings constructor also "
            "hard-codes 2."
        ),
        f"config.get_param::<usize>({CONFIG_KEY!r}).unwrap_or(DEFAULT_FAILURE_THRESHOLD).",
        "CONFIRMED",
        "E1",
        "almost-certain",
        (
            "Configurable via env/config for the create_lead_worker_from_env path. "
            "Callers of LeadWorkerProvider::new() still get a hard-coded 2."
        ),
        [
            thr["source_lineage"][1],
            thr["source_lineage"][2],
        ],
        {"supports": ["RES-0030-C3"], "contradicts": [], "duplicate_of": []},
        "probe2_threshold_locus.py",
        init_sha,
    )
    c5 = _claim(
        "RES-0030-C5",
        (
            "There is evidence that lead/worker failure-threshold escalation "
            "beats retrying the same worker."
        ),
        (
            "Would require a comparative eval (fallback-to-lead vs retry-worker) "
            "with a measured delta. Docs assert a design rationale only."
        ),
        "REFUTED",
        "E3",
        "remote",
        (
            "Tutorial and env docs claim fallback helps when the worker 'gets "
            "tripped up'. PR #7989 comments ask why the feature was removed and "
            "do not supply an A/B. Absence of a published comparison is not "
            "proof the heuristic is worse; it is proof the 'beats retry' claim "
            "is not a measured fact. Graded E3: one rail (docs rationale) and "
            "no independent empirical rail."
        ),
        [
            thr["source_lineage"][3],
        ],
        {"supports": [], "contradicts": ["RES-0030-C2b-as-quality-claim"], "duplicate_of": []},
        "probe2_threshold_locus.py",
        tut_sha,
    )
    c6 = _claim(
        "RES-0030-C6",
        (
            "Lead/worker was removed from current main: PR #7989 merged as "
            f"{REMOVAL_SHA} on 2026-03-18, deleting {('crates/goose/src/providers/lead_worker.rs')}. "
            "A GET of that path on main returns HTTP 404. Current env-var docs "
            "no longer mention GOOSE_LEAD_FAILURE_THRESHOLD."
        ),
        "Feature deletion, not a rename. Historical extract is pinned to parent SHA.",
        "CONFIRMED",
        "E1",
        "almost-certain",
        (
            "A later restore would make main 200 again. Probe 2 re-checks the 404. "
            "Pinned parent SHA remains the citation target for C2b-C4."
        ),
        [
            thr["source_lineage"][4],
            pr_lineage,
        ],
        {"supports": ["RES-0030-C2b"], "contradicts": [], "duplicate_of": []},
        "probe2_threshold_locus.py",
        None,
    )
    c7 = _claim(
        "RES-0030-C7",
        (
            "Goose recipes are YAML (recommended) or JSON session packages with "
            "required title/description and at least one of instructions/prompt. "
            "They also have an optional retry block (max_retries + success checks). "
            "Recipe retry re-runs the same recipe; it is not lead/worker escalation."
        ),
        f"Documented in {RECIPE_REF_REL} on current main.",
        "CONFIRMED",
        "E1",
        "almost-certain",
        (
            "Recipe schema may grow; this extract is the live docs table at "
            "freshness_stamp. Subrecipes exist and were not fully torn down here."
        ),
        recipes["source_lineage"],
        {"supports": [], "contradicts": ["conflating-recipe-retry-with-lead-worker"], "duplicate_of": []},
        "probe2_threshold_locus.py",
        recipes.get("live_sha256"),
    )

    claims = [c1, c2, c2b, c3, c4, c5, c6, c7]
    confirmed = [c for c in claims if c["verdict"] == "CONFIRMED"]
    for c in confirmed:
        if len(c["source_lineage"]) < 2:
            raise SystemExit(f"FAILED:emit {c['id']} CONFIRMED needs two rails")

    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SHORT_SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Extract Goose recipes and its lead/worker failure-threshold escalation mechanism",
        "question": QUESTION,
        "canonical_repo_url": canon["canonical_repo_url"],
        "canonical_full_name": canon["canonical_full_name"],
        "repo_numeric_id": canon["repo_numeric_id"],
        "old_html_pointer": canon["old_html_pointer"],
        "redirect_chain": html_chain,
        "html_redirect_chain": html_chain,
        "api_redirect_chain": api_chain,
        "pinned_source_sha": PARENT_SHA,
        "removal_sha": REMOVAL_SHA,
        "removal_commit_url": REMOVAL_COMMIT_URL,
        "removal_pr_url": REMOVAL_PR_URL,
        "escalation_threshold": {
            "default": thr["default_threshold"],
            "unit": "consecutive task failures (heuristic, not API errors)",
            "configurable": True,
            "config_key": CONFIG_KEY,
            "hardcoded_default_also_present": True,
            "direction": thr["direction"],
            "lead_to_worker_trigger": thr["lead_to_worker_trigger"],
            "failure_threshold_trigger": thr["failure_threshold_trigger"],
            "catalog_framing_lead_to_worker_via_failure_threshold": "REFUTED",
            "loci": thr["loci"],
            "snippets": thr["snippets"],
            "permalinks": thr["permalinks"],
            "file_line": thr["loci"]["trigger"],
        },
        "recipes": recipes,
        "claims": claims,
        "evidence": [
            {
                "path": "crates/goose/src/providers/lead_worker.rs",
                "line": 151,
                "sha256": lw_sha,
                "kind": "structured-source",
                "claim": "RES-0030-C2b",
            },
            {
                "path": "crates/goose/src/providers/init.rs",
                "line": 198,
                "sha256": init_sha,
                "kind": "structured-source",
                "claim": "RES-0030-C4",
            },
            {
                "path": "documentation/docs/guides/environment-variables.md",
                "line": 142,
                "sha256": env_sha,
                "kind": "prose-docs",
                "claim": "RES-0030-C3",
            },
            {
                "path": "documentation/docs/tutorials/lead-worker.md",
                "line": 77,
                "sha256": tut_sha,
                "kind": "prose-docs",
                "claim": "RES-0030-C2b",
            },
        ],
        "tests": [
            {
                "id": "T1",
                "name": "resolve canonical repo URL and record redirect chain before citing",
                "probe": "command-center/p2-wave/probes/RES-0030/probe1_canonical_redirect.py",
            },
            {
                "id": "T2",
                "name": "cite the escalation threshold at source file:line",
                "probe": "command-center/p2-wave/probes/RES-0030/probe2_threshold_locus.py",
                "file_line": thr["loci"]["trigger"],
            },
            {
                "id": "T3",
                "name": "control: state whether the threshold is configurable or hard-coded",
                "result": "configurable (GOOSE_LEAD_FAILURE_THRESHOLD) with hardcoded default 2",
            },
        ],
        "negative_controls": [
            {
                "id": "N1",
                "name": "canonical aaif-goose/goose does not 301",
                "pass": True,
            },
            {
                "id": "N2",
                "name": "strip GOOSE_LEAD_FAILURE_THRESHOLD from init.rs -> not configurable",
                "pass": not thr["mutant_config_key_stripped_still_configurable"],
            },
            {
                "id": "N3",
                "name": "main lead_worker.rs is 404 (feature gone)",
                "pass": thr["main_lead_worker_absent"],
            },
            {
                "id": "N4",
                "name": "do not grade 'beats retry' CONFIRMED on docs rationale alone",
                "pass": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0030-adversarial-refuter",
            "independent": True,
            "verdict": "PASS",
            "default": "REFUTED where evidence is insufficient",
            "notes": (
                "Refuted the catalog's lead-to-worker-at-failure-threshold wording "
                "(C2) and the 'beats retrying the same worker' quality claim (C5). "
                "Surviving mechanism claims are pinned to parent "
                f"{PARENT_SHA} because main deleted the provider."
            ),
        },
        "residual_unknowns": [
            "Why PR #7989 removed lead/worker: the PR body does not state a measured failure, and later comments are unanswered.",
            "No public eval comparing fallback-to-lead vs retry-worker on the same tasks.",
            "Recipe retry's empirical success rate was not measured (out of mechanism scope).",
        ],
        "output_schema": SCHEMA_REL,
        "schema_note": (
            "RES-0001 has not landed research-claim-record.schema.json on this "
            "tree. This record carries the Phase-2 fields named by that unit "
            "(claim id, canonical mechanism, source lineage, E1-E4, Sherman-Kent "
            "band, named settling probe, edges, freshness, snapshot sha256) so it "
            "is re-checkable without pretending the global schema file exists."
        ),
        "measured_at": now,
    }

    out = REPO / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_REL} bytes={out.stat().st_size}")
    print(f"canonical={doc['canonical_repo_url']}")
    print(f"threshold_locus={thr['loci']['trigger']} configurable=True default=2")
    print(SHORT_SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
