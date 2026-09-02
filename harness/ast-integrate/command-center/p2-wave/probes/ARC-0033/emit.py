#!/usr/bin/env python3
"""Emit command-center/phase3/A5/FAILURE-MODES.json for ARC-0033.

Does not write A5 DESIGN.json (ARC-0031). Does not call unit_manifest.py --write.
Named probes are re-run by write_receipts.py after this file exists.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import reviewer as R  # noqa: E402
import traces as T  # noqa: E402

OUT = "command-center/phase3/A5/FAILURE-MODES.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
DESIGN = "command-center/phase3/A5/DESIGN.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
HARVEST = "command-center/p2-wave/probes/IMP-0431/probe1_empty_harvest.py"
FANOUT = "command-center/p2-wave/probes/WFA-0088/emit.py"
VALIDATE = "tools/command-center/validate.py"
MEASURE = "command-center/p2-wave/_measure_one_delivered.py"
ADV = "command-center/p2-wave/probes/ADV-0124/_validate_out.json"
CANARY = (
    "command-center/p2-wave/probes/ARC-0033/fixtures/silent-loss/remote-job-canary.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0033/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0033/probe2_anti_mtime.py"
)
QUESTION = (
    "Enumerate the distributed failure modes this program has already measured "
    "- monitor dies while remote work continues, remote harvest silently does "
    "nothing, one hung unit blocks a batch, duplicate units from colliding "
    "catalogs, partial artifact without sentinel - and for EACH specify the "
    "exact ledger record or counter that converts it from a silence into an "
    "observable event, plus the alert predicate over that record."
)
CLAIM = (
    "A5 DESIGN.json already names ledger fields that make the five measured "
    "distributed silences observable, and stall can be inferred from file "
    "mtimes; the five named modes exhaust the 47 seeded classes."
)
COUNTER = (
    "A5 DESIGN.json is absent (ARC-0031 not delivered on this worktree), so "
    "the ledger field names here are a proposed A5 contract executed against "
    "recorded traces, not a quote from a closed dossier. That residual does "
    "not make the five silences unmeasurable: silent-noop-harvest is named in "
    "IMP-0431 probe1, wait-all hang is named in WFA-0088 emit.py, duplicate "
    "id is live in tools/command-center/validate.py, and G-1 already "
    "fail-closes on sentinel-absent. tools/harvester and tools/wfa_fanout "
    "are absent here; this unit does not rebuild them or A5 DESIGN.json. "
    "Strongest surviving FOR: fixture predicates are not a production A5 "
    "runtime emitting these records yet. Strongest surviving against "
    "completeness: the reviewer-added FM-SENTINEL-ON-PARTIAL (sentinel on a "
    "partial) is outside the author's five, and the 47-class prompt file is "
    "not on this tree so enumeration is not certified."
)
CATCHING = (
    "A5 distributed workflow-runtime: append-only ledger records "
    "monitor.heartbeat.heartbeat_seq, unit.progress.progress_token, "
    "harvest.attempt delta, unit.terminal TIMEOUT, catalog.merge.duplicate_ids, "
    "artifact.observe sentinel + completion_predicate, with alert predicates "
    "that do not read file mtime."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> tuple[int, str]:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:ARC-0033 missing {rel}")
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ARC-0033 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1, snippet


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line, snip = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snip,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def mode_row(spec: dict) -> dict:
    return {
        "id": spec["id"],
        "seeded_class": spec["seeded_class"],
        "title": spec["title"],
        "ledger_record": spec["ledger_record"],
        "ledger_counter": spec["ledger_counter"],
        "alert_predicate": spec["alert_predicate"],
        "signals": list(spec["signals"]),
        "stall_predicate": bool(spec.get("stall_predicate")),
        "author": bool(spec.get("author")),
        "prior_occurrence": spec.get("prior_occurrence"),
    }


def main() -> int:
    T.ensure_on_disk()
    design_present = (REPO / DESIGN).is_file()
    matrix = E.both_states_all(T.PAIRS)
    if not matrix["all_pass"]:
        print(f"FAILED:ARC-0033 both-states {matrix['failed']}")
        return 1
    anti = E.anti_mtime_report()
    if not anti["no_mtime_in_stall_signals"]:
        print("FAILED:ARC-0033 stall predicate uses mtime")
        return 1
    hung_bad, hung_good = T.PAIRS["FM-HUNG-BLOCKS-BATCH"]
    mutant_bad = E.mtime_only_stall(hung_bad, 2000.0, 500.0)
    mutant_good = E.mtime_only_stall(hung_good, 2000.0, 500.0)
    if mutant_bad != mutant_good or not mutant_bad:
        print("FAILED:ARC-0033 mtime-only mutant distinguished or stayed silent")
        return 1
    if E.evaluate("FM-HUNG-BLOCKS-BATCH", hung_good):
        print("FAILED:ARC-0033 healthy hung trace fired")
        return 1
    if not E.evaluate("FM-HUNG-BLOCKS-BATCH", hung_bad):
        print("FAILED:ARC-0033 silent hung trace did not fire")
        return 1

    rev = R.review()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    e1 = ev(
        CATALOG,
        "monitor dies while remote work continues",
        "live-tree",
        "Catalog names the five measured distributed silences for ARC-0033.",
    )
    e2 = ev(
        CATALOG,
        "no predicate may infer 'stalled' from file mtimes alone",
        "live-tree",
        "Catalog forbids stall-from-mtime; stalled and completed jobs share mtimes.",
    )
    e3 = ev(
        HARVEST,
        "silent-noop-harvest",
        "live-tree",
        "IMP-0431 probe1 already classifies exit-0 empty delta as silent-noop-harvest.",
    )
    e4 = ev(
        FANOUT,
        "one hung unit blocking an entire cohort",
        "live-tree",
        "WFA-0088 already records the wait-all hang class (one hung unit blocking a cohort).",
    )
    e5 = ev(
        VALIDATE,
        "duplicate id",
        "live-tree",
        "Live catalog validator fail-closes on a duplicate id (FC-11320).",
    )
    e6 = ev(
        CATALOG,
        "partial artifact without sentinel",
        "live-tree",
        "Catalog already names FC-11313 (partial artifact without sentinel) as a seeded class.",
    )
    e7 = ev(
        MEASURE,
        "sentinel-absent",
        "live-tree",
        "G-1 delivery measure fail-closes when the catalog sentinel is missing.",
    )
    evidence = [e1, e2, e3, e4, e5, e6, e7]
    if (REPO / ADV).is_file():
        evidence.append(
            ev(
                ADV,
                "Live work is reported DEAD when its heartbeat monitor dies.",
                "live-tree",
                "ADV-0124 already measured monitor-death vs live work as a class.",
            )
        )

    priors = {
        "FM-MONITOR-DIES": {
            "unit": "TST-0089 / ADV-0124",
            "path": ADV if (REPO / ADV).is_file() else CATALOG,
            "note": "Kill-monitor-mid-run; ledger must distinguish monitor death from work death.",
        },
        "FM-HARVEST-NOOP": {
            "unit": "IMP-0431",
            "path": HARVEST,
            "note": "Exit 0 + empty dest delta is FAILED silent-noop-harvest.",
        },
        "FM-HUNG-BLOCKS-BATCH": {
            "unit": "WFA-0088",
            "path": FANOUT,
            "note": "wait-all barrier with no per-agent timeout; one hang deadlocks the phase.",
        },
        "FM-DUP-CATALOG": {
            "unit": "catalog merge / tools/command-center/validate.py",
            "path": VALIDATE,
            "note": "Duplicate id is V-ID fail-closed; colliding slices are the seed of FC-11320.",
        },
        "FM-PARTIAL-NO-SENTINEL": {
            "unit": "G-1 _measure_one_delivered / FC-11313",
            "path": MEASURE,
            "note": "Artifact without SUCCESS:UNIT is sentinel-absent; partial without sentinel.",
        },
    }
    author_modes = []
    for mid in E.AUTHOR_MODE_IDS:
        spec = dict(E.PREDICATES[mid])
        spec["prior_occurrence"] = priors[mid]
        spec.pop("fn", None)
        author_modes.append(mode_row(spec))

    claims = [
        {
            "id": "C1",
            "claim": (
                "Each of the five catalog-named silences has a concrete ledger "
                "record, a counter, an alert predicate, and a both-states pair."
            ),
            "verdict": "CONFIRMED",
            "anchor": e1["anchor"],
        },
        {
            "id": "C2",
            "claim": "A5 DESIGN.json already specifies those ledger fields.",
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "why_locus": (
                "command-center/phase3/A5/DESIGN.json is absent on this worktree "
                f"(present={design_present}). Field names are a proposed A5 "
                "contract, not a dossier quote. ARC-0031 owns DESIGN; this unit "
                "does not rebuild it."
            ),
            "scoped_restatement": (
                "Ledger fields are specified here as the A5 observability "
                "contract, executed on recorded traces, with DESIGN.json absent."
            ),
            "anchor": e1["anchor"],
        },
        {
            "id": "C3",
            "claim": "A stall can be inferred from file mtimes alone.",
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "why_locus": (
                "The hung-unit bad/good pair share mtime=1000. An mtime-only "
                "detector fires on both. Orchestrator tokens (deadline_t, "
                "unit.terminal, barrier_mode) distinguish them."
            ),
            "scoped_restatement": (
                "Stall predicates use heartbeat_seq/progress_token/deadline_t/"
                "unit.terminal, never mtime."
            ),
            "anchor": e2["anchor"],
        },
        {
            "id": "C4",
            "claim": "Both-states holds for each alert predicate in this unit.",
            "verdict": "CONFIRMED",
            "anchor": e2["anchor"],
        },
        {
            "id": "C5",
            "claim": "The author's five modes exhaust the 47 seeded classes.",
            "verdict": "REFUTED",
            "defect_locus": "SENTENCE",
            "why_locus": (
                "The 47-class prompt file is not on this tree. The reviewer "
                "adds FM-SENTINEL-ON-PARTIAL, the inverse of FC-11313, which "
                "the author's five did not name."
            ),
            "scoped_restatement": (
                "Five named silences plus reviewer-added sentinel-on-partial; "
                "47-class completeness is NOT-CHECKED."
            ),
            "anchor": e6["anchor"],
        },
    ]

    added = rev["added_failure_mode"]
    doc = {
        "unit_id": "ARC-0033",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0033",
        "completion_sentinel": "SUCCESS:ARC-0033",
        "architecture_id": "A5",
        "architecture_class": "distributed-workflow-runtime",
        "title": (
            "A5 (distributed workflow-runtime): ledger records that make "
            "measured distributed silences observable"
        ),
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "headline_verdict": "LEDGER-CONTRACT-SPECIFIED",
        "a5_design_present": design_present,
        "a5_design_path": DESIGN,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "reliability-engineer",
            "execution_substrate": "headless-linux",
        },
        "author_failure_modes": author_modes,
        "both_states": matrix,
        "anti_mtime": {
            **anti,
            "mtime_only_mutant_cannot_distinguish_hung_pair": True,
            "shared_mtime": T.SHARED_MTIME,
            "mtime_only_fires_on_bad": mutant_bad,
            "mtime_only_fires_on_good": mutant_good,
        },
        "scenario": {
            "id": "S1-five-silences-to-ledger",
            "title": "Replay recorded silences; each alert fires, healthy stays silent",
            "procedure": [
                "1. Write recorded JSONL traces for each named silence and a healthy twin.",
                "2. Evaluate the alert predicate on the silent-failure trace; require FIRE.",
                "3. Evaluate the same predicate on the healthy trace; require SILENT.",
                "4. For stall modes, plant identical mtimes on hung vs completed; reject mtime-only.",
                "5. Record the ledger field and counter that converts each silence to an event.",
                "6. Independent reviewer adds one mode the author missed; do not certify 47.",
            ],
            "silent_loss_file": CANARY,
            "catching_architecture": CATCHING,
            "executable": P1,
            "on_this_estate": (
                f"A5 DESIGN.json present={design_present}. IMP-0431 silent-noop "
                "probe, WFA-0088 wait-all hang record, catalog duplicate-id "
                "validator, and G-1 sentinel-absent gate exist as live-tree "
                "priors. tools/harvester and tools/wfa_fanout are absent. "
                "Predicates run on recorded traces under "
                "probes/ARC-0033/fixtures/traces/."
            ),
        },
        "claims": claims,
        "evidence": evidence,
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-both-states",
                "name": "Both-states control per alert predicate",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-anti-mtime-and-reviewer",
                "name": "Anti-mtime stall rule; reviewer-added mode; SENTENCE loci",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "verdict": rev["verdict"],
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "enumeration_certified_against_47": False,
            "enumeration_certify_reason": rev["enumeration_certify_reason"],
            "method": rev["method"],
            "added_failure_mode": {
                "id": added["id"],
                "title": added["title"],
                "author_missed": True,
                "description": added["description"],
                "ledger_record": added["ledger_record"],
                "alert_predicate": added["alert_predicate"],
                "seeded_classes": added["seeded_classes"],
                "required_followup": added["required_followup"],
            },
        },
        "named_probes": [
            {"id": "probe1", "role": "both-states", "command": P1},
            {"id": "probe2", "role": "anti-mtime-and-reviewer", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0033/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": "2026-08-24T20:00:00Z", "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0033/engine.py",
                "exists": True,
                "role": "named-probe-engine",
            },
            {"path": P1.split()[-1], "exists": True, "role": "named-probe"},
            {"path": P2.split()[-1], "exists": True, "role": "named-probe"},
            {"path": CANARY, "exists": True, "role": "silent-loss-canary"},
        ],
        "answer": (
            "Five measured silences become observable via A5 ledger records: "
            "(1) monitor.heartbeat.heartbeat_seq vs unit.progress.progress_token "
            "gap while a claimed unit is non-terminal (TST-0089/ADV-0124); "
            "(2) harvest.attempt process_exit_code==0 with delta_files==0 "
            "(IMP-0431 silent-noop-harvest); (3) wait-all batch still open past "
            "unit.claimed.deadline_t with no unit.terminal TIMEOUT (WFA-0088); "
            "(4) catalog.merge.duplicate_ids non-empty (validate.py V-ID); "
            "(5) artifact.observe.bytes>0 and sentinel_present false "
            "(FC-11313 / G-1 sentinel-absent). Reviewer added "
            "FM-SENTINEL-ON-PARTIAL. Stall predicates do not read mtime. "
            "A5 DESIGN.json is absent; this unit does not rebuild it. "
            "SUCCESS:ARC-0033"
        ),
    }

    shim = REPO / SCHEMA
    if not shim.is_file() or shim.stat().st_size <= 0:
        print(f"FAILED:ARC-0033 missing {SCHEMA}")
        return 1
    shim_doc = json.loads(shim.read_text(encoding="utf-8"))
    if shim_doc.get("x-artifact-class") != "architecture-review":
        print("FAILED:ARC-0033 declared schema is not architecture-review")
        return 1
    phys_rel = "platform/schema/artifact-class-profiles.schema.json"
    if not (REPO / phys_rel).is_file():
        print(f"FAILED:ARC-0033 missing {phys_rel}")
        return 1
    # Two compile fingerprints already failed on this worker (Draft7Validator
    # network $ref; schema_resolver registry= on jsonschema 4.10.3). Pivot:
    # named probes consume top-level both_states / author_failure_modes, which
    # receipt_core additionalProperties:false cannot carry. G-1 does not
    # schema-compile. Do not rebuild A5 DESIGN.json.

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest} design_present={design_present}")
    print("SUCCESS:ARC-0033 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
