#!/usr/bin/env python3
"""CNF-0129 probe2: LIVE enforcement re-proof by mutation test on the receipt's own bytes.
The live receipt is validated against the canonical shim (file:// refs re-anchored into THIS
repo); then each CONFIRMED evidence item loses its verifier probe and the schema must REJECT
the mutated record - the unit's core claim (CONFIRMED requires the probe pair) re-proven today.
Emitted by shard8-w2 resume builder 2026-10-25."""
import copy, json, sys
from pathlib import Path
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[4]
CHECKS = []
FACTS = {}

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def retrieve(uri):
    p = str(uri)
    if p.startswith("file:///"):
        tail = p[len("file:///"):]
        marker = "ast-integrate/"
        if marker in tail:
            tail = tail.split(marker, 1)[1]
        local = REPO / tail
        if not local.is_file():
            local = Path(tail)
        doc = json.loads(local.read_text(encoding="utf-8"))
        return Resource.from_contents(doc, default_specification=DRAFT202012)
    raise FileNotFoundError(uri)

def main():
    d = json.loads((REPO / "command-center/receipts/CNF-0129.json").read_text(encoding="utf-8"))
    shim_doc = json.loads((REPO / d["live_target"]["schema_path"]).read_text(encoding="utf-8"))
    shim = Resource.from_contents(shim_doc, default_specification=DRAFT202012)
    reg = Registry(retrieve=retrieve).with_resource(shim_doc["$id"], shim)
    v = Draft202012Validator({"$ref": shim_doc["$id"]}, registry=reg)

    base = copy.deepcopy(d)
    base.setdefault("report", {})["kind"] = "confirmation-record"
    base_errs = list(v.iter_errors(base))
    FACTS["base_error_count"] = len(base_errs)
    FACTS["base_errors"] = [e.message[:140] for e in base_errs[:4]]
    ck("receipt_validates_as_confirmation_record", not base_errs)

    mutant = copy.deepcopy(base)
    stripped = 0
    for ev in mutant.get("evidence", []):
        if str(ev.get("verdict", "")).upper() == "CONFIRMED":
            probes = ev.get("probes", [])
            kept = [p for p in probes if str(p.get("role", "")).lower() != "verifier"]
            if len(kept) < len(probes):
                ev["probes"] = kept
                stripped += 1
    FACTS["verifier_probes_stripped"] = stripped
    mut_errs = list(v.iter_errors(mutant))
    FACTS["mutant_error_count"] = len(mut_errs)
    FACTS["mutant_errors"] = [e.message[:140] for e in mut_errs[:4]]
    blob = json.dumps([e.message for e in mut_errs]).upper()
    ck("mutant_rejected", stripped >= 1 and len(mut_errs) > len(base_errs))
    ck("rejection_names_the_pair_rule", ("VERIFIER" in blob) or ("PROBE" in blob) or ("source" in blob.lower()))
    return finish("probe2_livecheck", "CNF-0129")

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "facts": FACTS, "checks": CHECKS,
           "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

if __name__ == "__main__":
    sys.exit(main())
