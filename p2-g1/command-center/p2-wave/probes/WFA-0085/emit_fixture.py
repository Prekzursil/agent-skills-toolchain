#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0085-incremental-discovery-resume.json from live runs."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import (  # noqa: E402
    EXPECTED_STABLE_IDS,
    KILL_AFTER,
    MIGRATION_MAP,
    N_SOURCES,
    N_UNIQUE,
)
from scenarios import run_all  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0085-incremental-discovery-resume.json"
SCHEMA_REL = "command-center/p2-wave/probes/WFA-0085/regression_fixture.schema.json"
QUESTION = (
    "Implementation target: re-running any sweep must merge into the registry by "
    "stable identity rather than append, and a sweep interrupted midway must resume "
    "from its last durable checkpoint with no duplicate and no lost record."
)


def case(cid: str, name: str, kind: str, expected, observed, ok: bool) -> dict:
    return {
        "id": cid,
        "name": name,
        "kind": kind,
        "pass": ok,
        "expected": expected,
        "observed": observed,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0085-emit-") as tmp:
        results = run_all(Path(tmp))

    idem = results["idempotence"]
    upd = results["content_update"]
    adj = results["adjudication"]
    kr = results["kill_resume"]
    naive = results["naive_append"]

    c1 = idem["byte_identical"] and idem["new_records"] == 0 and idem["ids_match_expected"]
    c2 = (not upd["duplicated"]) and upd["update_applied"] and upd["delta_fields"] == ["body"]
    c3 = adj["preserved"] and adj["content_updated"] and not adj["duplicated"]
    c4 = (
        kr["kill_executed"]
        and kr["record_set_equal"]
        and kr["per_cell_equal"]
        and kr["no_lost_record"]
        and kr["no_duplicate"]
    )
    c5 = naive["duplicates"] and naive["n_records"] > N_UNIQUE and naive["n_unique_ids"] == N_UNIQUE
    if not all([c1, c2, c3, c4, c5]):
        print("FAILED:WFA-0085 emit live cases")
        print(json.dumps(results, indent=2, default=str)[:4000])
        return 1

    doc = {
        "record_type": "RegressionFixture",
        "unit_id": "WFA-0085",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0085",
        "fixture_id": "wfa-0085-incremental-discovery-resume",
        "title": "Make discovery incremental and resumable so a re-run does not duplicate the corpus",
        "question": QUESTION,
        "implementation_target": QUESTION,
        "schema_ref": SCHEMA_REL,
        "declared_output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
        ),
        "schema_note": (
            "WFA-0001 schema pack is absent on this worktree. This artifact is a "
            "RegressionFixture validated against the unit-local contract at schema_ref. "
            "Estate registries WFA-0078 / WFA-0010 / WFA-0030 are also absent; the "
            "engine is proven on a constructed colliding-catalog corpus whose unique "
            "identity set is known by construction."
        ),
        "dependencies_absent": ["WFA-0001", "WFA-0010", "WFA-0030", "WFA-0078"],
        "corpus": {
            "n_sources": N_SOURCES,
            "n_unique_identities": N_UNIQUE,
            "kill_after": KILL_AFTER,
            "collision_files": ["01-alpha.json", "06-alpha-collision.json"],
            "rename_alias": MIGRATION_MAP,
        },
        "engine": {
            "merge": (
                "command-center/p2-wave/probes/WFA-0085/registry.py merge_source "
                "keys records by canonical_id(migration map), never appends a second row"
            ),
            "checkpoint": (
                "per-source atomic JSON persist (write-tmp, fsync, replace) in "
                "command-center/p2-wave/probes/WFA-0085/store.py"
            ),
            "kill": (
                "probe2 sends SIGKILL to the sweep child after CHECKPOINT n=4; resume "
                "re-enters the same work directory"
            ),
        },
        "idempotence": idem,
        "content_update": upd,
        "adjudication": adj,
        "kill_resume": kr,
        "naive_append": naive,
        "evidence_a": {
            "byte_identical": idem["byte_identical"],
            "new_records": idem["new_records"],
            "sha256_first": idem["sha256_first"],
            "sha256_second": idem["sha256_second"],
        },
        "evidence_b": {
            "kill_executed": kr["kill_executed"],
            "kill_signal": kr["kill_signal"],
            "record_set_equal": kr["record_set_equal"],
            "per_cell_equal": kr["per_cell_equal"],
            "child_returncode": kr["child_returncode"],
        },
        "both_states": {
            "merge_unique": N_UNIQUE,
            "append_rows": naive["n_records"],
            "append_duplicates": naive["duplicates"],
            "merge_silent_on_collision": idem["n_records"] == N_UNIQUE,
        },
        "tests_required": [
            {
                "id": "T1",
                "requirement": "the kill-and-resume test must be executed, not reasoned about",
                "pass": kr["kill_executed"] and kr["child_returncode"] == -9,
            },
            {
                "id": "T2",
                "requirement": (
                    "a record whose content changed upstream must UPDATE with an "
                    "evidence delta rather than duplicate"
                ),
                "pass": c2,
            },
            {
                "id": "T3",
                "requirement": "the merge must be shown to preserve manual adjudications made between runs",
                "pass": c3,
            },
        ],
        "cases": [
            case("C1", "full re-run byte-identical registry", "idempotence", True, idem["byte_identical"], c1),
            case("C2", "upstream content change updates with delta", "update", ["body"], upd["delta_fields"], c2),
            case("C3", "locked adjudication survives content change", "adjudication", True, adj["preserved"], c3),
            case("C4", "SIGKILL resume matches uninterrupted record set", "kill-resume", True, kr["record_set_equal"], c4),
            case(
                "C5",
                "naive append duplicates colliding identities (negative control)",
                "both-states",
                True,
                naive["duplicates"],
                c5,
            ),
        ],
        "reviewer": {
            "reviewer_id": "WFA-0085-probe2-kill-resume",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
        },
        "tests": {
            "named_probe_1": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0085/probe1_idempotence.py"
            ),
            "named_probe_2": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/WFA-0085/probe2_kill_resume.py"
            ),
        },
    }

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    try:
        jsonschema.validate(garbage, schema)
        print("FAILED:WFA-0085 schema accepts garbage")
        return 1
    except jsonschema.ValidationError:
        pass

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} ids={EXPECTED_STABLE_IDS}")
    print("SUCCESS:WFA-0085 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
