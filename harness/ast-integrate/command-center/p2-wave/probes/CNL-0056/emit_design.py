#!/usr/bin/env python3
"""Emit the CNL-0056 design note (JSON at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ledger as L  # noqa: E402
import recount as R  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0056-idea-ledger-schema-and-per-participant-provenance.md"
)
QUESTION = (
    "What does the idea ledger record so that an idea can be traced to its "
    "originator, its duplicates, its supporters and its fate in the final "
    "synthesis - and what is the check that no idea silently disappears "
    "between ledger and synthesis?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0056/probe1_disappearing_idea.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0056/probe2_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    good = load_fix("known-good.json")
    bad = load_fix("planted-bad.json")
    good_res = L.check_disappearance(good)
    bad_res = L.check_disappearance(bad)
    drop = L.drop_idea_from_synthesis(good, "IDEA-0003")
    drop_res = L.check_disappearance(drop)
    g_ind = R.tabulate(good)
    b_ind = R.tabulate(bad)
    d_ind = R.tabulate(drop)
    g_ok, g_why = R.numbers_agree(good_res, g_ind)
    b_ok, b_why = R.numbers_agree(bad_res, b_ind)
    d_ok, d_why = R.numbers_agree(drop_res, d_ind)
    if not (good_res.get("silent") and bad_res.get("fired") and drop_res.get("fired")):
        print("FAILED:CNL-0056 emit checks did not discriminate")
        print(json.dumps({"good": good_res, "bad": bad_res, "drop": drop_res}, indent=2)[:4000])
        return 1
    if not (g_ok and b_ok and d_ok):
        print("FAILED:CNL-0056 emit recount", g_why, b_why, d_why)
        return 1
    if good_res.get("schema_errors") or bad_res.get("schema_errors"):
        print("FAILED:CNL-0056 emit schema", good_res.get("schema_errors"))
        return 1

    schema_rel = "command-center/schema/councilspec.v2.schema.json"
    schema_path = REPO / schema_rel
    schema_on_disk = schema_path.is_file() and schema_path.stat().st_size > 0
    if schema_on_disk:
        schema_note = (
            "Catalog points at command-center/schema/councilspec.v2.schema.json "
            "(CNL-0001). On this worktree the file is a generated shim that "
            "$ref's platform/schema/artifact-class-profiles.schema.json"
            "#/$defs/councilspec.v2; it is not the full CouncilSpec v2 root "
            "envelope. This note carries the idea-ledger $defs that CNL-0001 "
            "must absorb."
        )
    else:
        schema_note = (
            "Catalog points at command-center/schema/councilspec.v2.schema.json "
            "(CNL-0001). That file is absent on this worktree. This note carries "
            "the idea-ledger $defs that CNL-0001 must absorb; it does not claim "
            "to be the full CouncilSpec v2 root envelope."
        )

    negative_verbatim = (
        "On the planted-bad fixture (synthesis node SYN-03 removed, ledger still "
        "holds IDEA-0003 with originator P-dave, supporter P-alice, fate DISSENTED), "
        f"the check FIRES. signal_a.missing={bad_res['signal_a']['missing']} "
        f"signal_b.missing={bad_res['signal_b']['missing']} fired={bad_res['fired']} "
        f"silent={bad_res['silent']}."
    )

    doc = {
        "unit_id": "CNL-0056",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:CNL-0056",
        "completion_sentinel": "SUCCESS:CNL-0056",
        "title": "Idea ledger schema and per-participant provenance",
        "phase": "2C",
        "output_schema": schema_rel,
        "output_schema_on_disk": schema_on_disk,
        "output_schema_note": schema_note,
        "report": {
            "kind": "councilspec.v2",
            "observations": [
                {
                    "name": "known-good-silent",
                    "measured": bool(good_res["silent"]),
                    "method": "ledger.check_disappearance set-difference",
                    "anchor": "command-center/p2-wave/probes/CNL-0056/fixtures/known-good.json",
                },
                {
                    "name": "planted-bad-fires",
                    "measured": bool(bad_res["fired"]),
                    "method": "ledger.check_disappearance set-difference",
                    "anchor": "command-center/p2-wave/probes/CNL-0056/fixtures/planted-bad.json",
                },
                {
                    "name": "runtime-drop-IDEA-0003-fires",
                    "measured": bool(drop_res["fired"]),
                    "method": "drop_idea_from_synthesis then check_disappearance",
                    "anchor": "command-center/p2-wave/probes/CNL-0056/ledger.py:188",
                },
            ],
            "control_ids": [
                "known-good",
                "planted-bad",
                "runtime-drop-IDEA-0003",
                "ghost-id-only",
            ],
        },
        "question": QUESTION,
        "answer": (
            "The ledger is an append-only array of idea records. Each record "
            "stores a stable idea_id, a canonical_mechanism (the CNL-0051 dedup "
            "key; statement text is never identity), an immutable originator "
            "(participant_id, seat, round, seq, recorded_at), a duplicate_of "
            "pointer plus the inverse duplicates list, a supporters list with "
            "stance in {endorse,second,qualify,oppose}, and a fate object "
            "(status in {ADOPTED,MERGED,REJECTED,DEFERRED,DISSENTED,UNRESOLVED} "
            "plus synthesis_node_ids). A canonical idea (duplicate_of is null) "
            "must appear in the synthesis. The disappearance check FIRES when "
            "either Signal A (required idea_id set minus cites_idea_ids) or "
            "Signal B (required canonical_mechanism set minus covers_mechanisms) "
            "is non-empty. Duplicates are traced through duplicate_of and are "
            "not themselves required citations. SILENT only when both missing "
            "sets are empty."
        ),
        "depends_on": {
            "CNL-0051": (
                "Semantic unique-idea counter defines when two statements are "
                "the SAME idea. This unit records the resulting duplicate_of "
                "edge; it does not re-implement Jaccard/rewrite recall."
            )
        },
        "inputs_on_this_worktree": {
            "_USER-PROMPTS.md:10746-10767": False,
            "_USER-PROMPTS.md:10915-10946": False,
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "command-center/schema/councilspec.v2.schema.json": schema_on_disk,
            "note": (
                "Harness restore paths from the catalog are not on this Linux "
                "tree. Design is operationalised from the catalog question, "
                "tests_required, CNL-0051 dependency, and IMP-0291 ledger fields "
                "(author/round/canonical-mechanism)."
            ),
        },
        "idea_ledger_schema": {
            "id": "idea-ledger/v1",
            "append_only": True,
            "identity": {
                "idea_id": "stable record id; never recycled",
                "canonical_mechanism": (
                    "dedup key from CNL-0051; two records with the same "
                    "mechanism are the same idea even if statement text differs"
                ),
                "statement": "surface wording; not identity; not a quota token",
            },
            "originator": {
                "required": [
                    "participant_id",
                    "seat",
                    "round",
                    "seq",
                    "recorded_at",
                ],
                "immutable": True,
                "rule": (
                    "The first writer of a canonical_mechanism is originator. "
                    "Later restatements become new rows with duplicate_of set; "
                    "they MUST NOT overwrite originator."
                ),
            },
            "duplicates": {
                "duplicate_of": "null on the canonical row; idea_id of canonical on later rows",
                "duplicates": "inverse list on the canonical row",
                "not_required_in_synthesis": True,
                "fate_of_duplicate": "MERGED",
            },
            "supporters": {
                "item": [
                    "participant_id",
                    "round",
                    "seq",
                    "stance",
                    "recorded_at",
                ],
                "stance_vocab": sorted(L.STANCE_VOCAB),
                "rule": "supporters append; they never become originator",
            },
            "fate": {
                "status_vocab": sorted(L.FATE_VOCAB),
                "synthesis_node_ids": "nodes in the synthesis artifact that dispose this idea",
                "rule": (
                    "Fate on the ledger is a claim. The disappearance check "
                    "does not trust it: it re-reads synthesis citations."
                ),
            },
            "required_keys": list(L.REQUIRED_IDEA_KEYS),
            "$defs": {
                "IdeaRecord": {
                    "type": "object",
                    "required": list(L.REQUIRED_IDEA_KEYS),
                    "additionalProperties": False,
                    "properties": {
                        "idea_id": {"type": "string", "minLength": 1},
                        "canonical_mechanism": {"type": "string", "minLength": 1},
                        "statement": {"type": "string", "minLength": 1},
                        "originator": {
                            "type": "object",
                            "required": list(L.REQUIRED_ORIGINATOR_KEYS),
                            "properties": {
                                "participant_id": {"type": "string"},
                                "seat": {"type": "string"},
                                "round": {"type": "integer", "minimum": 1},
                                "seq": {"type": "integer", "minimum": 1},
                                "recorded_at": {"type": "string"},
                            },
                        },
                        "duplicate_of": {"type": ["string", "null"]},
                        "duplicates": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "supporters": {"type": "array"},
                        "fate": {
                            "type": "object",
                            "required": ["status", "synthesis_node_ids"],
                            "properties": {
                                "status": {"enum": sorted(L.FATE_VOCAB)},
                                "synthesis_node_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "rationale": {"type": "string"},
                            },
                        },
                    },
                }
            },
        },
        "disappearance_check": {
            "name": "check_disappearance",
            "implementation": "command-center/p2-wave/probes/CNL-0056/ledger.py",
            "required_set": (
                "canonical rows only (duplicate_of is null). IDEA-0004 in the "
                "fixture is a paraphrase and must not be required."
            ),
            "signal_a": {
                "mechanism": "set difference",
                "left": "canonical idea_id",
                "right": "synthesis node cites_idea_ids",
                "fires_when": "missing idea_ids non-empty",
                "source": "command-center/p2-wave/probes/CNL-0056/ledger.py:56",
            },
            "signal_b": {
                "mechanism": "set difference on a different field",
                "left": "canonical canonical_mechanism",
                "right": "synthesis node covers_mechanisms",
                "fires_when": "missing mechanisms non-empty",
                "source": "command-center/p2-wave/probes/CNL-0056/ledger.py:68",
            },
            "combine": "FIRE if A or B fires; SILENT iff both missing sets are empty",
            "signals_disagree_means": (
                "citation dump on one field only (ghost ID or ghost mechanism). "
                "Still FIRE. Independence is proven by dropping only cites_idea_ids."
            ),
            "does_not_trust": [
                "ledger fate.synthesis_node_ids without a matching synthesis node",
                "an empty synthesis section that merely exists",
                "string-equality unique counts",
            ],
        },
        "tests": {
            "disappearing_idea": {
                "method": "drop_idea_from_synthesis(known-good, IDEA-0003)",
                "fired": drop_res["fired"],
                "missing_ids": drop_res["signal_a"]["missing"],
                "missing_mechs": drop_res["signal_b"]["missing"],
                "n_missing_ids": drop_res["signal_a"]["n_missing"],
                "independent_recount": d_why,
                "duplicate_not_required": "IDEA-0004"
                not in drop_res["signal_a"]["required"],
            },
            "both_states": {
                "known_good_silent": good_res["silent"],
                "known_good_n_missing_ids": good_res["signal_a"]["n_missing"],
                "known_good_n_missing_mechs": good_res["signal_b"]["n_missing"],
                "planted_bad_fired": bad_res["fired"],
                "planted_bad_missing_ids": bad_res["signal_a"]["missing"],
                "planted_bad_missing_mechs": bad_res["signal_b"]["missing"],
            },
        },
        "negative_control": {
            "reject_state": good_res["negative_control_reject_state"],
            "fixture": "command-center/p2-wave/probes/CNL-0056/fixtures/planted-bad.json",
            "what_the_check_does": negative_verbatim,
            "fires": True,
            "silent": False,
        },
        "reviewer": {
            "reviewer_id": "CNL-0056-recount-tabulator",
            "method": (
                "recursive JSON walk collecting idea records / cites_idea_ids / "
                "covers_mechanisms (recount.py), not the author's set-difference "
                "helpers. A disagreement in n_canonical, n_missing_ids, or "
                "n_missing_mechs blocks the unit."
            ),
            "independent": True,
            "verdict": "PASS",
            "known_good_agree": g_ok,
            "planted_bad_agree": b_ok,
            "runtime_drop_agree": d_ok,
            "numbers": {
                "known_good": {
                    "n_required": g_ind["n_required"],
                    "n_missing_ids": g_ind["n_missing_ids"],
                    "n_missing_mechs": g_ind["n_missing_mechs"],
                },
                "planted_bad": {
                    "n_required": b_ind["n_required"],
                    "n_missing_ids": b_ind["n_missing_ids"],
                    "n_missing_mechs": b_ind["n_missing_mechs"],
                    "missing_ids": b_ind["missing_ids"],
                },
            },
        },
        "evidence": [
            {
                "claim": "Known-good fixture is SILENT on both signals.",
                "signal_1": {
                    "kind": "command+output",
                    "command": (
                        "python3 -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0056'); "
                        "import ledger, json as J; d=J.load(open('command-center/p2-wave/probes/CNL-0056/fixtures/known-good.json')); "
                        "print(ledger.check_disappearance(d)['silent'], ledger.check_disappearance(d)['signal_a']['n_missing'])\""
                    ),
                    "verbatim": f"silent={good_res['silent']} n_missing_ids={good_res['signal_a']['n_missing']}",
                },
                "signal_2": {
                    "kind": "file:line plus independent walk",
                    "anchor": "command-center/p2-wave/probes/CNL-0056/recount.py:32",
                    "verbatim": (
                        f"n_required={g_ind['n_required']} n_missing_ids={g_ind['n_missing_ids']} "
                        f"n_missing_mechs={g_ind['n_missing_mechs']} agree={g_ok}"
                    ),
                },
                "verdict": "CONFIRMED",
            },
            {
                "claim": (
                    "Removing IDEA-0003 from synthesis makes the check FIRE "
                    "with missing_ids=[IDEA-0003] and the matching mechanism."
                ),
                "signal_1": {
                    "kind": "command+output",
                    "command": P1,
                    "verbatim": (
                        f"fired={drop_res['fired']} missing_ids={drop_res['signal_a']['missing']} "
                        f"missing_mechs={drop_res['signal_b']['missing']}"
                    ),
                },
                "signal_2": {
                    "kind": "different field",
                    "anchor": "command-center/p2-wave/probes/CNL-0056/ledger.py:68",
                    "verbatim": (
                        f"signal_b.missing={drop_res['signal_b']['missing']} "
                        f"n_missing={drop_res['signal_b']['n_missing']} "
                        f"field={drop_res['signal_b']['field']}"
                    ),
                },
                "verdict": "CONFIRMED",
            },
            {
                "claim": "Planted-bad fixture FIRES; known-good is SILENT (both-states).",
                "signal_1": {
                    "kind": "command+output",
                    "command": P2,
                    "verbatim": (
                        f"good.silent={good_res['silent']} bad.fired={bad_res['fired']} "
                        f"bad.missing_ids={bad_res['signal_a']['missing']}"
                    ),
                },
                "signal_2": {
                    "kind": "independent recount numbers",
                    "anchor": "command-center/p2-wave/probes/CNL-0056/recount.py",
                    "verbatim": (
                        f"good n_missing_ids={g_ind['n_missing_ids']} "
                        f"bad n_missing_ids={b_ind['n_missing_ids']} "
                        f"bad missing_ids={b_ind['missing_ids']}"
                    ),
                },
                "verdict": "CONFIRMED",
            },
            {
                "claim": (
                    "An originator, duplicate, supporter, and fate can be traced "
                    "for every fixture idea."
                ),
                "signal_1": {
                    "kind": "file:line",
                    "anchor": "command-center/p2-wave/probes/CNL-0056/fixtures/known-good.json",
                    "verbatim": (
                        "IDEA-0001 originator=P-alice duplicates=[IDEA-0004] "
                        "supporters=[P-bob] fate=ADOPTED/SYN-01; "
                        "IDEA-0003 originator=P-dave supporters=[P-alice] fate=DISSENTED/SYN-03"
                    ),
                },
                "signal_2": {
                    "kind": "schema keys present",
                    "anchor": "idea_ledger_schema required_keys",
                    "verbatim": list(L.REQUIRED_IDEA_KEYS),
                },
                "verdict": "CONFIRMED",
            },
        ],
        "failure_classes_addressed": {
            "detector-failure": "both-states plus runtime drop of IDEA-0003",
            "uncontrolled-silence": "SILENT only on known-good; FIRE on planted-bad",
            "gameable-metric": (
                "citing idea_ids without covers_mechanisms still FIREs (ghost); "
                "duplicates do not inflate the required set"
            ),
            "overclaim": (
                "scoped to four-idea fixtures on this worktree; not a 100-idea "
                "production run; CouncilSpec v2 root schema is absent"
            ),
        },
        "residual_unknowns": [
            "Harness restore files named in catalog inputs are absent here.",
            "CNL-0051 catalog artifact is not on this tree; duplicate_of is assumed emitted by it.",
            (
                "councilspec.v2.schema.json is a generated class shim, not a "
                "CouncilSpec v2 root envelope."
                if schema_on_disk
                else "command-center/schema/councilspec.v2.schema.json is absent (CNL-0001)."
            ),
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "the 100-unique-idea production target was measured",
            "semantic duplicate recall (rename/paraphrase/rewrite) — that is CNL-0051",
            "CouncilSpec v2 root envelope exists on disk",
        ],
        "named_probes": [
            {"id": "probe1", "role": "disappearing-idea", "command": P1},
            {"id": "probe2", "role": "both-states-negative-control", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {
                "path": "command-center/p2-wave/probes/CNL-0056/ledger.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "cloud_ok": False,
        "registered": True,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0056 emit self-declared")
        return 1
    if "SUCCESS:CNL-0056" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0056 emit sentinel")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"good_silent={good_res['silent']} bad_fired={bad_res['fired']} "
        f"drop_missing={drop_res['signal_a']['missing']}"
    )
    print("SUCCESS:CNL-0056 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
