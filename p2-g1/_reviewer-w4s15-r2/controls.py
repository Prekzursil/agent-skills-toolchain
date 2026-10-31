#!/usr/bin/env python3
"""Both-states control for the D instruments (single-signal rule 3b).

GREEN state: find sibling artifacts declaring the same schema classes that
validate 0-error through BOTH D1 (repo resolver) and D2 (reviewer ref-walker).
A red-only instrument proves nothing; a green case proves the instrument CAN pass.

MUTATION state: take RES-0128 (D-red: missing required min_bytes_threshold),
add that one key, re-validate -> must go 0-error on both instruments. Proves the
red is CONTENT, not instrument.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(ROOT / "platform" / "lib"))
import schema_resolver as SR  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight import d2_validate  # noqa: E402

cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
entries = {u["id"]: u for u in cat["work_units"]}


def both(artifact, declared):
    e1 = SR.validate_artifact(artifact, declared)
    e2 = d2_validate(artifact, declared)
    return e1, e2


def main():
    # --- GREEN-state hunt: same declared schema files as my shard's classes ---
    classes = ["research-claim-record.schema.json", "measurement-run.schema.json", "research-registry.schema.json", "gem-candidate.schema.json"]
    found = []
    for u in cat["work_units"]:
        sch = u.get("output_schema", "")
        if any(c in sch for c in classes):
            p = ROOT / u["output_path"]
            if not p.is_file():
                continue
            try:
                doc = json.loads(p.read_bytes().decode("utf-8"))
            except Exception:
                continue
            try:
                e1, e2 = both(doc, u["output_schema"])
            except Exception:
                continue
            if not e1 and not e2:
                found.append((u["id"], u["output_schema"]))
                if len(found) >= 3:
                    break
    print("GREEN-state controls (0-error both instruments):")
    for uid, sch in found:
        print("  ", uid, sch)
    if not found:
        print("  NONE FOUND in same classes - widening to whole catalog")
        for u in cat["work_units"]:
            p = ROOT / u.get("output_path", "")
            if not p.is_file() or not str(p).endswith(".json"):
                continue
            try:
                doc = json.loads(p.read_bytes().decode("utf-8"))
                e1, e2 = both(doc, u["output_schema"])
            except Exception:
                continue
            if not e1 and not e2:
                print("  ", u["id"], u["output_schema"])
                found.append((u["id"], u["output_schema"]))
                if len(found) >= 3:
                    break

    # --- MUTATION control on RES-0128 ---
    e128 = entries["RES-0128"]
    p = ROOT / e128["output_path"]
    doc = json.loads(p.read_bytes().decode("utf-8"))
    before = both(doc, e128["output_schema"])
    mutated = copy.deepcopy(doc)
    mutated["min_bytes_threshold"] = {"applied": "artifact must exceed this byte floor", "bytes": 1024}
    after = both(mutated, e128["output_schema"])
    print("MUTATION RES-0128 (add required min_bytes_threshold):")
    print("  before D1/D2:", len(before[0]), len(before[1]))
    print("  after  D1/D2:", len(after[0]), len(after[1]))
    print("  after-first:", [e[:150] for e in after[0][:2]])
    # inverse mutation on a green control (if found): inject junk key -> must go red
    if found:
        uid, sch = found[0]
        e = entries[uid]
        doc2 = json.loads((ROOT / e["output_path"]).read_bytes().decode("utf-8"))
        bad = copy.deepcopy(doc2)
        bad["zz_reviewer_injected_forbidden_key"] = True
        red = both(bad, e["output_schema"])
        print(f"INVERSE-MUTATION {uid} (inject forbidden key): D1/D2 red = {len(red[0])}/{len(red[1])}")


if __name__ == "__main__":
    main()
