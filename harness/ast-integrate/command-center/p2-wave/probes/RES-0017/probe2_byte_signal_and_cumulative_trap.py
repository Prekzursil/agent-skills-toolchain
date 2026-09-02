#!/usr/bin/env python3
"""Probe 2: independent byte signal (wc -c) + cumulative/file-size traps.

Mechanically different from probe 1 (tokenizer occupancy re-run): this probe
dumps the concatenated turn-0 payload and counts UTF-8 bytes with wc -c,
refuses file-size inference, refuses cumulative-as-occupancy, and checks
lazy/server markers are absent from the injection.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inject import (  # noqa: E402
    CLASS_ORDER,
    SESSION,
    class_payloads,
    render,
    utf8_len,
)
from measure import measure  # noqa: E402

ART = REPO / "command-center/research/RES-0017.json"
SCHEMA = HERE / "measurement-run.schema.json"
FORBIDDEN = (
    "RES0017-LAZY-SKILL-BODY-NOT-TURN0",
    "RES0017-MCP-SERVER-SOURCE-NOT-TURN0",
    "RES0017-RULE-DISABLED-NOT-TURN0",
    "RES0017-SKILL-SIDECAR-NOT-TURN0",
)
REQUIRED = (
    "RES0017-ALWAYS-ON-SKILL-BODY",
    "RES0017-RULE-TURN0",
    "RES0017-MCP-SEARCH-SCHEMA",
    "RES0017-TOOLS-SCHEMA",
)


def wc_c(path: Path) -> int:
    p = subprocess.run(
        ["wc", "-c", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(p.stdout.strip().split()[0])


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0017-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:RES-0017-probe2 schema", errs[0].message)
        return 1

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
        print("FAILED:RES-0017-probe2 schema accepts garbage")
        return 1

    payloads = class_payloads(SESSION)
    text = render(payloads)
    for marker in FORBIDDEN:
        if marker in text:
            print("FAILED:RES-0017-probe2 forbidden marker in occupancy", marker)
            return 1
    for marker in REQUIRED:
        if marker not in text:
            print("FAILED:RES-0017-probe2 required marker missing", marker)
            return 1

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write(text)
        dumped = Path(fh.name)
    try:
        wc_bytes = wc_c(dumped)
    finally:
        dumped.unlink(missing_ok=True)

    py_bytes = utf8_len(text)
    if wc_bytes != py_bytes:
        print("FAILED:RES-0017-probe2 wc -c != python utf-8", wc_bytes, py_bytes)
        return 1
    pub_bytes = int((doc.get("occupancy") or {}).get("turn0_injected_bytes") or -1)
    if wc_bytes != pub_bytes:
        print("FAILED:RES-0017-probe2 wc -c != published occupancy bytes", wc_bytes, pub_bytes)
        return 1

    live = measure()
    inf = live["file_size_inference"]
    if not inf["tree_gt_occupancy"]:
        print("FAILED:RES-0017-probe2 file-size inference not larger than occupancy")
        return 1
    if inf["bytes_div4_equals_tokenizer"]:
        print("FAILED:RES-0017-probe2 bytes/4 accidentally equals tokenizer")
        return 1
    occ = live["occupancy"]
    if occ["turn0_injected_tokens"] == occ["tokens_cumulative"]:
        print("FAILED:RES-0017-probe2 cumulative equals occupancy (trap silent)")
        return 1
    if occ["turn0_injected_tokens"] >= occ["tokens_cumulative"]:
        print("FAILED:RES-0017-probe2 extra turns did not grow cumulative")
        return 1

    published_inf = doc.get("file_size_inference") or {}
    if published_inf.get("tree_bytes_sum") != inf["tree_bytes_sum"]:
        print("FAILED:RES-0017-probe2 tree_bytes_sum drift")
        return 1

    byte_rows = {r["class"]: r["injected_bytes"] for r in live["per_class"]}
    dominates_bytes = max(CLASS_ORDER, key=lambda c: byte_rows[c])
    if dominates_bytes != doc.get("dominates_bytes"):
        print("FAILED:RES-0017-probe2 dominates_bytes", dominates_bytes)
        return 1
    if doc.get("accounting", {}).get("conflation_rejected") is not True:
        print("FAILED:RES-0017-probe2 conflation_rejected")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-byte-signal-and-cumulative-trap",
                "unit_id": "RES-0017",
                "wc_c": wc_bytes,
                "python_utf8": py_bytes,
                "tree_bytes_sum": inf["tree_bytes_sum"],
                "occupancy_tokens": occ["turn0_injected_tokens"],
                "tokens_cumulative": occ["tokens_cumulative"],
                "bytes_div4": inf["bytes_div4"],
                "dominates_bytes": dominates_bytes,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"wc_c={wc_bytes} tree={inf['tree_bytes_sum']} "
        f"occ_tokens={occ['turn0_injected_tokens']} "
        f"cumulative={occ['tokens_cumulative']} bytes_div4={inf['bytes_div4']}"
    )
    print("SUCCESS:RES-0017-probe2 byte signal and cumulative trap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
