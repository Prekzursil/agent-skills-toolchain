"""LANE D1: independent check of F3/F4/F5 + the MD/JSON parity claim on all four paired artifacts.
Read-only. Prints JSON."""
import json
import re
import sys

T1 = "C:/Users/Prekzursil/.claude/harness-restore-20260806"


def read(p):
    with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return re.split(r"\r\n|\n", fh.read())


def jrecords(path, keys):
    j = json.load(open(path, encoding="utf-8"))
    for k in keys:
        if isinstance(j.get(k), list):
            return k, [r.get("id") for r in j[k] if isinstance(r, dict)], j
    return None, [], j


def f3():
    md = read(T1 + "/09-WORKFLOW-BLUEPRINT-LIBRARY.md")
    key, ids, j = jrecords(T1 + "/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
                           ["blueprints", "items", "records", "library"])
    audit = [m.group(1) for m in (re.match(r"^### `(BP-[A-Z]+-\d+)` v", ln) for ln in md) if m]
    # MY anchor: ALL h3 headings, partitioned -- residue must be 0
    all_h3 = [ln for ln in md if ln.startswith("### ")]
    bp_h3 = [ln for ln in all_h3 if re.match(r"^### `BP-", ln)]
    return {"json_key": key, "json_ids": len(ids), "json_unique": len(set(ids)),
            "audit_anchor": len(audit), "MY_all_h3": len(all_h3), "MY_bp_h3": len(bp_h3),
            "MY_residue_h3": [x[:90] for x in all_h3 if x not in bp_h3][:6],
            "set_equal": set(audit) == set(ids),
            "discovery_only": j.get("discovery_only")}


def f45():
    md = read(T1 + "/12-COUNCIL-PROTOCOLS-AND-PRESETS.md")
    j = json.load(open(T1 + "/12-COUNCIL-PROTOCOLS-AND-PRESETS.json", encoding="utf-8"))
    prot_key = next((k for k in ("protocols",) if isinstance(j.get(k), list)), None)
    pres_key = next((k for k in ("presets",) if isinstance(j.get(k), list)), None)
    pj = [r.get("id") for r in j[prot_key]] if prot_key else []
    cj = [r.get("id") for r in j[pres_key]] if pres_key else []
    prot = [m.group(1) for m in (re.match(r"^#### (P\d+) `", ln) for ln in md) if m]
    pres = [m.group(1) for m in (re.match(r"^#### (C-[A-Z]\d+) `", ln) for ln in md) if m]
    all_h4 = [ln for ln in md if ln.startswith("#### ")]
    residue = [x for x in all_h4
               if not re.match(r"^#### (P\d+|C-[A-Z]\d+) `", x)]
    return {
        "json_protocol_key": prot_key, "json_preset_key": pres_key,
        "json_protocols": len(pj), "json_protocols_unique": len(set(pj)),
        "json_presets": len(cj), "json_presets_unique": len(set(cj)),
        "md_protocols": len(prot), "md_presets": len(pres),
        "MY_all_h4": len(all_h4), "MY_residue_h4_count": len(residue),
        "MY_residue_h4_sample": [x[:90] for x in residue[:6]],
        "MY_sum_check": len(prot) + len(pres),
        "MY_disjoint": len(set(prot) & set(pres)) == 0,
        "set_equal_protocols": set(prot) == set(pj),
        "set_equal_presets": set(pres) == set(cj),
        "status": j.get("status"),
    }


def receipts():
    """Audit claim: zero of the 166 items carry an execution receipt."""
    out = {}
    for f, keys in (("09-WORKFLOW-BLUEPRINT-LIBRARY.json", ["blueprints", "items", "records", "library"]),
                    ("12-COUNCIL-PROTOCOLS-AND-PRESETS.json", ["protocols"])):
        j = json.load(open(T1 + "/" + f, encoding="utf-8"))
        txt = json.dumps(j).lower()
        out[f] = {
            "mentions_receipt": txt.count("receipt"),
            "mentions_executed_true": txt.count('"executed": true'),
            "discovery_only": j.get("discovery_only"),
            "status": j.get("status"),
        }
    return out


if __name__ == "__main__":
    json.dump({"F3": f3(), "F4_F5": f45(), "receipts": receipts()}, sys.stdout, indent=1)
