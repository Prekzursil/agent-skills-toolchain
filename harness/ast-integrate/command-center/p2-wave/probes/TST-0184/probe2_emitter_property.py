#!/usr/bin/env python3
"""Probe 2: emitter property test over 200 generated artifacts.

Independent of probe 1's accept/reject fixtures: generate values, emit via
tools.plugin.strict_json.emit_strict, then scan every blob with locate_json5_isms
AND re-parse with parse_strict AND json.loads (three signals).
A planted trailing-comma mutant must fire the scanner (detector control).
"""
from __future__ import annotations

import json
import random
import string
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.plugin.strict_json import (  # noqa: E402
    StrictJSONError,
    emit_strict,
    locate_json5_isms,
    parse_strict,
)

N_ARTIFACTS = 200
SEED = 184


def rand_string(rng: random.Random) -> str:
    alphabet = string.ascii_letters + string.digits + " _-./"
    extra = ["// looks like comment", "/* no */", "quote \" inside", "üñîçødé"]
    if rng.random() < 0.25:
        return rng.choice(extra)
    n = rng.randint(0, 12)
    return "".join(rng.choice(alphabet) for _ in range(n))


def rand_value(rng: random.Random, depth: int = 0) -> Any:
    if depth >= 4:
        return rng.choice([None, True, False, rng.randint(-10**6, 10**6), rand_string(rng)])
    kinds = ("null", "bool", "int", "str", "list", "obj")
    kind = rng.choice(kinds)
    if kind == "null":
        return None
    if kind == "bool":
        return bool(rng.getrandbits(1))
    if kind == "int":
        return rng.randint(-10**9, 10**9)
    if kind == "str":
        return rand_string(rng)
    if kind == "list":
        return [rand_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    n = rng.randint(0, 4)
    keys = [f"k{i}_{rand_string(rng)[:6]}" for i in range(n)]
    # JSON object keys must be unique
    seen: dict[str, Any] = {}
    for k in keys:
        seen[k or "empty"] = rand_value(rng, depth + 1)
    return seen


def plant_trailing_comma(blob: str) -> str:
    idx = blob.rfind("}")
    if idx <= 0:
        return blob[:-1] + ",\n}\n"
    return blob[:idx] + ",\n" + blob[idx:]


def main() -> int:
    rng = random.Random(SEED)
    scanned = 0
    json5_hits = 0
    roundtrip_fail = 0
    samples: list[dict[str, Any]] = []
    for i in range(N_ARTIFACTS):
        value = {
            "name": f"generated-{i:03d}",
            "version": f"1.{i}.0",
            "payload": rand_value(rng),
        }
        blob = emit_strict(value)
        hits = locate_json5_isms(blob)
        if hits:
            json5_hits += 1
            if len(samples) < 3:
                samples.append({"i": i, "hits": hits, "blob_head": blob[:120]})
        try:
            parsed = parse_strict(blob)
            via_stdlib = json.loads(blob)
        except (StrictJSONError, json.JSONDecodeError) as exc:
            roundtrip_fail += 1
            print(f"FAILED:TST-0184-probe2 emit {i} not strict-clean: {exc}")
            return 1
        if parsed != value or via_stdlib != value:
            roundtrip_fail += 1
            print(f"FAILED:TST-0184-probe2 roundtrip mismatch at {i}")
            return 1
        scanned += 1

    mutant = plant_trailing_comma(emit_strict({"name": "mutant", "ok": True}))
    mutant_hits = locate_json5_isms(mutant)
    mutant_rejected = False
    mutant_pos = None
    try:
        parse_strict(mutant)
    except StrictJSONError as exc:
        mutant_rejected = True
        mutant_pos = f"{exc.line}:{exc.column}"
        if exc.kind != "trailing-comma":
            print(f"FAILED:TST-0184-probe2 mutant kind={exc.kind}")
            return 1

    payload = {
        "detector_control_mutant_rejected": mutant_rejected,
        "json5_hits_on_emitted": json5_hits,
        "mutant_position": mutant_pos,
        "mutant_scanner_kinds": [h["kind"] for h in mutant_hits],
        "n_artifacts": N_ARTIFACTS,
        "pass": (
            scanned == N_ARTIFACTS
            and json5_hits == 0
            and roundtrip_fail == 0
            and mutant_rejected
            and any(h["kind"] == "trailing-comma" for h in mutant_hits)
        ),
        "probe": "probe2-emitter-property-200",
        "roundtrip_fail": roundtrip_fail,
        "scanned": scanned,
        "seed": SEED,
        "unit_id": "TST-0184",
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0184-probe2 emitter property")
        print(json.dumps(samples, indent=1)[:2000])
        return 1
    print(
        f"scanned={scanned} json5_hits={json5_hits} mutant_rejected={mutant_rejected} "
        f"mutant_pos={mutant_pos}"
    )
    print(
        "SUCCESS:TST-0184-probe2 emitter property: 200 artifacts strict-clean; "
        "planted trailing-comma mutant fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
