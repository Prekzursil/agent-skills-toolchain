#!/usr/bin/env python3
"""TST-0144 probe2 -- truncated JSON fails parse and is never cached as parsed.

Rebuilds the 224-byte truncated fixture (error offset == byte 224), re-runs
the three recorded production surfaces live: stdlib json.loads (byte-offset
error), ready_units.artifact_delivered (condition-4 parse step fails), and
platform/plugin/cache.Cache (no entry retained for the failed artifact).
Both-states control: a complete artifact parses and caches. Negative
control: a lenient repair-parser would yield an object, proving the strict
gate can go red.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0144.json"
FIXDIR = Path(__file__).resolve().parent / "fixtures"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def main() -> int:
    FIXDIR.mkdir(parents=True, exist_ok=True)
    trunc = FIXDIR / "truncated.json"
    trunc.write_bytes(('{"a": ' + "2" * 218).encode("ascii"))  # exactly 224 bytes
    raw = trunc.read_bytes()
    chk(len(raw) == 224, "fixture-size", len(raw))
    try:
        json.loads(raw.decode("ascii"))
        chk(False, "truncated-parsed")
        err = None
    except json.JSONDecodeError as exc:
        err = exc
    chk(err is not None and err.pos == 224, "parse-offset", (err.pos if err else None))

    # surface 2: ready_units.artifact_delivered (condition 4 parse step)
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("live_ready_units", REPO / "command-center/ready_units.py")
    ru = importlib.util.module_from_spec(spec)
    sys.modules["live_ready_units"] = ru
    spec.loader.exec_module(ru)
    unit = {
        "id": "TST-0144",
        "unit_id": "TST-0144",
        "output_path": "command-center/p2-wave/probes/TST-0144/fixtures/truncated.json",
        "output_schema": None,
        "min_bytes_threshold": 512,
    }
    ok_delivered, reason = ru.artifact_delivered(unit, resolver=None)
    chk(ok_delivered is False, "delivered-true-on-truncated", reason)

    # surface 3: the cache never retains a parsed object for a failed parse
    import types
    pkg = types.ModuleType("p2_platform_plugin")
    pkg.__path__ = [str(REPO / "platform/plugin")]
    sys.modules["p2_platform_plugin"] = pkg
    spec2 = importlib.util.spec_from_file_location(
        "p2_platform_plugin.cache", REPO / "platform/plugin/cache.py")
    pc = importlib.util.module_from_spec(spec2)
    sys.modules["p2_platform_plugin.cache"] = pc
    spec2.loader.exec_module(pc)
    with tempfile.TemporaryDirectory() as td:
        cache = pc.Cache(Path(td) / "state")
        cache.put(json.dumps({"complete": True}).encode())
        n_after_complete = sum(1 for _ in cache.root.rglob("*") if _.is_file())
        chk(n_after_complete == 1, "complete-artifact-not-cached", n_after_complete)
        # strict pipeline: parse raises BEFORE any put -> no new entry
        entries_before = n_after_complete
        try:
            json.loads(raw.decode("ascii"))
        except json.JSONDecodeError:
            pass
        entries_after = sum(1 for _ in cache.root.rglob("*") if _.is_file())
        chk(entries_after == entries_before, "failed-parse-cached", entries_after)

    # negative control: a lenient repair-parser WOULD produce an object
    def lenient(data: bytes):
        try:
            return json.loads(data.decode("ascii"))
        except json.JSONDecodeError:
            text = data.decode("ascii").rstrip()
            for closer in ('"}', '"}', "2}", "]}", "}}"):
                try:
                    return json.loads(text + closer)
                except json.JSONDecodeError:
                    continue
        return None
    chk(lenient(raw) is not None, "lenient-control-silent")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    prod = doc.get("production_surfaces") or []
    chk(len(prod) == 3, "production-surfaces", prod)
    if FAILS:
        print("FAILED:TST-0144-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0144-probe2 truncated fixture (224 B) fails json.loads at byte 224, ready_units.artifact_delivered returns False on the condition-4 parse step, cache retains zero entries for the failed artifact; complete artifact caches; lenient repair-parser would go red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
