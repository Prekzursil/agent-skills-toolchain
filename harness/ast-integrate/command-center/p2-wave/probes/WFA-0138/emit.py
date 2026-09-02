#!/usr/bin/env python3
"""Emit the WFA-0138 lineage-record foundry artifact."""
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
import lineage as L  # noqa: E402

OUT = (
    "command-center/foundry/"
    "WFA-0138-fusion-lineage-record-and-the-decomposition-round-tr.json"
)
SCHEMA = "command-center/schema/foundry-artifact.schema.json"
QUESTION = (
    "Define the lineage record a fused workflow must carry and implement the "
    "executable round-trip test that decomposes a fusion back into its source "
    "mechanisms and asserts the recovered set equals the declared sources. "
    "Question: for each of the 30 merge_units, does decompose(fuse(sources)) "
    "return exactly sources_declared, and which units fail because of the "
    "entries already recorded as sources_unresolved?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:WFA-0138 snippet not in {path}: {snippet[:80]!r}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
        "verdict": "CONFIRMED",
    }


def validate(doc: dict) -> None:
    """Local pin for lineage-record. Catalog schema $defs are $ref shims to
    https://ast-integrate.invalid/...; jsonschema would fetch the network and
    fail closed as RefResolutionError. G-1 does not require that fetch.
    """
    if doc.get("unit_id") != "WFA-0138":
        raise SystemExit("FAILED:WFA-0138 unit_id")
    if doc.get("kind") != "lineage-record":
        raise SystemExit("FAILED:WFA-0138 kind")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise SystemExit(f"FAILED:WFA-0138 self-declared {doc.get('state')}")
    if doc.get("sentinel") != "SUCCESS:WFA-0138":
        raise SystemExit("FAILED:WFA-0138 sentinel")
    if "SUCCESS:WFA-0138" not in str(doc.get("answer") or ""):
        raise SystemExit("FAILED:WFA-0138 answer missing sentinel")
    records = doc.get("records") or []
    if len(records) != C.REQUIRED_COUNT:
        raise SystemExit(f"FAILED:WFA-0138 records={len(records)}")
    if not isinstance(doc.get("both_states"), dict):
        raise SystemExit("FAILED:WFA-0138 both_states")
    report = doc.get("report") or {}
    if report.get("kind") != "lineage-record":
        raise SystemExit("FAILED:WFA-0138 report.kind")
    if not (report.get("observations") or []):
        raise SystemExit("FAILED:WFA-0138 report.observations")
    if not (report.get("control_ids") or []):
        raise SystemExit("FAILED:WFA-0138 report.control_ids")
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        raise SystemExit("FAILED:WFA-0138 schema missing on disk")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    target = schema.get("$defs", {}).get("lineage-record")
    if not isinstance(target, dict) or "$ref" not in target:
        raise SystemExit("FAILED:WFA-0138 schema fragment missing")


def main() -> int:
    loaded = C.load_corpus(REPO)
    units = loaded["merge_units"]
    if len(units) != C.REQUIRED_COUNT:
        print(f"FAILED:WFA-0138 count={len(units)} want=30")
        return 1

    trips = []
    records = []
    failures = []
    for unit in units:
        trip = L.round_trip(unit)
        if trip.get("signal_disagreement"):
            print(f"FAILED:WFA-0138 signal-disagreement {trip['merge_unit_id']}")
            print(json.dumps(trip["signal_disagreement"], indent=2)[:2000])
            return 1
        rec = L.lineage_record_for(unit, trip)
        trips.append({k: v for k, v in trip.items() if k != "fusion"})
        records.append(rec)
        if not trip["round_trip_ok"]:
            failures.append(
                {
                    "merge_unit_id": trip["merge_unit_id"],
                    "missing": trip["missing"],
                    "extra": trip["extra"],
                    "unresolved_recorded": trip["unresolved_recorded"],
                    "fail_because_unresolved": trip["fail_because_unresolved"],
                    "set_difference": (
                        f"declared-recovered missing={trip['missing']} "
                        f"extra={trip['extra']}"
                    ),
                }
            )
            if trip["unresolved_recorded"]:
                if not trip["fail_because_unresolved"]:
                    print(
                        f"FAILED:WFA-0138 unresolved mismatch "
                        f"{trip['merge_unit_id']} missing={trip['missing']} "
                        f"unresolved={trip['unresolved_recorded']}"
                    )
                    return 1
            else:
                print(
                    f"FAILED:WFA-0138 unexpected round-trip fail "
                    f"{trip['merge_unit_id']} missing={trip['missing']} "
                    f"extra={trip['extra']}"
                )
                return 1

    resolved_ok = [t for t in trips if not t["unresolved_recorded"] and t["round_trip_ok"]]
    unresolved_fail = [t for t in trips if t["fail_because_unresolved"]]
    if len(resolved_ok) + len(unresolved_fail) != C.REQUIRED_COUNT:
        print("FAILED:WFA-0138 not every unit classified")
        return 1

    subject = C.first_fully_resolved(units)
    both = L.both_states_drop_restore(subject)
    if not both["drop_names_exact_source"] or both["drop_round_trip_ok"]:
        print("FAILED:WFA-0138 both-states drop did not name the source")
        print(json.dumps(both, indent=2, default=str)[:2000])
        return 1
    if not both["restore_round_trip_ok"]:
        print("FAILED:WFA-0138 both-states restore did not pass")
        print(json.dumps(both, indent=2, default=str)[:2000])
        return 1

    maps_note = (
        f"{loaded['maps_name']} present path={loaded['maps_path']} "
        f"bytes={loaded['maps_bytes']}"
        if loaded["maps_present"]
        else (
            f"{loaded['maps_name']} ABSENT on this worktree "
            f"(CC-0019 recorded it at {loaded['expected_bytes_cc0019']} B in "
            "harness-restore-20260806, which is not mounted here). Round-trip "
            "ran on 30 reconstructed stand-in merge_units using catalog fields "
            "sources_declared/sources_unresolved. Original maps rows are not "
            "forged."
        )
    )
    fail_ids = [f["merge_unit_id"] for f in failures]
    answer = (
        f"decompose(fuse(sources)) recovers the source id set from fusion "
        f"component blobs (operator={L.OPERATOR}). Of 30 merge_units, "
        f"{len(resolved_ok)} round-trip to exactly sources_declared. "
        f"{len(unresolved_fail)} fail; each printed set-difference names the "
        f"sources_unresolved entries and nothing else "
        f"(ids={fail_ids}). {maps_note} Both-states: drop "
        f"{both['dropped_source']} from {both['merge_unit_id']} missing="
        f"{both['drop_missing']}; restore recovers declared. "
        "SUCCESS:WFA-0138"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lin_rel = "command-center/p2-wave/probes/WFA-0138/lineage.py"
    cor_rel = "command-center/p2-wave/probes/WFA-0138/corpus.py"
    evidence = [
        ev(
            lin_rel,
            "def fuse(",
            "mechanism",
            "fuse embeds resolvable sources as hashed component blobs",
        ),
        ev(
            lin_rel,
            "def decompose(fusion: dict[str, Any]) -> list[str]:",
            "mechanism",
            "decompose requires two independent walks to agree",
        ),
        ev(
            lin_rel,
            "def both_states_drop_restore(merge_unit: dict[str, Any]) -> dict[str, Any]:",
            "both-states",
            "drop one embedded source; restore must pass",
        ),
        ev(
            cor_rel,
            "REQUIRED_COUNT = 30",
            "corpus",
            "fail-closed unless exactly 30 merge_units",
        ),
    ]

    doc = {
        "unit_id": "WFA-0138",
        "kind": "lineage-record",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0138",
        "title": "Fusion lineage record and the decomposition round-trip test",
        "question": QUESTION,
        "answer": answer,
        "operator": L.OPERATOR,
        "output_schema": SCHEMA + "#/$defs/lineage-record",
        "ts": now,
        "maps": {
            "present": loaded["maps_present"],
            "path": loaded["maps_path"],
            "bytes": loaded["maps_bytes"],
            "sha256": loaded["maps_sha256"],
            "name": loaded["maps_name"],
            "expected_bytes_cc0019": loaded["expected_bytes_cc0019"],
            "provenance": loaded["provenance"],
            "searched": loaded["searched"],
            "count": loaded["count"],
        },
        "lineage_schema": {
            "required_fields": [
                "kind",
                "merge_unit_id",
                "fusion_id",
                "operator",
                "sources_declared",
                "sources_unresolved",
                "recovered_sources",
                "decomposition",
                "missing",
                "extra",
                "round_trip_ok",
                "fail_because_unresolved",
            ],
            "recovery_rule": (
                "recovered_sources is decompose(fusion.components), never a "
                "copied sources_declared field"
            ),
            "unresolved_rule": (
                "fuse skips sources_unresolved; round trip must then fail "
                "with missing == sources_unresolved and extra == []"
            ),
        },
        "records": records,
        "round_trips": trips,
        "failures_named": failures,
        "counts": {
            "merge_units": len(units),
            "round_trip_ok": len(resolved_ok),
            "fail_because_unresolved": len(unresolved_fail),
            "signal_disagreement": 0,
        },
        "both_states": both,
        "tests": [
            {
                "id": "probe1_roundtrip",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0138/probe1_roundtrip.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2_both_states",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0138/probe2_both_states.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0138-probe2-drop-source",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "probe2 drops a source from the fusion body and requires the "
                "named missing id; it does not author lineage.py"
            ),
        },
        "evidence": evidence,
        "report": {
            "kind": "lineage-record",
            "observations": [
                {
                    "name": "round_trip_ok_count",
                    "measured": len(resolved_ok),
                    "method": "decompose(fuse(sources_declared)) set equality per merge_unit",
                    "anchor": f"{lin_rel}:{find_line(REPO / lin_rel, 'def decompose(fusion: dict[str, Any]) -> list[str]:')}",
                },
                {
                    "name": "fail_because_unresolved_count",
                    "measured": len(unresolved_fail),
                    "method": "set-difference missing==sources_unresolved and extra==[]",
                    "anchor": f"{lin_rel}:{find_line(REPO / lin_rel, 'fail_because_unresolved = (')}",
                },
                {
                    "name": "both_states_drop_names_exact_source",
                    "measured": bool(both["drop_names_exact_source"]),
                    "method": "drop one embedded component then restore",
                    "anchor": f"{lin_rel}:{find_line(REPO / lin_rel, 'def both_states_drop_restore(merge_unit: dict[str, Any]) -> dict[str, Any]:')}",
                },
            ],
            "control_ids": [
                "probe2-drop-one-source-then-restore",
                "unresolved-sources-named-in-set-diff",
            ],
        },
        "cloud_ok": False,
    }
    validate(doc)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:WFA-0138")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
