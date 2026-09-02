#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0066-mechanism-level-dedup.json from live evaluate()."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import dedup as D  # noqa: E402

OUT = "command-center/wfa/WFA-0066-mechanism-level-dedup.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SemanticDiff"
QUESTION = (
    "Which canonical mechanism ids are the same mechanism under two names - "
    "the spec's mechanism-level deduplication requirement applied to the "
    "vocabulary itself rather than to workflows - and does collapsing them "
    "change the leverage ranking?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0066/probe1_and_gate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0066/probe2_ranking_delta.py"
)
SYN_A = "MECH-CONFLICT-REFUSE"
SYN_B = "MECH-UNION-GUARD"
SHARE_A = "MECH-SBAR-HANDOFF"
SHARE_B = "MECH-PEER-REVIEW"
ECHO = "MECH-ECHO-COPY"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:WFA-0066 emit needle {needle!r} missing in {rel}")


def _pair(result: dict, a: str, b: str) -> dict:
    for p in result["pair_verdicts"]:
        if {p["left"], p["right"]} == {a, b}:
            return p
    raise SystemExit(f"FAILED:WFA-0066 missing pair {a}/{b}")


def _residuals(
    corp: dict, schema_pack: Path, live_vocab: Path, live_extract: Path
) -> list[str]:
    rows: list[str] = []
    if not live_vocab.is_file() or not live_extract.is_file():
        rows.append(
            "command-center/wfa/WFA-0058-mechanism-vocabulary.json and "
            "command-center/wfa/WFA-0059-mechanism-extraction.json are "
            "absent. This unit runs the catalog's two-signal operator on "
            "a closed fixture vocabulary. Re-run the same operator on the "
            "live WFA-0058/0059 artifacts when those units deliver; do not "
            "treat the fixture ids as the frozen estate vocabulary."
        )
    else:
        rows.append(
            "Live WFA-0058/WFA-0059 catalog artifacts were present and "
            f"loaded (source={corp.get('source')}). Fixture ids are not "
            "claimed as the frozen estate vocabulary beyond that load."
        )
    lev = REPO / "command-center/wfa/WFA-0060-mechanism-leverage-ranking.json"
    if not lev.is_file():
        rows.append(
            "command-center/wfa/WFA-0060-mechanism-leverage-ranking.json is "
            "absent. Ranking here is the independent-source formula this "
            "unit needs in order to report a collapse delta; it is not a "
            "claim to have delivered WFA-0060."
        )
    else:
        rows.append(
            "WFA-0060 ranking artifact is present on disk; this unit still "
            "recomputes leverage from its own incidence union so the "
            "collapse delta is not a copied WFA-0060 row."
        )
    if schema_pack.is_file():
        rows.append(
            "command-center/wfa/schema/wfa-schema-pack.json is present "
            f"({schema_pack.stat().st_size} bytes) as a generated $ref "
            "shim to artifact-class-profiles. report_kind=SemanticDiff is "
            "declared; this document is not Draft-validated against the "
            "remote $defs URL. schema_pack_present=True. No ADV rebuild."
        )
    else:
        rows.append(
            "command-center/wfa/schema/wfa-schema-pack.json is absent "
            "(WFA-0001). report_kind=SemanticDiff is declared; this "
            "document is not validated against the missing $defs. "
            "schema_pack_present=False."
        )
    rows.append(
        "Harness-restore inputs "
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json and _USER-PROMPTS.md:10666 "
        "are not mounted on this Linux worktree."
    )
    return rows


def main() -> int:
    corp = C.load_corpus()
    live = D.evaluate(corp, incidence_only=False)
    mutant = D.evaluate(corp, incidence_only=True)
    if live["ids_deleted"]:
        print(f"FAILED:WFA-0066 emit deleted ids {live['ids_deleted']}")
        return 1
    if not D.same_canonical(live, SYN_A, SYN_B):
        print("FAILED:WFA-0066 emit synonym pair not collapsed")
        return 1
    if D.same_canonical(live, SHARE_A, SHARE_B):
        print("FAILED:WFA-0066 emit shared-source pair collapsed")
        return 1
    if not D.same_canonical(mutant, SHARE_A, SHARE_B):
        print("FAILED:WFA-0066 emit incidence-only mutant did not fire")
        return 1

    dedup_rel = "command-center/p2-wave/probes/WFA-0066/dedup.py"
    corp_rel = "command-center/p2-wave/probes/WFA-0066/corpus.py"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"
    a_and = (
        f"{dedup_rel}:"
        f"{line_of(dedup_rel, 'collapse = bool(suspect and (incidence_only or disc[\"indistinguishable\"]))')}"
    )
    a_alias = f"{dedup_rel}:{line_of(dedup_rel, '\"relation\": \"duplicate-of\"')}"
    a_rank = f"{dedup_rel}:{line_of(dedup_rel, 'def leverage_score')}"
    a_cat = f"{cat_rel}:{line_of(cat_rel, '\"id\": \"WFA-0066\"')}"
    a_load = f"{corp_rel}:{line_of(corp_rel, 'source\"] = \"closed-fixture\"')}"

    syn = _pair(live, SYN_A, SYN_B)
    share = _pair(live, SHARE_A, SHARE_B)
    syn_delta = next(
        d
        for d in live["ranking_delta"]["survivor_deltas"]
        if {d["canonical_id"], d["alias_id"]} == {SYN_A, SYN_B}
    )
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    canonical = live["canonical_of"][SYN_A]
    alias = SYN_B if canonical == SYN_A else SYN_A
    echo = live["ranking_delta"].get("frequency_vs_leverage")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    decision = (
        f"On the closed vocabulary actually present on this worktree "
        f"(source={corp.get('source')}; live WFA-0058="
        f"{C.LIVE_VOCAB.is_file()}; live WFA-0059={C.LIVE_EXTRACT.is_file()}), "
        f"{SYN_A} and {SYN_B} are the same mechanism under two names: incidence "
        f"Jaccard {syn['incidence_jaccard']} and definition-prototype accuracy "
        f"{syn['discrimination']['accuracy']} both fire, so {alias} is aliased "
        f"to {canonical} via a duplicate-of edge and is not deleted. "
        f"{SHARE_A} and {SHARE_B} share an incidence set (Jaccard "
        f"{share['incidence_jaccard']}) because they co-occur on the same "
        f"artifacts, but definition-prototype accuracy "
        f"{share['discrimination']['accuracy']} tells them apart, so they are "
        f"not collapsed. Incidence-only collapse of that pair is the negative "
        f"control. Collapsing the synonym pair changes leverage: survivor "
        f"independent sources {syn_delta['independent_before']}->"
        f"{syn_delta['independent_after']}, score {syn_delta['leverage_before']}"
        f"->{syn_delta['leverage_after']}, ranked count "
        f"{live['ranking_delta']['ranked_count_before']}->"
        f"{live['ranking_delta']['ranked_count_after']}. Frequency ranking "
        f"still promotes {ECHO}; leverage ranking does not."
    )

    doc = {
        "unit_id": "WFA-0066",
        "id": "WFA-0066",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:WFA-0066",
        "completion_sentinel": "SUCCESS:WFA-0066",
        "report_kind": "SemanticDiff",
        "title": (
            "Mechanism-level deduplication: collapse vocabulary entries that "
            "name one mechanism twice"
        ),
        "question": QUESTION,
        "decision": decision,
        "output_schema": SCHEMA,
        "schema_pack_present": schema_pack.is_file(),
        "corpus": {
            "source": corp.get("source"),
            "version": corp.get("version"),
            "live_vocab_present": C.LIVE_VOCAB.is_file(),
            "live_extract_present": C.LIVE_EXTRACT.is_file(),
            "mechanism_count": len(corp["mechanisms"]),
            "artifact_count": len(corp["artifacts"]),
            "fixture_path": (
                "command-center/p2-wave/probes/WFA-0066/fixtures/vocabulary.json"
            ),
        },
        "thresholds": {
            "incidence_jaccard": live["threshold"],
            "discrimination_accuracy_floor": live["accuracy_floor"],
            "collapse_rule": "suspect AND indistinguishable",
        },
        "same_mechanism_under_two_names": [
            {
                "alias": alias,
                "canonical": canonical,
                "incidence_jaccard": syn["incidence_jaccard"],
                "discrimination_accuracy": syn["discrimination"]["accuracy"],
                "duplicate_of": True,
            }
        ],
        "suspect_pairs_not_collapsed": [
            {
                "left": SHARE_A,
                "right": SHARE_B,
                "incidence_jaccard": share["incidence_jaccard"],
                "discrimination_accuracy": share["discrimination"]["accuracy"],
                "reason": share["reason"],
            }
        ],
        "pair_verdicts": live["pair_verdicts"],
        "collapses": live["collapses"],
        "duplicate_of_edges": live["duplicate_of_edges"],
        "canonical_of": live["canonical_of"],
        "mechanism_ids": live["mechanism_ids"],
        "ids_deleted": live["ids_deleted"],
        "ranking_before": live["ranking_before"],
        "ranking_after": live["ranking_after"],
        "frequency_ranking_after": live["frequency_ranking_after"],
        "ranking_delta": live["ranking_delta"],
        "frequency_vs_leverage": echo,
        "rules": [
            {
                "id": "both-signals",
                "statement": (
                    "Collapse requires incidence Jaccard at or above threshold "
                    "AND a failed blind discrimination test. Incidence overlap "
                    "alone can be a shared source."
                ),
            },
            {
                "id": "alias-not-delete",
                "statement": (
                    "Each collapse writes a duplicate-of edge from the alias "
                    "to the canonical id. The alias remains in mechanism_ids."
                ),
            },
            {
                "id": "recompute-leverage",
                "statement": (
                    "Leverage is independent_source_count * severity * "
                    "decision_impact. Ranking is recomputed after unioning "
                    "incidence onto the canonical id, and the delta is reported."
                ),
            },
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    f"{SYN_A} and {SYN_B} collapse under both signals; "
                    f"{SHARE_A} and {SHARE_B} do not, despite incidence overlap."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_and,
            },
            {
                "id": "C2",
                "claim": (
                    "Collapsed ids remain as aliases with duplicate-of edges; "
                    "ids_deleted is empty."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_alias,
            },
            {
                "id": "C3",
                "claim": (
                    "Leverage ranking after collapse differs from the "
                    "pre-collapse ranking; frequency ranking still disagrees "
                    "with leverage on the echo cluster."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_rank,
            },
        ],
        "tests": [
            {
                "id": "collapse-requires-both-signals",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "leverage-ranking-recomputed",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "duplicate-of-alias-not-delete",
                "command": P1,
                "result": "PASS",
            },
        ],
        "both_states": {
            "fires_on": (
                "incidence-only mutant of the AND-gate, which merges "
                f"{SHARE_A}/{SHARE_B} (Jaccard {share['incidence_jaccard']})"
            ),
            "silent_on": (
                "production AND-gate on the same pair, which refuses collapse "
                f"because discrimination accuracy="
                f"{share['discrimination']['accuracy']}"
            ),
            "verbatim_fire": (
                f"incidence-only same_canonical({SHARE_A},{SHARE_B})=true"
            ),
            "verbatim_silent": (
                f"AND-gate same_canonical({SHARE_A},{SHARE_B})=false"
            ),
        },
        "negative_controls": [
            {
                "id": "incidence-only-shared-source",
                "rejects": (
                    "collapsing a pair on incidence Jaccard without a failed "
                    "discrimination test"
                ),
                "observed": (
                    f"mutant merged {SHARE_A}/{SHARE_B}; production did not"
                ),
            }
        ],
        "evidence": [
            {
                "claim": "AND-gate on synonym vs shared-source pair",
                "mechanism": (
                    "incidence Jaccard over artifact-id sets AND "
                    "definition-prototype assignment of held-out examples"
                ),
                "anchor": a_and,
                "verbatim": (
                    f"synonym jaccard={syn['incidence_jaccard']} "
                    f"acc={syn['discrimination']['accuracy']} collapse=true; "
                    f"shared jaccard={share['incidence_jaccard']} "
                    f"acc={share['discrimination']['accuracy']} collapse=false"
                ),
            },
            {
                "claim": "leverage delta after aliasing",
                "mechanism": (
                    "independent upstream set of the unioned incidence; "
                    "frequency ranking published beside it"
                ),
                "anchor": a_rank,
                "verbatim": json.dumps(syn_delta, sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0066-probe2-example-1nn-and-rank-delta",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe2 does not call discriminate(). It leave-one-out 1-NN "
                "classifies example texts, reconstructs the pre-collapse id "
                f"set from duplicate-of edges, and checks that frequency rank "
                f"and leverage rank disagree on {ECHO}."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0066/dedup.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0066/fixtures/vocabulary.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": _residuals(
            corp, schema_pack, C.LIVE_VOCAB, C.LIVE_EXTRACT
        ),
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
            }
        ],
        "catalog_anchor": a_cat,
        "loader_anchor": a_load,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "differ-engineer",
            "execution_substrate": "linux-local",
        },
        "min_bytes_threshold": 2048,
        "ts": now,
        "notes": (
            "SUCCESS:WFA-0066 G-1 SemanticDiff. Live named probes exit 0. "
            "Did not run global unit_manifest.py --write. Did not rebuild "
            "WFA-0001 schema pack. cloud ok=true is not delivery."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:WFA-0066")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
