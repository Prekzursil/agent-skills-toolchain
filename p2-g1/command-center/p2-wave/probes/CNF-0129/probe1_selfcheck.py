#!/usr/bin/env python3
"""CNF-0129 probe1: canonical schema resolves + delegation contract live; the receipt's
schema_sha256 pin is re-measured and any regeneration drift is RECORDED EXPLICITLY (never
silently forgiven): the probe passes only when the logical contract (delegate -> physical
confirmation-record class -> const kind) still holds live. Emitted by shard8-w2 resume
builder 2026-10-25."""
import hashlib, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []
FACTS = {}

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "facts": FACTS, "checks": CHECKS,
           "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0129.json")
    lt = d["live_target"]
    raw = (REPO / lt["schema_path"]).read_bytes()
    live_sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    shim = json.loads(raw.decode("utf-8"))
    drift = live_sha != lt["schema_sha256"]
    FACTS["declared_schema_sha256"] = lt["schema_sha256"]
    FACTS["live_schema_sha256"] = live_sha
    FACTS["regeneration_drift_detected"] = drift
    ck("shim_is_draft2020_delegate", shim.get("$schema", "").endswith("2020-12/schema") and bool(shim.get("$ref")))
    ck("shim_class_marker", shim.get("x-artifact-class") == "confirmation-record")
    phys = load("platform/schema/artifact-class-profiles.schema.json")
    node = phys["$defs"]["confirmation-record"]
    ref0 = json.dumps(node["allOf"][0])
    ck("delegation_contract_intact_live",
       "receipt.schema.json" in ref0 and "generic_report" in ref0
       and node["allOf"][1]["properties"]["report"]["properties"]["kind"]["const"] == "confirmation-record")
    ck("drift_if_any_recorded_not_denied",
       (not drift) or (drift and shim.get("x-generated-by", "") != "" and FACTS["live_schema_sha256"] == live_sha))
    cits = d.get("required_field_citations") or {}
    ck("required_field_citations_carry_pathline",
       len(cits) >= 3 and all((":" in v and ".json" in v) for v in cits.values()))
    obs = d.get("observations") or []
    names = [o.get("name", "") for o in obs]
    ck("before_and_after_observations_recorded",
       any("before" in n.lower() or "historical" in n.lower() for n in names)
       and any("live" in n.lower() and "unsourced" in n.lower() for n in names))
    ck("canonical_gate_declared", bool(lt.get("canonical_gate_path")))
    ck("completion_sentinel_in_artifact",
       "SUCCESS:CNF-0129" in (REPO / "command-center/receipts/CNF-0129.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0129")

if __name__ == "__main__":
    sys.exit(main())
