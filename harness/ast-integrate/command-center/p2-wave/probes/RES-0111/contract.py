#!/usr/bin/env python3
"""RES-0111 contract: map named DS primitives onto this program's failure classes.

The closed target list is the four classes named in the unit question, resolved
to exact catalog / seeded-class strings. A primitive that does not address one
of those four is dropped rather than fitted for elegance.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

UNIT = "RES-0111"
OUT_REL = "command-center/research/RES-0111.json"
SCHEMA_REL = "command-center/p2-wave/probes/RES-0111/research-claim-record.schema.json"
CATALOG_SCHEMA = "command-center/schema/research-claim-record.schema.json"
SEEDED = "command-center/p2-wave/probes/ARC-0005/seeded_classes.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
TST0090 = "command-center/WORK-UNIT-CATALOG.json"

SENTINEL = (
    "SUCCESS:RES-0111 in the receipt AND a primitive-to-failure-class mapping "
    "with a stated count of primitives dropped as unmapped"
)
QUESTION = (
    "Which distributed-systems primitives (idempotency keys, fencing tokens, "
    "lease expiry, exactly-once illusions, backpressure) map directly onto this "
    "program's known failure classes - duplicate dispatch, stale monitor, one "
    "hung unit blocking a batch, 429 storms?"
)

NAMED_PRIMITIVES: tuple[str, ...] = (
    "idempotency keys",
    "fencing tokens",
    "lease expiry",
    "exactly-once illusions",
    "backpressure",
)
# Detector control: a real DS primitive that is NOT on the unit's named list
# and does not address any of the four spec classes. Must be dropped.
CONTROL_UNMAPPED_PRIMITIVE = "two-phase commit"

# Closed spec list for THIS unit (question_or_target + seeded/catalog names).
SPEC_FAILURE_CLASSES: dict[str, dict[str, Any]] = {
    "duplicate-dispatch": {
        "id": "duplicate-dispatch",
        "exact_name": "duplicate-dispatch",
        "question_gloss": "duplicate dispatch",
        "seeded_fc": None,
        "why_on_list": (
            "Named in RES-0111 question_or_target and as catalog "
            "failure_classification; Phase 10 layer 23 duplicate-dispatch tests."
        ),
    },
    "FC-11315": {
        "id": "FC-11315",
        "exact_name": (
            "stall detection from mtimes alone is impossible / orchestrator death"
        ),
        "question_gloss": "stale monitor",
        "seeded_fc": 11315,
        "catalog_gloss": "monitor dies while remote work continues",
        "phase10": "stale-monitor tests (_USER-PROMPTS.md:11010)",
        "why_on_list": (
            "Question gloss 'stale monitor'; catalog 51293 binds 11315 to "
            "'monitor dies while remote work continues'; seeded_classes.py "
            "FC-11315."
        ),
    },
    "FC-11317": {
        "id": "FC-11317",
        "exact_name": "one hung unit blocks a large batch",
        "question_gloss": "one hung unit blocking a batch",
        "seeded_fc": 11317,
        "why_on_list": "Question gloss plus seeded_classes.py FC-11317.",
    },
    "FC-11318": {
        "id": "FC-11318",
        "exact_name": "429 arrival-rate storm / self-throttling",
        "question_gloss": "429 storms",
        "seeded_fc": 11318,
        "why_on_list": "Question gloss plus seeded_classes.py FC-11318.",
    },
}

PAPERS: dict[str, dict[str, Any]] = {
    "millwheel": {
        "title": (
            "MillWheel: Fault-Tolerant Stream Processing at Internet Scale"
        ),
        "authors": "Akidau et al.",
        "year": 2013,
        "venue": "PVLDB 6(11)",
        "doi": "10.14778/2536222.2536229",
        "url": "https://www.vldb.org/pvldb/vol6/p1033-akidau.pdf",
        "fetched": "2026-08-24T18:40:00Z",
        "http_status": 200,
    },
    "leases": {
        "title": (
            "Leases: An Efficient Fault-Tolerant Mechanism for "
            "Distributed File Cache Consistency"
        ),
        "authors": "Gray and Cheriton",
        "year": 1989,
        "venue": "SOSP '89",
        "doi": "10.1145/74850.74870",
        "url": (
            "https://courses.cs.duke.edu/spring15/cps210/readings/leases-sosp89.pdf"
        ),
        "fetched": "2026-08-24T18:40:00Z",
        "http_status": 200,
    },
    "bbr": {
        "title": "BBR: Congestion-Based Congestion Control",
        "authors": "Cardwell, Cheng, Gunn, Hassas Yeganeh, Jacobson",
        "year": 2016,
        "venue": "ACM Queue 14(5)",
        "doi": "10.1145/3012426.3022184",
        "url": "https://queue.acm.org/detail.cfm?id=3022184",
        "fetched": "2026-08-24T18:40:00Z",
        "http_status": 200,
    },
    "gfs": {
        "title": "The Google File System",
        "authors": "Ghemawat, Gobioff, Leung",
        "year": 2003,
        "venue": "SOSP '03",
        "doi": "10.1145/945445.945450",
        "url": "https://pdos.csail.mit.edu/6.824/papers/gfs.pdf",
        "fetched": "2026-08-24T18:40:00Z",
        "http_status": 200,
    },
}

CAPTURES: dict[str, str] = {
    "millwheel-s611": (
        "The record is checked against deduplication data from previous "
        "deliveries; duplicates are discarded. The system assigns unique IDs "
        "to all records at production time. We identify duplicate records by "
        "including this unique ID for the record in the same atomic write as "
        "the state modification. If the same record is later retried, we can "
        "compare it to the journaled ID, and discard and ACK the duplicate. "
        "This guarantee does not extend to external systems."
    ),
    "millwheel-s81": (
        "Figure 13 shows the latency distribution for records when running "
        "over 200 CPUs. Median record delay is 3.6 milliseconds and "
        "95th-percentile latency is 30 milliseconds. This test was performed "
        "with strong productions and exactly once disabled. With both of these "
        "features enabled, median latency jumps up to 33.7 milliseconds and "
        "95th-percentile latency to 93.8 milliseconds."
    ),
    "millwheel-s62": (
        "A major threat to our data consistency is the possibility of zombie "
        "writers and network remnants issuing stale writes to our backing store. "
        "To address this possibility, we attach a sequencer token to each write, "
        "which the mediator of the backing store checks for validity before "
        "allowing the write to commit. New workers invalidate any extant "
        "sequencers before starting work, so that no remnant writes can succeed "
        "thereafter."
    ),
    "leases-fig1": (
        "From Figure 1, most of the benefit of a non-zero lease term is gained "
        "by a term of just a few seconds. For example, at S = 1, a term of 10 "
        "seconds reduces the consistency traffic to 10% of that for a zero term. "
        "At a lease term of zero, consistency accounts for 30% of the server "
        "traffic in the trace, so that the actual benefit is a 27% reduction in "
        "total server traffic, to a level just 4.5% above that for infinite term."
    ),
    "bbr-fig7": (
        "Figure 7 shows one reason for switching: BBR's throughput is "
        "consistently 2 to 25 times greater than CUBIC's. Manually raising the "
        "receive buffer on one US-Europe path caused BBR immediately to reach "
        "2 Gbps, while CUBIC remained at 15 Mbps — the 133x relative "
        "improvement predicted by Mathis et al. Figure 8 shows BBR vs. CUBIC "
        "goodput for 60-second flows on a 100-Mbps/100-ms link. CUBIC's "
        "throughput decreases by 10 times at 0.1 percent loss and totally "
        "stalls above 1 percent. BBR meets this limit up to a 5 percent loss."
    ),
    "gfs-s31": (
        "The lease mechanism is designed to minimize management overhead at "
        "the master. A lease has an initial timeout of 60 seconds. Even if "
        "the master loses communication with a primary, it can safely grant a "
        "new lease to another replica after the old lease expires. Whenever "
        "the master grants a new lease on a chunk, it increases the chunk "
        "version number and informs the up-to-date replicas."
    ),
}


def capture_digest(key: str) -> str:
    body = CAPTURES[key].encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def source_lineage(paper_key: str, capture_key: str) -> dict[str, Any]:
    p = PAPERS[paper_key]
    return {
        "paper": paper_key,
        "title": p["title"],
        "doi": p["doi"],
        "url": p["url"],
        "fetched": p["fetched"],
        "http_status": p["http_status"],
        "capture_key": capture_key,
        "snapshot_sha256": capture_digest(capture_key),
    }


def _row(
    primitive: str,
    decision: str,
    failure_class_id: str | None,
    reason: str,
    *,
    promoted: bool,
    evidence_tier: str,
    paper_key: str | None = None,
    section_or_figure: str | None = None,
    effect_size: str | None = None,
    baseline: str | None = None,
    capture_key: str | None = None,
    strongest_caveat: str,
) -> dict[str, Any]:
    fc = SPEC_FAILURE_CLASSES.get(failure_class_id) if failure_class_id else None
    paper = PAPERS[paper_key] if paper_key else None
    return {
        "primitive": primitive,
        "decision": decision,
        "failure_class_id": failure_class_id,
        "failure_class_exact_name": None if fc is None else fc["exact_name"],
        "question_gloss": None if fc is None else fc["question_gloss"],
        "reason": reason,
        "promoted": promoted,
        "evidence_tier": evidence_tier,
        "doi": None if paper is None else paper["doi"],
        "arxiv_id": None,
        "section_or_figure": section_or_figure,
        "effect_size": effect_size,
        "baseline": baseline,
        "paper_key": paper_key,
        "capture_key": capture_key,
        "source_lineage": (
            None
            if paper_key is None or capture_key is None
            else source_lineage(paper_key, capture_key)
        ),
        "strongest_caveat": strongest_caveat,
    }


def mapping_rows() -> list[dict[str, Any]]:
    """One row per named primitive. Source of truth for emit and probes."""
    return [
        _row(
            "idempotency keys",
            "MAPPED",
            "duplicate-dispatch",
            (
                "MillWheel §6.1.1 unique record IDs journaled in the same atomic "
                "write as state; retried deliveries with the same ID are discarded. "
                "That is an idempotency key on dispatch. This program's duplicate-"
                "dispatch class is the same shape: a second dispatch of one unit "
                "must not produce a second receipt."
            ),
            promoted=True,
            evidence_tier="E2",
            paper_key="millwheel",
            section_or_figure="Section 8.1 / Figure 13",
            effect_size=(
                "exactly-once + strong productions ON: median 33.7 ms, "
                "p95 93.8 ms (200 CPUs)"
            ),
            baseline=(
                "same pipeline with exactly-once and strong productions OFF: "
                "median 3.6 ms, p95 30 ms"
            ),
            capture_key="millwheel-s81",
            strongest_caveat=(
                "The paired number is latency cost of the dedup envelope, not a "
                "counted reduction in duplicate dispatches. §6.1.1 is structural; "
                "it reports no duplicate-discard count. Transfer to this estate is "
                "unmeasured."
            ),
        ),
        _row(
            "fencing tokens",
            "MAPPED",
            "FC-11315",
            (
                "MillWheel §6.2 sequencer tokens reject stale writes from zombie "
                "workers after an interval moves. GFS chunk version numbers rise "
                "on each new lease so a stale replica cannot serve. TST-0090 "
                "requires a monotonically increasing fencing token so a thawed "
                "original dispatcher cannot commit after reclaim. That is the "
                "stale-monitor / 11315 class."
            ),
            promoted=False,
            evidence_tier="E3",
            paper_key="millwheel",
            section_or_figure="Section 6.2",
            effect_size=None,
            baseline=None,
            capture_key="millwheel-s62",
            strongest_caveat=(
                "Headline mechanism without a reported zombie-write rejection "
                "count versus an unfenced baseline. E3: mapped, not promoted."
            ),
        ),
        _row(
            "lease expiry",
            "MAPPED",
            "FC-11315",
            (
                "Gray & Cheriton: an unreachable leaseholder blocks writers only "
                "until the term expires. GFS §3.1: after a 60 s chunk lease "
                "expires the master may grant a new primary. TST-0090: when the "
                "dispatcher holding a unit lease dies, reclaim is allowed only "
                "after expiry. That is monitor/dispatcher death (11315), not "
                "the 11317 live-hang barrier."
            ),
            promoted=True,
            evidence_tier="E2",
            paper_key="leases",
            section_or_figure="Section 3 / Figure 1",
            effect_size=(
                "S=1, 10 s term: consistency traffic is 10% of zero-term; "
                "total server traffic 27% below zero-term and 4.5% above "
                "infinite-term"
            ),
            baseline=(
                "zero-term lease (callback on every access); infinite-term as "
                "the other bound. Trace: consistency is 30% of server traffic "
                "at zero term"
            ),
            capture_key="leases-fig1",
            strongest_caveat=(
                "Gray numbers are V-system file-cache consistency traffic, not "
                "orchestrator reclaim latency. This program's 11317 (hung unit "
                "blocks a batch) is assigned by the catalog to per-unit pipelines, "
                "not to leases; lease is bound here to 11315 per TST-0090."
            ),
        ),
        _row(
            "exactly-once illusions",
            "DROPPED",
            None,
            (
                "MillWheel §6.1.1: the exactly-once guarantee does not extend to "
                "external systems. This program's artifacts are external JSON "
                "files. Framework exactly-once is at-least-once plus idempotent "
                "sinks — the idempotency-key primitive already mapped. Treating "
                "the illusion as a fifth distinct mapping would be elegance."
            ),
            promoted=False,
            evidence_tier="E3",
            paper_key="millwheel",
            section_or_figure="Section 6.1.1",
            effect_size=None,
            baseline=None,
            capture_key="millwheel-s611",
            strongest_caveat=(
                "Dropped as unmapped-as-distinct-primitive. §8.1 latency numbers "
                "belong to the idempotency-key envelope already promoted, not to "
                "a second class mapping."
            ),
        ),
        _row(
            "backpressure",
            "MAPPED",
            "FC-11318",
            (
                "BBR is sender-side admission that slows when the path is "
                "saturated instead of bursting into loss. FC-11318 is a 429 "
                "arrival-rate storm: naive fan-out bursts into provider quota. "
                "The shared primitive is backpressure / admission control with "
                "a measured competing baseline (CUBIC)."
            ),
            promoted=True,
            evidence_tier="E2",
            paper_key="bbr",
            section_or_figure="Figure 7 and Figure 8",
            effect_size=(
                "B4 production: BBR throughput 2–25× CUBIC; one US-Europe path "
                "BBR 2 Gbps vs CUBIC 15 Mbps (133×). Figure 8: BBR holds the "
                "(1-lossRate) limit up to 5% random loss"
            ),
            baseline=(
                "CUBIC on the same B4 prober (8 MB every minute) and on the "
                "100 Mbps / 100 ms lab link; CUBIC drops 10× at 0.1% loss and "
                "stalls above 1%"
            ),
            capture_key="bbr-fig7",
            strongest_caveat=(
                "BBR measures TCP goodput, not HTTP 429 counts on this estate. "
                "The mapping is structural (admission vs burst), not a measured "
                "429-storm close."
            ),
        ),
    ]


def classify(primitive: str) -> dict[str, Any]:
    """Map one primitive. Unknown primitives drop (no elegance fit)."""
    for row in mapping_rows():
        if row["primitive"] == primitive:
            return {
                "primitive": primitive,
                "decision": row["decision"],
                "failure_class_id": row["failure_class_id"],
            }
    return {
        "primitive": primitive,
        "decision": "DROPPED",
        "failure_class_id": None,
    }


def dropped_unmapped_count(rows: list[dict[str, Any]] | None = None) -> int:
    rows = mapping_rows() if rows is None else rows
    return sum(1 for r in rows if r["decision"] == "DROPPED")


def promoted_ok(row: dict[str, Any]) -> tuple[bool, str]:
    """A mechanism may be promoted only with DOI/section + effect AND baseline."""
    if not row.get("promoted"):
        return True, "not-promoted"
    missing = [
        k
        for k in ("doi", "section_or_figure", "effect_size", "baseline")
        if not str(row.get(k) or "").strip()
    ]
    if missing:
        return False, "headline-without-baseline:" + ",".join(missing)
    if str(row.get("evidence_tier") or "") == "E3":
        return False, "E3-cannot-promote"
    if row.get("decision") != "MAPPED":
        return False, "dropped-cannot-promote"
    fc = row.get("failure_class_id")
    if fc not in SPEC_FAILURE_CLASSES:
        return False, "promoted-onto-non-spec-class"
    return True, "ok"


def check_mapping_table(rows: list[dict[str, Any]]) -> tuple[bool, str]:
    named = [r.get("primitive") for r in rows]
    if named != list(NAMED_PRIMITIVES):
        return False, f"primitive-set {named}"
    live = {r["primitive"]: classify(r["primitive"]) for r in rows}
    for r in rows:
        c = live[r["primitive"]]
        if r.get("decision") != c["decision"]:
            return False, f"decision-drift {r['primitive']}"
        if r.get("failure_class_id") != c["failure_class_id"]:
            return False, f"class-drift {r['primitive']}"
        if r["decision"] == "MAPPED":
            if r.get("failure_class_id") not in SPEC_FAILURE_CLASSES:
                return False, f"mapped-off-list {r['primitive']}"
            exact = SPEC_FAILURE_CLASSES[r["failure_class_id"]]["exact_name"]
            if r.get("failure_class_exact_name") != exact:
                return False, f"inexact-class-name {r['primitive']}"
        elif r["decision"] == "DROPPED":
            if r.get("failure_class_id") is not None:
                return False, f"dropped-but-classed {r['primitive']}"
        else:
            return False, f"bad-decision {r['decision']}"
        ok, why = promoted_ok(r)
        if not ok:
            return False, f"{r['primitive']}:{why}"
    n_drop = dropped_unmapped_count(rows)
    if n_drop < 1:
        return False, "dropped-count-zero-control-missing"
    ctrl = classify(CONTROL_UNMAPPED_PRIMITIVE)
    if ctrl["decision"] != "DROPPED" or ctrl["failure_class_id"] is not None:
        return False, "control-2pc-not-dropped"
    mapped_ids = {r["failure_class_id"] for r in rows if r["decision"] == "MAPPED"}
    if "FC-11317" in mapped_ids:
        return False, "elegance-fit-11317"
    return True, f"ok dropped={n_drop}"


def e3_fixture(row: dict[str, Any]) -> dict[str, Any]:
    """Headline number without baseline: must not promote."""
    mutant = json.loads(json.dumps(row))
    mutant["baseline"] = None
    mutant["promoted"] = True
    mutant["evidence_tier"] = "E3"
    return mutant


def both_states() -> dict[str, Any]:
    rows = mapping_rows()
    ok, why = check_mapping_table(rows)
    ctrl = classify(CONTROL_UNMAPPED_PRIMITIVE)
    known = classify("idempotency keys")
    e3 = e3_fixture(rows[0])
    e3_ok, e3_why = promoted_ok(e3)
    forged = json.loads(json.dumps(rows))
    for r in forged:
        if r["primitive"] == "exactly-once illusions":
            r["decision"] = "MAPPED"
            r["failure_class_id"] = "duplicate-dispatch"
            r["failure_class_exact_name"] = SPEC_FAILURE_CLASSES[
                "duplicate-dispatch"
            ]["exact_name"]
            r["promoted"] = True
            r["evidence_tier"] = "E2"
            r["effect_size"] = "placeholder"
            r["baseline"] = "placeholder"
            r["doi"] = PAPERS["millwheel"]["doi"]
            r["section_or_figure"] = "Section 8.1"
    forged_ok, forged_why = check_mapping_table(forged)
    return {
        "good_table_ok": ok,
        "good_why": why,
        "control_2pc_dropped": ctrl["decision"] == "DROPPED",
        "known_idempotency_mapped": (
            known["decision"] == "MAPPED"
            and known["failure_class_id"] == "duplicate-dispatch"
        ),
        "e3_without_baseline_rejected": (not e3_ok),
        "e3_why": e3_why,
        "elegance_exactly_once_rejected": (not forged_ok),
        "elegance_why": forged_why,
        "dropped_unmapped_count": dropped_unmapped_count(rows),
    }
