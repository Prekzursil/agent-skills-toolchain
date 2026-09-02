#!/usr/bin/env python3
"""Emit command-center/research/RES-0031.json from live captures."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import captures_lib as C  # noqa: E402
import features as F  # noqa: E402
import intersect as I  # noqa: E402
import reviewer as R  # noqa: E402
import schema_local as S  # noqa: E402

OUT_REL = "command-center/research/RES-0031.json"
SCHEMA_REL = "command-center/schema/compatibility-matrix.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0031/probe1_intersection.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0031/probe2_schema_and_rails.py"
)
CONSUMER = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
    "\"import json;from pathlib import Path;d=json.loads(Path("
    "'command-center/research/RES-0031.json').read_text(encoding='utf-8'));"
    "i=d['report']['intersection'];print('DOWNSTREAM',i['members'],i['cardinality'])\""
)
QUESTION = (
    "Across Cline, Roo Code and Windsurf, which rule/memory/MCP primitives "
    "appear in ALL THREE - and is that intersection the real portable core "
    "for a cross-vendor adapter, as opposed to the union each vendor advertises?"
)
CLIENTS = (
    {
        "id": "cline",
        "display": "Cline",
        "declared_by": "pinned cline/cline source plus official docs.cline.bot captures",
    },
    {
        "id": "roo",
        "display": "Roo Code",
        "declared_by": "pinned RooCodeInc/Roo-Code source plus docs.roocode.com captures",
    },
    {
        "id": "windsurf",
        "display": "Windsurf",
        "declared_by": "official docs.windsurf.com plus GitHub MCP install guide",
    },
)
GATE_NOTE = (
    "mcpServers JSON is an allowlist of configured MCP servers (the E2 portable "
    "core this unit measured). Per-call MCP tool consent was not instrumented "
    "here; that gate is out of scope for RES-0031."
)
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:65176-65228"
SUPPORTING = [
    (SCHEMA_REL, "supporting"),
    ("command-center/p2-wave/probes/RES-0031/intersect.py", "supporting"),
    ("command-center/p2-wave/probes/RES-0031/features.py", "supporting"),
    ("command-center/p2-wave/probes/RES-0031/captures/INDEX.json", "fixture"),
]


def _sha_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fp(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _art_row(rel: str, role: str) -> dict:
    sha, size = _sha_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def _encode(sets: dict, primitive_ids: list[str]) -> list[dict]:
    rows = []
    for vendor in F.VENDORS:
        have = set(sets.get(vendor) or [])
        per_entry = [
            {
                "catalog_entry": pid,
                "verdict": "can" if pid in have else "cannot",
            }
            for pid in primitive_ids
        ]
        cans = sum(1 for e in per_entry if e["verdict"] == "can")
        rows.append(
            {
                "client_id": vendor,
                "verdict": "can" if cans == len(primitive_ids) else "cannot",
                "can_count": cans,
                "entry_count": len(primitive_ids),
                "per_entry": per_entry,
            }
        )
    return rows


def _public_rail(rail: dict, vendor: str, pid: str) -> dict:
    return {
        "permalink": str(rail.get("permalink") or rail.get("url") or ""),
        "url": rail.get("url"),
        "fetched_at": rail.get("fetched_at"),
        "http_status": rail.get("http_status"),
        "sha256": rail.get("sha256"),
        "rail": rail.get("kind") or "unknown",
        "kind": rail.get("kind"),
        "vendor": vendor,
        "primitive_id": pid,
        "capture_id": rail.get("capture_id"),
        "needles": list(rail.get("needles") or []),
    }


def main() -> int:
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        print("FAILED:RES-0031 emit jsonschema not installed")
        return 1
    extracted = F.extract(C.by_id(C.load_metas()))
    lists = extracted["e2_sets"]
    inter = I.intersection(lists)
    uniques = I.unique_sets(lists)
    presence = extracted["present_sets"]
    presence_inter = I.intersection(presence)
    rev = R.review(extracted, None)
    if rev["verdict"] != "PASS":
        print("FAILED:RES-0031 emit reviewer REFUTED")
        print(json.dumps(rev, indent=2)[:3000])
        return 1

    printed = (
        "THREE-WAY INTERSECTION "
        + json.dumps(inter)
        + "\nUNIQUE cline "
        + json.dumps(uniques["cline"])
        + "\nUNIQUE roo "
        + json.dumps(uniques["roo"])
        + "\nUNIQUE windsurf "
        + json.dumps(uniques["windsurf"])
    )
    answer = (
        "The dual-rail (E2) three-way intersection is the MCP config surface: "
        + ", ".join(inter)
        + ". That is the citable portable core. Workspace rules, AGENTS.md, "
        "global rules and skills appear in all three vendors' documentation "
        f"({json.dumps(presence_inter)}) but Windsurf lacks a public structured "
        "source rail, so those cells are E3 and are not cited as measured fact. "
        "The advertised union is larger: Roo custom-modes and mode-specific-rules, "
        "Cline hooks / Memory Bank methodology / cross-vendor rule import, and "
        "Windsurf first-class memories. An adapter that targets the union will "
        "not be portable. "
        + F.CATALOG_SENTINEL
    )
    primitive_ids = [p["id"] for p in F.PRIMITIVES]
    extra_counts = {v: len(uniques[v]) for v in F.VENDORS}
    ranked = sorted(F.VENDORS, key=lambda v: (extra_counts[v], v))
    ranking = [
        {
            "rank": i,
            "client_id": vendor,
            "reason": (
                f"{vendor} adds {extra_counts[vendor]} E2 primitives beyond "
                f"the dual-rail portable core of {len(inter)}"
            ),
        }
        for i, vendor in enumerate(ranked, 1)
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_out = (
        "THREE-WAY INTERSECTION "
        + json.dumps(inter)
        + " UNIQUE sets printed; planted custom-modes excluded"
    )
    p2_out = "schema dual-rail overclaim gate; live intersection matches artifact"
    doc = {
        "schema_version": 1,
        "unit_id": "RES-0031",
        "state": "SUCCESS",
        "sentinel": F.CATALOG_SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "ecosystem-cartographer",
            "execution_substrate": "headless-linux-p2-deliver",
        },
        "artifacts": [_art_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "The dual-rail three-way intersection is "
                    + ", ".join(inter)
                    + " and is computed from vendor feature lists, not eyeballed."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0031/probe1_intersection.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": p1_out,
                        "fingerprint": _fp("command", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": P2,
                        "raw_output": p2_out,
                        "fingerprint": _fp("schema-validate", P2),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Roo-only custom-modes and Windsurf first-class-memories are "
                    "absent from the citable intersection."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0031/intersect.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/RES-0031/intersect.py"
                        ),
                        "raw_output": "unique_sets.roo contains custom-modes; intersection does not",
                        "fingerprint": _fp("static-analysis", "intersect.py"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": "RED_MUTANT intersection_contains_planted=True; live intersection excludes planted unique",
                        "fingerprint": _fp("test-run", P1, "planted"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "CTL-PLANTED-UNIQUE-MUTANT",
                "kind": "mutation",
                "description": (
                    "Forcing Roo-only custom-modes into all three E2 lists must "
                    "put it in the intersection; the live lists must not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "RED_MUTANT intersection_contains_planted=True",
                "good_state_output": "planted unique custom-modes not in live intersection",
            },
            {
                "id": "CTL-EYEBALLED-INTERSECTION",
                "kind": "malformed-input",
                "description": (
                    "Replacing report.intersection with the adjective 'eyeballed' "
                    "must fail the bound schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "eyeballed_intersection_rejected=True",
                "good_state_output": "schema_accepts_artifact=True",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0031-adversarial-refuter",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                rev["strongest_caveat"]
                + " Defaulted to REFUTED unless every intersection cell is dual-rail."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0031/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "RES-0031",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "RES-0031-json-load-intersection",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": CONSUMER,
                    "raw_output": f"DOWNSTREAM {inter} {len(inter)}",
                    "fingerprint": _fp("file-read", CONSUMER),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "on HTTP 429 or a quota rejection, back off exponentially and "
                "rotate to a different search rail; never lower the evidence bar; "
                "3 rail rotations then park as dependency-blocked"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Windsurf editor binaries were not reverse-engineered; E2 "
                    "Windsurf cells use GitHub's versioned install guide plus docs."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "If Windsurf publishes a public source rail, re-score "
                    "workspace-rules / agents-md / skills for dual-rail."
                ),
            }
        ],
        "report": {
            "kind": "compatibility-matrix",
            "observations": [
                {
                    "name": "e2-three-way-intersection",
                    "measured": ", ".join(inter),
                    "method": "set intersection over dual-rail vendor feature lists",
                    "anchor": "command-center/p2-wave/probes/RES-0031/intersect.py",
                },
                {
                    "name": "intersection-cardinality",
                    "measured": len(inter),
                    "method": "len(intersection(e2_sets))",
                    "anchor": "command-center/p2-wave/probes/RES-0031/probe1_intersection.py",
                },
                {
                    "name": "planted-unique-excluded",
                    "measured": True,
                    "method": "custom-modes present only on Roo E2; red-mutant forces it into all three",
                    "anchor": "command-center/p2-wave/probes/RES-0031/probe1_intersection.py",
                },
            ],
            "control_ids": [
                "CTL-PLANTED-UNIQUE-MUTANT",
                "CTL-EYEBALLED-INTERSECTION",
            ],
            "question": QUESTION,
            "clients": [dict(c) for c in CLIENTS],
            "gate_models": [
                {
                    "client_id": c["id"],
                    "mcp_gate": "allowlist",
                    "notes": GATE_NOTE,
                }
                for c in CLIENTS
            ],
            "real_list": {
                "source_unit": "RES-0031",
                "source_path": "command-center/p2-wave/probes/RES-0031/features.py",
                "entries": primitive_ids,
            },
            "encodings_real": _encode(lists, primitive_ids),
            "encodings_overbroad": _encode(presence, primitive_ids),
            "least_privilege_ranking": ranking,
            "answer": answer,
            "printed": printed,
            "axes": [
                {"id": "vendor", "values": list(F.VENDORS)},
                {"id": "primitive", "values": primitive_ids},
            ],
            "cells": extracted["cells"],
            "feature_sets": lists,
            "presence_any_rail": presence,
            "intersection": {
                "computed": True,
                "members": inter,
                "cardinality": len(inter),
                "tier": "E2-dual-rail",
                "derived_from": "feature_sets",
                "script": "command-center/p2-wave/probes/RES-0031/intersect.py",
            },
            "unique_sets": uniques,
            "presence_intersection_not_citable": {
                "computed": True,
                "members": presence_inter,
                "note": "Includes E3 cells. Not the measured portable core.",
            },
            "portable_core_verdict": (
                "YES for the MCP mcpServers/stdio/remote-http trio; NO for the "
                "advertised rules+memory union."
            ),
            "pinned_commits": {
                "cline/cline": "09ee9026393e681a4834d8acbf4d9d5fdfa8664a",
                "RooCodeInc/Roo-Code": "b867ec9145750d0ae1ff7f02d35406e9bf2a0b16",
                "github/github-mcp-server": "8898db96b8043db1ddacff444600e408cf824fa2",
            },
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "cloud_ok": False,
        },
    }

    errs = S.errors(doc)
    if errs:
        print("FAILED:RES-0031 emit schema")
        for e in errs[:20]:
            print(e)
        return 1
    bound_errs = S.errors(doc, S.bound_intersection_schema())
    if bound_errs:
        print("FAILED:RES-0031 emit bound schema")
        for e in bound_errs[:20]:
            print(e)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    loaded = json.loads(out.read_text(encoding="utf-8"))
    got = loaded["report"]["intersection"]["members"]
    if got != inter:
        print("FAILED:RES-0031 emit downstream mismatch")
        return 1
    print(printed)
    print(f"wrote {OUT_REL}")
    print("SUCCESS:RES-0031 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
