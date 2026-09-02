#!/usr/bin/env python3
"""Known 31-way M-NN corpus, clean/planted controls, and the three catalog tests."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import collision as C

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
KNOWN_DIR = FIX / "known-31way"
CLEAN_DIR = FIX / "clean"
PLANTED_DIR = FIX / "planted"

OPTION_NS = "option-universe"
MECH_NS = "architecture-mech"
WAVE3_NS = "wave3-deep-research"
WAVE1_NS = "wave1-register"

OPTION_IDS = list(range(1, 34))
MECH_IDS = list(range(1, 32)) + list(range(34, 41))
WAVE3_IDS = [16]
WAVE1_IDS = [1, 3]
KNOWN_COLLISION_NUMBERS = sorted(set(OPTION_IDS) & set(MECH_IDS))
KNOWN_COLLISION_SET = [f"M-{n}" for n in KNOWN_COLLISION_NUMBERS]


def dump(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_known_fixtures() -> dict[str, Path]:
    option_records = [
        {
            "id": f"M-{n}",
            "title": f"Family-M option card {n}",
            "definition": (
                f"Option-universe family M card {n}: a selectable program option "
                "with an owner-facing tradeoff. This is not an architecture mechanism."
            ),
        }
        for n in OPTION_IDS
    ]
    mech_records = [
        {
            "id": f"M-{n}",
            "title": f"Architecture mechanism {n}",
            "definition": (
                f"Architecture-candidate mechanism {n}: an implementation mechanism "
                "card describing a runtime shape. This is not a family-M option."
            ),
        }
        for n in MECH_IDS
    ]
    written = {
        "options": KNOWN_DIR / "option-universe.json",
        "mechanisms": KNOWN_DIR / "architecture-mechanisms.json",
        "wave3": KNOWN_DIR / "wave3-deep-research.json",
        "wave1": KNOWN_DIR / "wave1-register.json",
        "blueprints": KNOWN_DIR / "blueprints.json",
        "presets": KNOWN_DIR / "presets.json",
    }
    dump(
        written["options"],
        {"namespace": OPTION_NS, "kind": "option", "options": option_records},
    )
    dump(
        written["mechanisms"],
        {"namespace": MECH_NS, "kind": "mechanism", "mechanisms": mech_records},
    )
    dump(
        written["wave3"],
        {
            "namespace": WAVE3_NS,
            "kind": "skill",
            "records": [
                {
                    "id": "M-16",
                    "title": "Research Harness",
                    "definition": (
                        "Wave3 deep-research SKILL.md Research Harness (M-16). "
                        "Neither an option-universe card nor an architecture mechanism."
                    ),
                }
            ],
        },
    )
    dump(
        written["wave1"],
        {
            "namespace": WAVE1_NS,
            "kind": "register",
            "records": [
                {
                    "id": f"M-{n}",
                    "title": f"Wave1 mission-grade M-{n}",
                    "definition": (
                        f"Wave1 REGISTER.md mission-grade identifier M-{n}. "
                        "Not an option card and not a mechanism card."
                    ),
                }
                for n in WAVE1_IDS
            ],
        },
    )
    dump(
        written["blueprints"],
        {
            "namespace": "blueprint-catalog",
            "kind": "blueprint",
            "blueprints": [
                {
                    "id": "BP-KNOWN-0001",
                    "title": "Discovery-only blueprint",
                    "definition": "A unique blueprint id used as a negative control.",
                }
            ],
        },
    )
    dump(
        written["presets"],
        {
            "namespace": "preset-catalog",
            "kind": "preset",
            "presets": [
                {
                    "id": "PRE-KNOWN-0001",
                    "title": "Council preset",
                    "definition": "A unique preset id used as a negative control.",
                }
            ],
        },
    )
    return written


def write_clean_fixtures() -> dict[str, Path]:
    written = {
        "options": CLEAN_DIR / "options.json",
        "units": CLEAN_DIR / "work-units.json",
        "blueprints": CLEAN_DIR / "blueprints.json",
        "presets": CLEAN_DIR / "presets.json",
    }
    dump(
        written["options"],
        {
            "namespace": "clean-options",
            "kind": "option",
            "options": [
                {
                    "id": "OPT-CLEAN-1",
                    "title": "Clean option 1",
                    "definition": "Unique option definition A.",
                },
                {
                    "id": "OPT-CLEAN-2",
                    "title": "Clean option 2",
                    "definition": "Unique option definition B.",
                },
            ],
        },
    )
    dump(
        written["units"],
        {
            "namespace": "clean-work-units",
            "kind": "work_unit",
            "work_units": [
                {
                    "id": "TST-CLEAN-0001",
                    "title": "Clean unit 1",
                    "definition": "Unique work unit A.",
                },
                {
                    "id": "TST-CLEAN-0002",
                    "title": "Clean unit 2",
                    "definition": "Unique work unit B.",
                },
            ],
        },
    )
    dump(
        written["blueprints"],
        {
            "namespace": "clean-blueprints",
            "blueprints": [
                {
                    "id": "BP-CLEAN-1",
                    "title": "Clean blueprint",
                    "definition": "Unique blueprint.",
                }
            ],
        },
    )
    dump(
        written["presets"],
        {
            "namespace": "clean-presets",
            "presets": [
                {
                    "id": "PRE-CLEAN-1",
                    "title": "Clean preset",
                    "definition": "Unique preset.",
                }
            ],
        },
    )
    return written


def write_planted_fixtures() -> dict[str, Path]:
    written = {
        "def_a": PLANTED_DIR / "blueprint-meaning-a.json",
        "def_b": PLANTED_DIR / "blueprint-meaning-b.json",
        "dup_a": PLANTED_DIR / "units-slice-a.json",
        "dup_b": PLANTED_DIR / "units-slice-b.json",
    }
    dump(
        written["def_a"],
        {
            "namespace": "planted-blueprint-a",
            "blueprints": [
                {
                    "id": "BP-TWOMEAN",
                    "title": "Meaning A",
                    "definition": "Planted definition A: a load-bearing ingest blueprint.",
                }
            ],
        },
    )
    dump(
        written["def_b"],
        {
            "namespace": "planted-blueprint-b",
            "blueprints": [
                {
                    "id": "BP-TWOMEAN",
                    "title": "Meaning B",
                    "definition": "Planted definition B: an unrelated publish blueprint.",
                }
            ],
        },
    )
    dump(
        written["dup_a"],
        {
            "namespace": "catalog-slice-a",
            "work_units": [
                {
                    "id": "TST-DUP-0001",
                    "title": "Slice A copy",
                    "definition": "Work unit from colliding catalog slice A.",
                },
                {
                    "id": "TST-UNIQ-0001",
                    "title": "Unique from A",
                    "definition": "A unique unit that must still be allowed to run.",
                },
            ],
        },
    )
    dump(
        written["dup_b"],
        {
            "namespace": "catalog-slice-b",
            "work_units": [
                {
                    "id": "TST-DUP-0001",
                    "title": "Slice B copy",
                    "definition": "Work unit from colliding catalog slice B.",
                },
                {
                    "id": "TST-UNIQ-0002",
                    "title": "Unique from B",
                    "definition": "Another unique unit that must still be allowed to run.",
                },
            ],
        },
    )
    return written


def ensure_fixtures() -> None:
    write_known_fixtures()
    write_clean_fixtures()
    write_planted_fixtures()


def json_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.json") if p.is_file())


def extract_dir(root: Path) -> list[dict[str, Any]]:
    return C.extract_paths(json_files(root), repo=REPO)


def cc0023_collision_numbers() -> list[int] | None:
    ns_path = REPO / "command-center/p2-wave/probes/CC-0023/namespaces.py"
    if not ns_path.is_file():
        return None
    import importlib.util

    spec = importlib.util.spec_from_file_location("tst0095_cc0023_ns", ns_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.collision_numbers())


def live_catalog_rows() -> list[dict[str, Any]]:
    path = REPO / "command-center/WORK-UNIT-CATALOG.json"
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    units = doc.get("work_units") if isinstance(doc, dict) else None
    if not isinstance(units, list):
        return []
    wrapped = {
        "namespace": "work-unit-catalog",
        "kind": "work_unit",
        "work_units": [
            {
                "id": u.get("id"),
                "title": u.get("title") or "",
                "definition": (
                    u.get("question_or_target") or u.get("title") or u.get("id") or ""
                ),
            }
            for u in units
            if isinstance(u, dict)
        ],
    }
    return C.extract_document(
        wrapped,
        path="command-center/WORK-UNIT-CATALOG.json",
        default_namespace="work-unit-catalog",
    )


def test_extractor_reproduces_the_known_collision_set() -> dict[str, Any]:
    ensure_fixtures()
    rows = extract_dir(KNOWN_DIR)
    mapping = C.id_map(rows)
    got = C.intersecting_ids(mapping, OPTION_NS, MECH_NS)
    option_rows = C.extract_path(KNOWN_DIR / "option-universe.json", repo=REPO)
    option_map = C.id_map(option_rows)
    option_vs_self = C.intersecting_ids(option_map, OPTION_NS, MECH_NS)
    empty_vs = C.intersecting_ids(C.id_map([]), OPTION_NS, MECH_NS)
    cc_nums = cc0023_collision_numbers()
    cc_ok = cc_nums is None or cc_nums == KNOWN_COLLISION_NUMBERS
    extra = {
        ident: sorted({d["namespace"] for d in mapping[ident]})
        for ident in ("M-1", "M-3", "M-16")
        if ident in mapping
    }
    ok = (
        got == KNOWN_COLLISION_SET
        and len(got) == 31
        and option_vs_self == []
        and empty_vs == []
        and cc_ok
        and set(extra.get("M-16") or []) >= {OPTION_NS, MECH_NS, WAVE3_NS}
        and set(extra.get("M-1") or []) >= {OPTION_NS, MECH_NS, WAVE1_NS}
        and set(extra.get("M-3") or []) >= {OPTION_NS, MECH_NS, WAVE1_NS}
        and "BP-KNOWN-0001" in mapping
        and mapping["BP-KNOWN-0001"][0]["kind"] == "blueprint"
        and "PRE-KNOWN-0001" in mapping
    )
    return {
        "id": "test_extractor_reproduces_the_known_collision_set",
        "ok": ok,
        "got": got,
        "expected": KNOWN_COLLISION_SET,
        "count": len(got),
        "single_namespace_false_positive": option_vs_self,
        "empty_corpus_false_positive": empty_vs,
        "cc0023_collision_numbers": cc_nums,
        "cc0023_agrees": cc_ok,
        "third_fourth_namespaces": extra,
        "id_count": len(mapping),
        "record_count": len(rows),
    }


def test_gate_fails_on_any_id_with_two_definitions() -> dict[str, Any]:
    ensure_fixtures()
    known = C.gate(extract_dir(KNOWN_DIR))
    clean = C.gate(extract_dir(CLEAN_DIR))
    planted = C.gate(extract_dir(PLANTED_DIR))
    planted_only = C.gate(
        C.extract_paths(
            [
                PLANTED_DIR / "blueprint-meaning-a.json",
                PLANTED_DIR / "blueprint-meaning-b.json",
            ],
            repo=REPO,
        )
    )
    ok = (
        known["ok"] is False
        and set(KNOWN_COLLISION_SET).issubset(set(known["colliding_ids"]))
        and clean["ok"] is True
        and clean["colliding_ids"] == []
        and planted_only["ok"] is False
        and "BP-TWOMEAN" in planted_only["colliding_ids"]
        and planted["ok"] is False
    )
    return {
        "id": "test_gate_fails_on_any_id_with_two_definitions",
        "ok": ok,
        "known_gate_ok": known["ok"],
        "known_collision_count": len(known["colliding_ids"]),
        "clean_gate_ok": clean["ok"],
        "planted_id_named": "BP-TWOMEAN" in planted_only["colliding_ids"],
        "planted_colliding_ids": planted_only["colliding_ids"],
        "reason": known.get("reason"),
    }


def test_dispatch_refuses_to_run_two_units_with_the_same_id() -> dict[str, Any]:
    ensure_fixtures()
    units = [r for r in extract_dir(PLANTED_DIR) if r["kind"] == "work_unit"]
    result = C.dispatch(units)
    refused_ids = set(result["refused_ids"])
    ran_ids = [u["id"] for u in result["ran"]]
    dup_refused = [r for r in result["refused"] if r["id"] == "TST-DUP-0001"]
    clean_units = [r for r in extract_dir(CLEAN_DIR) if r["kind"] == "work_unit"]
    clean = C.dispatch(clean_units)
    ok = (
        result["ok"] is False
        and refused_ids == {"TST-DUP-0001"}
        and len(dup_refused) == 2
        and "TST-DUP-0001" not in ran_ids
        and set(ran_ids) == {"TST-UNIQ-0001", "TST-UNIQ-0002"}
        and clean["ok"] is True
        and clean["refused"] == []
        and {u["id"] for u in clean["ran"]} == {"TST-CLEAN-0001", "TST-CLEAN-0002"}
    )
    return {
        "id": "test_dispatch_refuses_to_run_two_units_with_the_same_id",
        "ok": ok,
        "refused_ids": result["refused_ids"],
        "refused_count": len(result["refused"]),
        "ran_ids": ran_ids,
        "clean_dispatch_ok": clean["ok"],
    }


def run_required_tests() -> dict[str, Any]:
    tests = [
        test_extractor_reproduces_the_known_collision_set(),
        test_gate_fails_on_any_id_with_two_definitions(),
        test_dispatch_refuses_to_run_two_units_with_the_same_id(),
    ]
    return {"ok": all(t["ok"] for t in tests), "tests": tests}


def evidence_bundle() -> dict[str, Any]:
    ensure_fixtures()
    known_rows = extract_dir(KNOWN_DIR)
    known_map = C.id_map(known_rows)
    live_rows = live_catalog_rows()
    live_map = C.id_map(live_rows)
    live_multi = C.multi_definition_ids(live_map)
    known_multi = C.multi_definition_ids(known_map)
    option_mech = C.intersecting_ids(known_map, OPTION_NS, MECH_NS)
    return {
        "known_collision_set": option_mech,
        "known_collision_count": len(option_mech),
        "known_multi_definition_ids": known_multi,
        "known_id_to_definitions": C.compact_map(known_map),
        "known_id_count": len(known_map),
        "namespaces_scanned": sorted({r["namespace"] for r in known_rows}),
        "live_catalog_id_count": len(live_map),
        "live_catalog_record_count": len(live_rows),
        "live_catalog_multi_definition_ids": live_multi,
        "live_catalog_path": "command-center/WORK-UNIT-CATALOG.json",
        "original_markdown_option_universe_present": (REPO / "07-OPTION-UNIVERSE.md").is_file(),
        "original_markdown_architecture_candidates_present": (
            REPO / "13-ARCHITECTURE-CANDIDATES.md"
        ).is_file(),
        "option_id_resolution_present": (
            REPO / "command-center/OPTION-ID-RESOLUTION.json"
        ).is_file(),
        "extractor_proven_on_known_case_before_live_zero_trusted": option_mech
        == KNOWN_COLLISION_SET,
    }


if __name__ == "__main__":
    ensure_fixtures()
    report = run_required_tests()
    print(json.dumps({"ok": report["ok"]}, indent=2, sort_keys=True))
    for test in report["tests"]:
        print(f"{test['id']} ok={test['ok']}")
    raise SystemExit(0 if report["ok"] else 1)
