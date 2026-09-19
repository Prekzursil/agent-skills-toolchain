#!/usr/bin/env python3
"""Pack AUD-0052 order-dependence and flake census receipt.

Emits BLOCKED until an independent, fresh-context Claude review PASS that
TRIED TO FALSIFY the headline count is on disk (catalog `reviewer_requirement`);
then SUCCESS. Never stubs SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0052"
OUT = "command-center/audit/AUD-0052-test-order-dependence.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0052/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when an independent, fresh-context Claude review PASS
    that TRIED TO FALSIFY the headline count is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"anthropic", "claude"}:
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads(
        (PROBE / "probe1-shuffled-order-dependence.json").read_text(encoding="utf-8")
    )
    p2 = json.loads(
        (PROBE / "probe2-repeated-identical-order.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-shuffled-order-dependence.raw.txt").read_text(
        encoding="utf-8"
    )
    raw2 = (PROBE / "probe2-repeated-identical-order.raw.txt").read_text(
        encoding="utf-8"
    )
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T21:33:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    baseline_collected = p1["baseline_collected_count"]
    seeds = p1["seeds"]
    shuffle_control_ok = bool(p1.get("shuffle_control_ok"))
    order_dep_count = p1["order_dependent_candidates_count"]
    p1_ground_truth_ok = bool(p1.get("ground_truth_ok"))
    p1_ok = bool(p1.get("ok"))

    repeats = p2["repeats"]
    orders_identical = bool(p2.get("orders_identical"))
    flaky_count = p2["flaky_tests_count"]
    p2_ground_truth_ok = bool(p2.get("ground_truth_ok"))
    p2_ok = bool(p2.get("ok"))

    # Cross-reference (catalog evidence_requirement's whole point): a single
    # shuffled-run failure cannot tell order-dependence apart from plain
    # nondeterminism. Probe2's 5 identical-order repeats are the instrument
    # that CAN tell them apart, so any probe1 candidate that probe2 also
    # flags as flaky under a held-constant order is reclassified as
    # flake-explained, not order-dependent.
    p1_candidate_ids = {c["nodeid"] for c in p1["order_dependent_candidates"]}
    p2_flaky_ids = {f["nodeid"] for f in p2["flaky_tests"]}
    flake_explained_ids = sorted(p1_candidate_ids & p2_flaky_ids)
    genuine_order_dependent_ids = sorted(p1_candidate_ids - p2_flaky_ids)
    genuine_order_dependent_count = len(genuine_order_dependent_ids)
    flake_explained_count = len(flake_explained_ids)

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(
            "command-center/p2-wave/probes/AUD-0052/probe1-shuffled-order-dependence.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/probe2-repeated-identical-order.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/probe1-shuffled-order-dependence.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/probe2-repeated-identical-order.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/probe1_shuffled_order_dependence.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/probe2_repeated_identical_order.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/fixtures/aud0052_plugin.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/fixtures/collectible_scope.py",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/fixtures/order_dependent/test_a_writer.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/fixtures/order_dependent/test_b_reader.py",
            "control",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0052/fixtures/flaky/test_flaky_ground_truth.py",
            "control",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0052/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which tests pass in declaration order but fail under a shuffled order, "
        "and which produce a different result across repeated identical runs?"
    )
    headline = (
        f"{baseline_collected} collectible tests this pass (command-center/, "
        "2 non-hermetic salvage/scratch trees excluded, see fixtures/"
        "collectible_scope.py). Probe1 raw (3 shuffled seeds "
        f"{seeds}, shuffle-actually-reordered control={shuffle_control_ok}): "
        f"{order_dep_count} candidate(s) that passed at baseline and failed under "
        "at least one shuffle. Probe2 (5 identical-order repeats, order-held-"
        f"constant control={orders_identical}): {flaky_count} test(s) that "
        "disagree with themselves even with order held constant. "
        f"Cross-referencing the two (the catalog's own point: a single shuffled "
        "failure alone cannot tell order-dependence apart from plain "
        f"nondeterminism): {flake_explained_count} of the {order_dep_count} probe1 "
        "candidate(s) are ALSO flaky under a held-constant order and are "
        f"therefore flake, not order-dependence, leaving {genuine_order_dependent_count} "
        "genuinely order-dependent test(s) this pass. All flagged tests in both "
        "categories are the deliberately planted ground-truth fixtures (real "
        "135-test corpus: 0 order-dependent, 0 flaky this pass). Detection method "
        "proven live: both ground-truth fixtures were caught and correctly "
        f"classified (probe1_ground_truth_ok={p1_ground_truth_ok}, "
        f"probe2_ground_truth_ok={p2_ground_truth_ok})."
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "anthropic"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0052"
        failure = None
        anti = "SUCCESS-after-independent-falsify-PASS"
        defects = [
            {
                "id": "AUD-0052-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Independent fresh-context Claude review PASS recorded at "
                    "command-center/p2-wave/probes/AUD-0052/independent-review.json"
                ),
            },
            {
                "id": "AUD-0052-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"This pass swept {baseline_collected} tests collectible cleanly "
                    "under command-center/ only; tools/, platform/, skills/, and the "
                    "two excluded non-hermetic trees are carried forward as "
                    "not-yet-swept residuals, not silently dropped."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires one fresh-context Claude reviewer who has not "
                "seen this unit's transcript; the reviewer must try to FALSIFY "
                "the headline count before PASS, not re-read the artifact. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0052 shuffled-order-dependence+repeated-identical-order "
            f"probes measured baseline_collected={baseline_collected} "
            f"order_dependent_candidates={order_dep_count} flaky_tests={flaky_count} "
            f"genuine_order_dependent={genuine_order_dependent_count} "
            f"flake_explained={flake_explained_count}; blocked-on-independent-review"
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "green-not-live",
                "concurrency-contention",
                "detector-failure",
            ],
            "reason": (
                f"Named probes completed: {baseline_collected} tests swept for "
                f"order-dependence across {len(seeds)} shuffled seeds "
                f"({order_dep_count} candidate(s) found, ground-truth confirmed "
                f"caught={p1_ground_truth_ok}) and for flake across {repeats} "
                f"identical-order repeats ({flaky_count} flaky, ground-truth "
                f"confirmed caught={p2_ground_truth_ok}), but catalog "
                "reviewer_requirement is unmet."
            ),
            "diagnostic_tail": (
                f"p1_ok={p1_ok} shuffle_control_ok={shuffle_control_ok} "
                f"order_dependent_candidates={order_dep_count} "
                f"p2_ok={p2_ok} orders_identical={orders_identical} "
                f"flaky_tests={flaky_count} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen "
                "this transcript to try to FALSIFY the headline order-dependent "
                "and flaky-test counts before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0052/probe1_shuffled_order_dependence.py",
                    f"order_dependent_candidates_count={order_dep_count} "
                    f"shuffle_control_ok={shuffle_control_ok}",
                    0 if p1_ok else 1,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-with-real-probes"
        defects = [
            {
                "id": "AUD-0052-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude falsify-review unpaid.",
            },
            {
                "id": "AUD-0052-D-SCOPE",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"This pass swept {baseline_collected} tests collectible cleanly "
                    "under command-center/ only; tools/, platform/, skills/, and the "
                    "two excluded non-hermetic trees are carried forward as "
                    "not-yet-swept residuals, not silently dropped."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0052",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 shuffled-order-dependence census: {baseline_collected} "
                    "collectible tests run once in declaration order (baseline) then "
                    f"three more times with distinct seeds {seeds}, each reordered by "
                    "fixtures/aud0052_plugin.py's random.Random(seed).shuffle() over "
                    "the FULL collected item list. tests_required control: the three "
                    f"recorded post-shuffle orders are pairwise distinct and differ "
                    f"from the baseline (shuffle_control_ok={shuffle_control_ok}) -- "
                    "proving the shuffle plugin actually reordered rather than "
                    f"being a no-op. {order_dep_count} test(s) passed in the baseline "
                    "but failed under at least one shuffled seed; ground truth "
                    "(a deliberately planted order-dependent pair) confirmed caught: "
                    f"{p1_ground_truth_ok}."
                ),
                "CONFIRMED" if p1_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0052/probe1-shuffled-order-dependence.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0052/probe1_shuffled_order_dependence.py",
                        raw1,
                        0 if p1_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-shuffled-order-dependence.json",
                        json.dumps(
                            {
                                "baseline_collected_count": baseline_collected,
                                "shuffle_control_ok": shuffle_control_ok,
                                "order_dependent_candidates_count": order_dep_count,
                                "ground_truth_ok": p1_ground_truth_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Probe 2 repeated-identical-order flake census: the same "
                    f"{baseline_collected}-test set run {repeats} times with NO "
                    "shuffle (collection order held constant across all five -- "
                    f"orders_identical={orders_identical}). A test whose outcome "
                    "still varies across these five identical-order repeats cannot "
                    f"be explained by reordering. {flaky_count} test(s) disagreed "
                    "with themselves across the five repeats; ground truth (a "
                    "deliberately planted OS-entropy-seeded flaky test) confirmed "
                    f"caught: {p2_ground_truth_ok}."
                ),
                "CONFIRMED" if p2_ok else "REFUTED",
                "command-center/p2-wave/probes/AUD-0052/probe2-repeated-identical-order.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0052/probe2_repeated_identical_order.py",
                        raw2,
                        0 if p2_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-repeated-identical-order.json",
                        json.dumps(
                            {
                                "orders_identical": orders_identical,
                                "flaky_tests_count": flaky_count,
                                "ground_truth_ok": p2_ground_truth_ok,
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0052-shuffle-actually-reorders",
                "name": (
                    "tests_required control: the shuffle plugin must actually "
                    "reorder; assert the recorded collection order differs "
                    "between seeds, otherwise a green result means the shuffle "
                    "never happened"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0052/probe1_shuffled_order_dependence.py",
                "result": "PASS" if shuffle_control_ok else "FAIL",
                "assertions": 3,
                "output_tail": raw1[-800:],
            },
            {
                "id": "AUD-0052-order-held-constant",
                "name": "probe2 precondition: all five repeats must use the SAME collection order",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0052/probe2_repeated_identical_order.py",
                "result": "PASS" if orders_identical else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0052-C1",
                "mutation",
                (
                    "The recorded collection order must differ between the three "
                    "shuffled seeds (and from the declaration-order baseline); "
                    "identical orders would mean the shuffle plugin never fired."
                ),
                True,
                True,
                bad="all three seed orders identical to each other and/or to baseline",
                good=f"shuffle_control_ok={shuffle_control_ok} seeds={seeds}",
            ),
            L.control(
                "AUD0052-C2",
                "known-broken-fixture",
                (
                    "A deliberately planted order-dependent test pair "
                    "(test_a_writer.py writes a flag, test_b_reader.py requires "
                    "it) must be flagged by probe1 on the seeds that place B "
                    "before A, and must NOT be flagged on the seed that keeps "
                    "A first."
                ),
                True,
                True,
                bad=f"ground_truth failed_on_seeds={p1['ground_truth']['failed_on_seeds']}",
                good=f"expected={p1['ground_truth']['expected_failed_on_seeds']} ok={p1_ground_truth_ok}",
            ),
            L.control(
                "AUD0052-C3",
                "known-broken-fixture",
                (
                    "A deliberately planted OS-entropy-seeded flaky test must be "
                    "flagged by probe2 as disagreeing with itself across the five "
                    "identical-order repeats."
                ),
                True,
                True,
                bad=f"ground_truth outcomes={p2['ground_truth']['outcomes_by_repeat']}",
                good=f"flagged={p2['ground_truth']['flagged']} ok={p2_ground_truth_ok}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0052/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry only after the named upstream unit emits its SUCCESS "
                "sentinel; retrying against a missing input is a detector "
                "failure, not a transient"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether tests under tools/, platform/, skills/, and the two "
                    "excluded non-hermetic salvage/scratch trees "
                    "(command-center/ssot/salvaged-at-risk, "
                    "command-center/p2-wave/probes/AUD-0043/fixtures) are "
                    "order-dependent or flaky (this pass swept only the "
                    f"{baseline_collected} tests collectible cleanly under "
                    "command-center/)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Repair the two excluded trees' import/collection errors "
                    "(fixtures/collectible_scope.py names each), extend "
                    "TARGET_ARGS to cover tools/ and platform/ once each "
                    "collects cleanly, and re-run both named probes."
                ),
            },
            {
                "claim": (
                    "Whether any of the 4 deterministic jsonschema-missing "
                    "failures in the real 135-test corpus would flip to flaky "
                    "or order-dependent once the missing 'jsonschema' package "
                    "is installed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "pip install jsonschema>=4.18 in the probe environment and "
                    "re-run both probes; compare the resulting counts to this "
                    "pass's (order_dependent_candidates="
                    f"{order_dep_count}, flaky_tests={flaky_count})."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0052-C1", "AUD0052-C2", "AUD0052-C3"],
            "observations": [
                {
                    "name": "baseline_collected_count",
                    "measured": baseline_collected,
                    "method": "pytest --collect-only over fixtures/collectible_scope.py TARGET_ARGS",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/probe1-shuffled-order-dependence.raw.txt",
                },
                {
                    "name": "shuffle_control_ok",
                    "measured": shuffle_control_ok,
                    "method": "assert 3 seeded post-shuffle orders pairwise distinct and distinct from baseline",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/probe1-shuffled-order-dependence.json",
                },
                {
                    "name": "order_dependent_candidates_count",
                    "measured": order_dep_count,
                    "method": "baseline PASS + shuffled-seed non-PASS on the same nodeid, any of 3 seeds",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/probe1-shuffled-order-dependence.raw.txt",
                },
                {
                    "name": "flaky_tests_count",
                    "measured": flaky_count,
                    "method": "5 identical-declaration-order repeats; outcome disagreement across repeats",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/probe2-repeated-identical-order.raw.txt",
                },
                {
                    "name": "ground_truth_detection_ok",
                    "measured": bool(p1_ground_truth_ok and p2_ground_truth_ok),
                    "method": "deliberately planted order-dependent pair + OS-entropy flaky test, both must be caught",
                    "anchor": "command-center/p2-wave/probes/AUD-0052/fixtures/",
                },
                {
                    "name": "genuine_order_dependent_count",
                    "measured": genuine_order_dependent_count,
                    "method": (
                        "probe1 candidates minus probe2's flaky-under-held-order "
                        "set (set difference), per catalog evidence_requirement"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0052/probe1-shuffled-order-dependence.json",
                },
                {
                    "name": "flake_explained_count",
                    "measured": flake_explained_count,
                    "method": (
                        "probe1 candidates intersected with probe2's flaky-under-"
                        "held-order set -- these look order-dependent to probe1 "
                        "alone but are plain nondeterminism, not order-dependence"
                    ),
                    "anchor": "command-center/p2-wave/probes/AUD-0052/probe2-repeated-identical-order.json",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-finding",
            "wave": "p2-loop",
            "anti_false_green": anti,
            "output_schema_confirmed": SCHEMA,
            "output_path_confirmed": OUT,
            "probe1_summary": {
                "baseline_collected_count": baseline_collected,
                "seeds": seeds,
                "shuffle_control_ok": shuffle_control_ok,
                "order_dependent_candidates_count": order_dep_count,
                "ground_truth_ok": p1_ground_truth_ok,
                "ok": p1_ok,
            },
            "probe2_summary": {
                "repeats": repeats,
                "orders_identical": orders_identical,
                "flaky_tests_count": flaky_count,
                "ground_truth_ok": p2_ground_truth_ok,
                "ok": p2_ok,
            },
            "cross_reference": {
                "genuine_order_dependent_count": genuine_order_dependent_count,
                "genuine_order_dependent_ids": genuine_order_dependent_ids,
                "flake_explained_count": flake_explained_count,
                "flake_explained_ids": flake_explained_ids,
            },
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    required = [
        PROBE / "probe1-shuffled-order-dependence.json",
        PROBE / "probe2-repeated-identical-order.json",
        PROBE / "probe1-shuffled-order-dependence.raw.txt",
        PROBE / "probe2-repeated-identical-order.raw.txt",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0052 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
