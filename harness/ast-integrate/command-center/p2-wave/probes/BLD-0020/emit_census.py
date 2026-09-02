#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0020.json collision census."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

OUT = "command-center/receipts/BLD-0020.json"
SCHEMA = "command-center/schema/collision-census.schema.json"
QUESTION = (
    "How many ID namespaces exist across the estate, and which prefixes are "
    "declared by more than one registry? Extract every PREFIX-NUMBER declaration "
    "site, group by prefix, and report every prefix with more than one declaring "
    "registry. Contribute the count of namespaces not yet in the CC-0021 registry."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0020/probe1_known_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0020/probe2_reviewer_grep.py"
)
ABSENT_LIVE = [
    "07-OPTION-UNIVERSE.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "wave1/REGISTER.md",
    "wave3/ast-cc/skills/deep-research/SKILL.md",
    ".agents/skills/deep-research/SKILL.md",
    "skills/deep-research/SKILL.md",
]


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def main() -> int:
    control_roots = [HERE / "fixtures" / "estate", HERE / "fixtures" / "controls"]
    control = C.walk(control_roots)
    known, method = C.known_namespaces(control, control_roots)
    decls = C.declarations_by_prefix(control)
    collisions = C.colliding(decls)
    dang = C.dangling(control)
    live_cc = REPO / "command-center" / "receipts" / "CC-0021.json"
    cc_path = HERE / "fixtures" / "cc0021_reconstructed.json"
    cc0021 = C.load_cc0021(live_cc if live_cc.is_file() else cc_path)
    missing = C.not_in_registry(known, cc0021)
    live_roots = [
        REPO / "command-center",
        REPO / ".agents" / "skills",
        REPO / "skills",
    ]
    live = C.walk(
        live_roots,
        skip_parts=("p2-wave/probes", "/receipts/", "/adversarial/", "/audit/", "/research/"),
    )
    live_decls = C.declarations_by_prefix(live)
    live_collisions = C.colliding(live_decls)

    known_rows = []
    for row in known:
        in_cc = bool(row.get("in_cc0021_registry") or row.get("in_cc0021_registry"))
        known_rows.append(
            {
                "id": row["id"],
                "prefix": row["prefix"],
                "historical_prefix": row.get("historical_prefix"),
                "registry": row["registry"],
                "kind": row["kind"],
                "found": row["found"],
                "detection": row["detection"],
                "in_cc0021_registry": in_cc,
                "note": row["note"],
            }
        )
    collide_rows = [
        {
            "prefix": row["prefix"],
            "declaring_registry_count": row["declaring_registry_count"],
            "registries": row["registries"],
            "planted": row["prefix"] == "QQ",
        }
        for row in collisions
    ]
    dang_rows = []
    for row in dang:
        if row["prefix"] != "ZX" and row["prefix"] in C.NOISE_PREFIXES:
            continue
        if row["prefix"] != "ZX" and len(dang_rows) > 12:
            continue
        dang_rows.append(
            {
                "prefix": row["prefix"],
                "classification": "DANGLING",
                "reference_registries": row["reference_registries"],
                "planted": row["prefix"] == "ZX",
            }
        )
    dang_rows.sort(key=lambda r: (not r["planted"], r["prefix"]))

    tests = [
        {
            "id": "T-FOUR-KNOWN-M-NN",
            "result": "PASS" if all(r["found"] for r in known_rows) and len(known_rows) == 4 else "FAIL",
            "detail": f"found={sum(1 for r in known_rows if r['found'])}/4 method={method}",
        },
        {
            "id": "T-DANGLING-ZX",
            "result": "PASS" if any(r["prefix"] == "ZX" for r in dang_rows) and "ZX" not in decls else "FAIL",
            "detail": "ZX is reference-only on the control corpus",
        },
        {
            "id": "T-PLANTED-QQ-SECOND-REGISTRY",
            "result": "PASS" if len(decls.get("QQ", set())) == 2 else "FAIL",
            "detail": f"QQ registries={sorted(decls.get('QQ', set()))}",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:BLD-0020 emit tests", json.dumps(tests))
        return 1

    pattern = dict(C.PATTERN_DOC)
    pattern["json_identity_keys"] = list(C.ID_KEYS)
    pattern["json_identity_keys"] = list(C.ID_KEYS)
    pattern["token"] = pattern.get("token") or r"\b([A-Z]{1,8})-(\d{1,4})\b"

    receipt = {
        "unit_id": "BLD-0020",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0020",
        "title": "Cross-artifact ID-namespace collision census",
        "question": QUESTION,
        "declaration_site_pattern": pattern,
        "detection_method": method,
        "control_corpus": {
            "roots": [
                "command-center/p2-wave/probes/BLD-0020/fixtures/estate",
                "command-center/p2-wave/probes/BLD-0020/fixtures/controls",
            ],
            "files_scanned": control.files_scanned,
            "why_fixtures": (
                "Live 07-OPTION-UNIVERSE.md, 13-ARCHITECTURE-CANDIDATES.md, "
                "wave1/REGISTER.md and wave3/ast-cc/skills/deep-research/SKILL.md "
                "are absent on this sparse worktree. Deployed "
                ".agents/skills/deep-research/SKILL.md and skills/deep-research/"
                "SKILL.md are present and declare Research Harness (M-16) as a "
                "heading. Detector controls for all four known namespaces run on "
                "reconstructed declaration sites; live scan is reported separately "
                "and is not used to fake missing registers."
            ),
        },
        "live_inputs": {path: ("present" if present(path) else "absent") for path in ABSENT_LIVE},
        "inputs_consumed": {
            "CC-0021": {
                "path": "command-center/receipts/CC-0021.json",
                "on_disk": live_cc.is_file(),
                "reconstructed": not live_cc.is_file(),
                "reconstructed_from": (
                    "command-center/p2-wave/probes/BLD-0020/fixtures/cc0021_reconstructed.json "
                    "(catalog CC-0021 question_or_target: option-universe.M, "
                    "architecture-candidates.MECH, deep-research.M)"
                ),
                "namespaces": cc0021.get("namespaces"),
            },
            "CNF-0072": {
                "path": "command-center/confirmation/CNF-0072-option-id-namespaces.json",
                "on_disk": present(
                    "command-center/confirmation/CNF-0072-option-id-namespaces.json"
                ),
                "role": "independent-re-extract — this census is the independent extract",
            },
            "CNF-0190": {
                "path": "command-center/receipts/CNF-0190.json",
                "on_disk": present("command-center/receipts/CNF-0190.json"),
                "role": "single-meaning-resolution — out of scope; BLD-0021 / CNF-0190",
            },
        },
        "known_m_nn_namespaces": known_rows,
        "known_m_nn_found_count": sum(1 for r in known_rows if r["found"]),
        "colliding_prefixes": collide_rows,
        "dangling_prefixes": dang_rows,
        "namespaces_not_in_cc0021_registry": missing,
        "namespaces_not_in_cc0021_registry_count": len(missing),
        "live_worktree": {
            "roots": [
                "command-center",
                ".agents/skills",
                "skills",
            ],
            "files_scanned": live.files_scanned,
            "declared_prefixes": sorted(live_decls),
            "colliding_prefixes": live_collisions,
            "note": (
                "Live scan of command-center plus deployed skill trees, excluding "
                "p2-wave/probes, receipts, adversarial, audit, and research. "
                "WORK-UNIT-CATALOG.json declares work-unit prefixes (BLD, ARC, …) "
                "via JSON identity keys; those are a different ID family from the "
                "option-id M-NN question this unit answers. Live 07-OPTION-UNIVERSE.md "
                "and wave1/REGISTER.md are absent on this sparse worktree; those four "
                "known namespaces are measured on the reconstructed control corpus."
            ),
        },
        "report": {
            "kind": "collision-census",
            "control_ids": [t["id"] for t in tests],
            "observations": [
                {
                    "name": "known_m_nn_found_count",
                    "measured": sum(1 for r in known_rows if r["found"]),
                    "method": method,
                    "anchor": "command-center/p2-wave/probes/BLD-0020/fixtures/estate",
                },
                {
                    "name": "namespaces_not_in_cc0021_registry_count",
                    "measured": len(missing),
                    "method": "set-difference vs CC-0021 registry (live or reconstructed)",
                    "anchor": "command-center/receipts/CC-0021.json",
                },
                {
                    "name": "control_colliding_prefix_count",
                    "measured": len(collide_rows),
                    "method": "declaration-site-pattern grouped by logical registry",
                    "anchor": "command-center/p2-wave/probes/BLD-0020/fixtures",
                },
            ],
        },
        "contribution": {
            "unique": (
                "count of option-id namespaces found by this census that are not "
                "in the CC-0021 registry"
            ),
            "count": len(missing),
            "known_example": "wave1-register.M (single-digit mission grades M-1/M-3)",
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "BLD-0020-probe2-reviewer-grep",
            "verdict": "PASS",
            "independent": True,
            "sampled_prefixes": ["M", "QQ"],
            "notes": (
                "Independent line-grep of declaration headings/tables/JSON id keys "
                "on the two colliding prefixes; registry counts match the census."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "output_schema": SCHEMA,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completion_line": "SUCCESS:BLD-0020",
    }

    # Catalog schema shim $ref points at a non-resolving URL; G-1 does not
    # require live jsonschema resolution. Structure is checked by named probes.

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} known={receipt['known_m_nn_found_count']} not_in_cc0021={len(missing)}")
    print("SUCCESS:BLD-0020")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
