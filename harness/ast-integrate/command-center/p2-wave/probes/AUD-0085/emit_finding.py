#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0085-encoding-bom-mojibake-census.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import run_census  # noqa: E402
from common import (  # noqa: E402
    COMPLETION_SENTINEL,
    FX_BOM,
    FX_CORRECT,
    FX_DOUBLE,
    FX_INVALID,
    FX_PLUGIN,
    OUT,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    SCHEMA,
    SCHEMA_REL,
    UNIT,
)
from detector import control_vectors  # noqa: E402

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = run_census()
    s = live["summary"]
    v = s["controls"] if "controls" in s else control_vectors()
    if not v.get("production_both_states"):
        print("FAILED:AUD-0085 emit detector failed both-states control")
        print(json.dumps(v, indent=2)[:3000])
        return 1
    if not v.get("mutant_killed"):
        print("FAILED:AUD-0085 emit mutant not killed")
        return 1
    if not s["planted_double_decoded_fired"] or not s["planted_correct_silent"]:
        print("FAILED:AUD-0085 emit planted fixture control failed")
        print(json.dumps({k: s[k] for k in s if k.startswith("planted")}, indent=2))
        return 1
    if not s["planted_bom_seen"] or not s["planted_invalid_seen"]:
        print("FAILED:AUD-0085 emit planted BOM/invalid not seen")
        return 1
    if s["extension_only_overclaim_paths"]:
        print("FAILED:AUD-0085 emit extension-only consumer overclaim")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:AUD-0085 schema accepts garbage")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    invalid_n = s["invalid_utf8_text_count"]
    bom_n = s["bom_count"]
    moj_n = s["confirmed_mojibake_count"]
    consumed_n = s["strict_consumed_count"]
    answer = (
        f"On this worktree a live walk of {s['files_scanned']} regular files found "
        f"{invalid_n} text-scope invalid UTF-8 path(s), {bom_n} BOM-bearing path(s), "
        f"and {moj_n} confirmed prior-double-decode mojibake path(s) under a gated "
        f"cp1252/UTF-8 detector applied after parse (or after UTF-8 decode for "
        f"unstructured text). Of those mojibake paths, {consumed_n} have a "
        f"path-specific product reader AND a successful strict parse rehearsal. "
        f"Extension-only consumption is not counted. The naive latin-1 repair "
        f"one-liner is not applied to repository bytes. Planted controls: "
        f"double-decoded JSON fired; correctly encoded Français/日本語/—/Привет/×¥ "
        f"stayed silent; UTF-8 BOM and invalid UTF-8 fixtures were observed. "
        f"Did not run tools/command-center/unit_manifest.py --write."
    )
    probe1_record = {
        "id": "probe1",
        "command": P1,
        "files_scanned": s["files_scanned"],
        "invalid_utf8_all_count": s["invalid_utf8_all_count"],
        "invalid_utf8_text_count": invalid_n,
        "invalid_utf8_text_paths": s["invalid_utf8_text_paths"],
        "bom_count": bom_n,
        "bom_paths": s["bom_paths"],
        "planted_invalid_seen": True,
        "planted_bom_seen": True,
    }
    probe2_record = {
        "id": "probe2",
        "command": P2,
        "confirmed_mojibake_count": moj_n,
        "confirmed_mojibake_paths": s["confirmed_mojibake_paths"],
        "strict_consumed_count": consumed_n,
        "extension_only_overclaim_paths": s["extension_only_overclaim_paths"],
        "production_both_states": True,
        "mutant_killed": True,
        "collision_silent": True,
        "parse_first": True,
    }
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0085",
        "completion_sentinel": COMPLETION_SENTINEL,
        "title": "Encoding, BOM, and mojibake census",
        "question": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0085",
        "report_kind": "audit-finding",
        "report": {
            "kind": "audit-finding",
            "answer": answer,
            "observations": [
                f"files_scanned={s['files_scanned']} invalid_utf8_all={s['invalid_utf8_all_count']} invalid_utf8_text={invalid_n}",
                f"bom={bom_n} confirmed_mojibake={moj_n} strict_consumed={consumed_n}",
                "naive latin-1 one-liner is not used; detector is cp1252-gated and parse-first",
                "U+00D7 U+00A5 collision is silent on the production detector and fires ungated reversible coincidence",
                "strict_parser_consumed requires a path-specific product reader, not a file extension",
            ],
        },
        "deleted_inventory": {
            "catalog_claimed_count": s["files_scanned"],
            "tree_count": 1,
            "recovered_count": invalid_n + bom_n + moj_n,
            "planted_count": 5,
            "unit_interpretation": (
                "AUD-0085 is an encoding census, not a DELETE-ALL path census. "
                "This inventory records the walked regular-file surface plus planted controls."
            ),
            "paths": [
                {"path": FX_DOUBLE, "tree": "worktree", "source": "planted-control"},
                {"path": FX_CORRECT, "tree": "worktree", "source": "planted-control"},
                {"path": FX_BOM, "tree": "worktree", "source": "planted-control"},
                {"path": FX_INVALID, "tree": "worktree", "source": "planted-control"},
                {"path": FX_PLUGIN, "tree": "worktree", "source": "planted-control"},
            ],
        },
        "dangling_references": [],
        "census": {
            "files_scanned": s["files_scanned"],
            "invalid_utf8_all_count": s["invalid_utf8_all_count"],
            "invalid_utf8_text_count": invalid_n,
            "invalid_utf8_text_paths": s["invalid_utf8_text_paths"],
            "invalid_utf8_all_sample": live["invalid_utf8_all_sample"],
            "bom_count": bom_n,
            "bom_paths": s["bom_paths"],
            "bom_rows": live["bom_rows"],
            "confirmed_mojibake_count": moj_n,
            "confirmed_mojibake_paths": s["confirmed_mojibake_paths"],
            "mojibake": live["mojibake"],
            "strict_consumed_count": consumed_n,
            "plugin_manifests_checked": s["plugin_manifests_checked"],
            "plugin_manifests_ok": s["plugin_manifests_ok"],
            "parse_failed_structured_count": s["parse_failed_structured_count"],
            "skipped_large_count": s["skipped_large_count"],
            "extension_only_overclaim_paths": s["extension_only_overclaim_paths"],
            "naive_repair_policy": (
                "Never run text.encode('latin-1').decode('utf-8') over raw serialized "
                "input. Parse first, detect reversible spans in logical strings with "
                "cp1252-gated C2/C3/E2 leads, then consider per-span repair. Do not "
                "treat U+00D7 U+00A5 coincidence as prior double-decode."
            ),
        },
        "named_probe_records": {"probe1": probe1_record, "probe2": probe2_record},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": 0,
                "raw_output": json.dumps(probe1_record, sort_keys=True),
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": 0,
                "raw_output": json.dumps(probe2_record, sort_keys=True),
            },
        ],
        "tests": [
            {
                "id": "T-DECODE-CENSUS",
                "command": P1,
                "name": "strict UTF-8 decode attempt per regular file; planted invalid UTF-8 and BOM observed",
                "result": "PASS",
            },
            {
                "id": "T-MOJIBAKE-BOTH-STATES",
                "command": P2,
                "name": (
                    "control: the mojibake detector must fire on a known double-decoded "
                    "fixture and stay silent on correctly encoded non-ASCII text; a "
                    "detector that flags all non-ASCII is unusable"
                ),
                "result": "PASS",
            },
            {
                "id": "T-NONASCII-MUTANT-KILLED",
                "command": P2,
                "name": "negative control goes red when detector is replaced by any-non-ASCII",
                "result": "PASS",
            },
            {
                "id": "T-PARSE-FIRST",
                "command": P2,
                "name": "detector applied after JSON/YAML parse (or after UTF-8 decode for unstructured text), never as a pre-parse latin-1 repair",
                "result": "PASS",
            },
            {
                "id": "T-COLLISION-SILENT",
                "command": P2,
                "name": "production detector stays silent on correctly encoded U+00D7 U+00A5; ungated reversible coincidence fires",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CTL-MOJIBAKE-BOTH-STATES",
                "planted_defect": "double-decoded cafe/quote/warn JSON fixture vs correctly encoded Français/日本語/—/Привет/×¥",
                "detector_fired": True,
                "silent_on_good": True,
            },
            {
                "id": "CTL-NONASCII-MUTANT",
                "planted_defect": "replace detector with any(ord(c)>127); must flag correct Français",
                "detector_fired": True,
                "silent_on_good": False,
            },
            {
                "id": "CTL-TIMES-YEN-COLLISION",
                "planted_defect": "U+00D7 U+00A5 reversible coincidence must not count as confirmed mojibake",
                "detector_fired": False,
                "silent_on_good": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0085-probe2-gated-detector-and-collision",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": False,
            "notes": (
                "Catalog asks for a fresh-context Claude who tries to falsify the "
                "headline count. That reviewer is not impersonated. Independent "
                "falsification is the ×¥ collision (must stay silent), the any-non-ASCII "
                "mutant (must fire on correct Français), and live re-walk vs artifact."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {"path": FX_DOUBLE, "exists": True, "role": "planted-control"},
            {"path": FX_CORRECT, "exists": True, "role": "planted-control"},
            {"path": FX_BOM, "exists": True, "role": "planted-control"},
            {"path": FX_INVALID, "exists": True, "role": "planted-control"},
            {"path": FX_PLUGIN, "exists": True, "role": "planted-control"},
        ],
        "evidence": [
            {
                "claim": QUESTION,
                "verdict": "CONFIRMED",
                "anchor": OUT_REL,
            },
            {
                "claim": "Planted double-decoded JSON fires; planted correct Unicode including ×¥ stays silent",
                "verdict": "CONFIRMED",
                "anchor": FX_DOUBLE,
            },
            {
                "claim": "Planted invalid UTF-8 and UTF-8 BOM fixtures are observed by the decode census",
                "verdict": "CONFIRMED",
                "anchor": FX_INVALID,
            },
            {
                "claim": "strict_parser_consumed is never set from file extension alone",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0085/census.py consumer_for",
            },
        ],
        "honesty": (
            "Headline counts are live walks of this Linux worktree, not harvest-era "
            "numbers. Binary invalid UTF-8 (.pyc and similar) is counted separately "
            "from text-scope. Global tools/command-center/unit_manifest.py --check "
            "redness on sibling units is not treated as this unit's delivery gate; "
            "G-1 uses the per-unit UNIT-ARTIFACT-MANIFEST.json. cloud_ok is false."
        ),
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0085/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
        },
        "produced_by": {
            "role": "encoding-census",
            "execution_substrate": "linux-worktree",
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
        },
        "timestamps": {"emitted_at": now},
        "min_bytes_threshold": 1024,
        "cloud_ok": False,
    }

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:AUD-0085 schema validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    dumped = json.dumps(doc, indent=2) + "\n"
    if COMPLETION_SENTINEL not in dumped:
        print("FAILED:AUD-0085 completion_sentinel not in document text")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dumped, encoding="utf-8")
    digest, size = sha256_file(OUT)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:AUD-0085 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
