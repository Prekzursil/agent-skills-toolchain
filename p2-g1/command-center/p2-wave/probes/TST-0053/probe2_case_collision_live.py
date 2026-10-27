#!/usr/bin/env python3
"""probe2 for TST-0053: case-collision keys ("Name" vs "name") live.

Per-consumer resolution over a document carrying BOTH keys:
  stdlib json.loads / node JSON.parse / jq  -> kept-both (case-sensitive)
  ci-downstream (load_ci)                   -> silent-merge (last wins, no error)
  case_keys.producer (emit)                 -> REFUSES case-colliding documents
  strict_json                               -> exact-dup rail (TST-0054), out of scope here
Both states of the producer: emits clean, refuses colliding (CaseCollisionError).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0053"
HERE = Path(__file__).resolve().parent
COLLIDING = '{"Name": "uppercase-N", "name": "lowercase-n", "id": "tst-0053-case-collision", "version": "1.0.0"}'
CLEAN = {"Name": "N", "id": "tst-0053-clean", "version": "1.0.0"}


def load(name: str, rel: Path):
    spec = importlib.util.spec_from_file_location(name, rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ck = load("t53_case_keys", HERE / "case_keys.py")
    checks: dict[str, object] = {}
    doc = json.loads(COLLIDING)
    checks["document_has_both_keys"] = {"Name", "name"} <= set(doc)

    # silent-merge path: the case-insensitive downstream reader loses "Name"
    merged = ck.load_ci(COLLIDING.encode("utf-8"))
    checks["ci_reader_silently_drops_one"] = "name" in merged and "Name" not in merged
    # and the producer's collision detector names exactly the colliding pair
    coll = ck.case_collisions(doc)
    checks["collisions_detected"] = any(set(v) == {"Name", "name"} for v in coll.values())

    # producer both-states
    clean_bytes = ck.emit(CLEAN)
    checks["producer_emits_clean"] = json.loads(clean_bytes.decode("utf-8")) == CLEAN
    refused = False
    try:
        ck.emit(doc)
    except ck.CaseCollisionError:
        refused = True
    except Exception:
        refused = False
    checks["producer_refuses_collision"] = refused

    # parser table (live): stdlib keeps both; pairs hook records both;
    # node keeps both; jq keeps both
    pairs: list[tuple[str, object]] = []
    json.loads(COLLIDING, object_pairs_hook=lambda ps: pairs.extend(ps) or dict(ps))
    checks["stdlib_keeps_both"] = {"Name", "name"} <= set(json.loads(COLLIDING))
    checks["pairs_hook_records_both"] = [k for k, _ in pairs if k in ("Name", "name")] == ["Name", "name"]
    node = subprocess.run(
        ["node", "-e", "const d=JSON.parse(process.argv[1]); console.log(JSON.stringify(Object.keys(d)))", COLLIDING],
        capture_output=True, text=True,
    )
    checks["node_keeps_both"] = node.returncode == 0 and "Name" in node.stdout and '"name"' in node.stdout
    jq = subprocess.run(["jq", "-c", "keys_unsorted", "-"], input=COLLIDING.encode(), capture_output=True)
    checks["jq_keeps_both"] = jq.returncode == 0 and b"Name" in jq.stdout and b'"name"' in jq.stdout

    # fixture file (per receipt fixture spec) written to the probe dir
    fixture = HERE / "fixtures" / "name-and-Name.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_bytes(COLLIDING.encode("utf-8"))
    checks["fixture_written"] = fixture.is_file() and fixture.stat().st_size > 0

    table = {
        "cpython-json.loads": "kept-both",
        "cpython-object_pairs_hook": "kept-both-recorded",
        "ci-downstream-of-cs-producer": "silent-merge-last-wins",
        "tst-0053-pipeline-reader": "error-via-producer-CaseCollisionError",
        "node-JSON.parse": "kept-both",
        "jq": "kept-both",
    }
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe2-case-collision-live", "pass": ok,
                      "resolution_table": table, "ci_merged_keys": sorted(merged),
                      "checks": checks}, default=str))
    if ok:
        print(f"SUCCESS:{UID}-probe2 live: case-distinct keys kept-both by stdlib/node/jq, silently merged by the ci reader, REFUSED by the producer (CaseCollisionError); clean emits fine")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
