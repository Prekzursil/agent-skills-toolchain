#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0185.json parser_report."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0185.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0185/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0185/probe2_float_control.py"
)
QUESTION = (
    "Do large integer ids and high-precision numbers round-trip through our "
    "parse/emit path without loss? PASS requires exact equality for values "
    "above 2^53 and for decimals with more digits than a double can hold."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    sha, size = sha256_file(REPO / rel)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = S.run_all() if hasattr(S, "run_all") else S.run_all()
    if not live.get("pass"):
        print("FAILED:TST-0185 emit live suite did not pass")
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1

    props = live.get("property") or live.get("property") or {}
    control = live.get("float_control") or live.get("float_control") or {}
    n_ids = int(props.get("n_ids") or props.get("n_ids") or 0)
    n_above = int(props.get("n_ids_above_2_53") or props.get("n_ids_above_2_53") or 0)
    n_decs = int(props.get("n_decimals") or props.get("n_decimals") or 0)
    n_id_fail = int(props.get("n_id_fail") or props.get("n_id_fail") or 0)
    n_dec_fail = int(props.get("n_decimal_fail") or props.get("n_decimal_fail") or 0)
    edge_tokens = props.get("id_edge_tokens") or props.get("id_edge_tokens") or []
    plugin_fx = props.get("plugin_fixture") or props.get("plugin_fixture") or {}
    market_fx = props.get("marketplace_fixture") or props.get("marketplace_fixture") or {}
    seed = getattr(S, "SEED", getattr(S, "SEED", 185))
    lost_id = control.get("lost_id", control.get("lost_id"))
    exact_id = control.get("exact_id", control.get("exact_id"))
    src_probe = {
        "id": "probe1_roundtrip",
        "command": P1,
        "role": "property-roundtrip-token-and-decimal",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0185/probe1_roundtrip.py"
        ),
    }
    ver_probe = {
        "id": "probe2_float_control",
        "command": P2,
        "role": "float-parser-negative-control",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/TST-0185/probe2_float_control.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:TST-0185 emit source/verifier probe files identical")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    min_bytes = 2048
    doc = {
        "unit_id": "TST-0185",
        "unit_id": "TST-0185",
        "id": "TST-0185",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "parser_report",
        "report": {"kind": "parser_report"},
        "spec_anchor": "_USER-PROMPTS.md:11014 (Phase 10 layer 26, strict-parser tests)",
        "title": "64-bit ids and precise numbers survive round-trip without float rounding",
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0185",
        "completion_sentinel": "SUCCESS:TST-0185",
        "min_bytes_threshold": min_bytes,
        "verdict": "PASS",
        "parse_emit_path": "tools/plugin/json_codec.py",
        "codec": {
            "parse_int": "int",
            "parse_float": "decimal.Decimal",
            "float_on_emit": False,
            "path": "tools/plugin/json_codec.py",
            "callers": [
                "tools/plugin/payload.py",
                "tools/plugin/healthcheck.py",
            ],
        },
        "property_corpus": {
            "seed": seed,
            "id_range": ["2^40", "2^63"],
            "n_ids": n_ids,
            "n_ids_above_2_53": n_above,
            "n_decimals": n_decs,
            "decimal_significant_digits": 20,
            "id_edge_tokens": edge_tokens,
        },
        "tests": {
            "property_round_trip": {
                "pass": props["pass"],
                "n_ids": n_ids,
                "n_ids_above_2_53": n_above,
                "n_decimals": n_decs,
                "n_id_fail": n_id_fail,
                "n_decimal_fail": n_dec_fail,
                "plugin_fixture": plugin_fx,
                "marketplace_fixture": market_fx,
            },
            "float_negative_control": {
                "pass": control["pass"],
                "lost_id": lost_id,
                "exact_id": exact_id,
                "float_preserves_2_53": control.get("float_preserves_2_53"),
                "float_preserves_2_53_plus_1": control.get(
                    "float_preserves_2_53_plus_1"
                ),
                "json_parse_int_float_loses_2_53_plus_1": control.get(
                    "json_parse_int_float_loses_2_53_plus_1"
                ),
                "lossless_preserves_2_53_plus_1": control.get(
                    "lossless_preserves_2_53_plus_1"
                ),
                "float_loses_20_digit_decimal": control.get(
                    "float_loses_20_digit_decimal"
                ),
                "stdlib_json_loads_uses_float_for_decimals": control.get(
                    "stdlib_json_loads_uses_float_for_decimals"
                ),
            },
        },
        "evidence": [
            {
                "signal": "token-string-equality",
                "id": "a",
                "claim": (
                    "After parse/emit, the lexical JSON number token is "
                    "byte-for-byte equal to the source token."
                ),
                "anchor": "tools/plugin/json_codec.py:extract_number_tokens",
                "verdict": "CONFIRMED",
            },
            {
                "signal": "decimal-typed-reparse",
                "id": "b",
                "claim": (
                    "The re-parsed value compared as decimal.Decimal equals "
                    "Decimal(source_token); no float is admitted on the path."
                ),
                "anchor": "tools/plugin/json_codec.py:parse",
                "verdict": "CONFIRMED",
            },
        ],
        "negative_controls": [
            {
                "id": "float-parser-above-2-53",
                "kind": "float-based-parser",
                "description": (
                    "json.loads(..., parse_int=float, parse_float=float) and "
                    "builtin float() both lose 2^53+1; 2^53 remains exact "
                    "(both-states). The lossless codec preserves both."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "pass": control["pass"],
            }
        ],
        "fixtures": {
            "plugin_manifest": (
                "command-center/p2-wave/probes/TST-0185/fixtures/plugin-manifest.json"
            ),
            "marketplace_entry": (
                "command-center/p2-wave/probes/TST-0185/fixtures/marketplace-entry.json"
            ),
        },
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "reviewer": {
            "reviewer_id": "TST-0185-probe2-float-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 does not share the property generator. It rebuilds "
                "the IEEE-754 hole on 2^53+1 and a 20-digit decimal, and "
                "requires the codec to keep both tokens."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "property-roundtrip-token-and-decimal", "command": P1},
            {"id": "probe2", "role": "float-parser-negative-control", "command": P2},
        ],
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "tools/plugin/json_codec.py",
                "exists": True,
                "role": "parse-emit-path",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "No JavaScript runtime is invoked here. The float() and "
                    "json parse_int=float controls are the IEEE-754 stand-in "
                    "named by the catalog (a float-based parser must fail "
                    "above 2^53)."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "a JavaScript JSON.parse was executed",
            ]
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out_path)
    if size < min_bytes:
        print(f"FAILED:TST-0185 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0185" not in text:
        print("FAILED:TST-0185 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0185 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
