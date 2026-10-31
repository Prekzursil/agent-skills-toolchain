"""Independent reviewer static battery - wave2 shard4.
Per unit: artifact exists/non-empty/parses; not self-blocked; manifest sha256 match
(CRLF->LF normalized); schema validation against catalog output_schema.
"""
import json, hashlib, os

ROOT = r"C:\Users\Prekzursil\p2-g1"
OUT  = os.path.join(ROOT, "_rev-w2-shard4", "static_results.json")

IDS = ["AUD-0043","AUD-0044","AUD-0047","AUD-0053","AUD-0055","AUD-0057",
       "AUD-0064","AUD-0066","AUD-0069","AUD-0071","AUD-0072","AUD-0075"]

with open(os.path.join(ROOT, "command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8") as f:
    cat = json.load(f)
wu = {u["id"]: u for u in cat["work_units"]}

def sha256_lf(path):
    data = open(path, "rb").read()
    data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()

def find_state(obj):
    states = {}
    for k in ("state", "delivery_state", "status"):
        if isinstance(obj, dict) and k in obj and isinstance(obj[k], str):
            states["top." + k] = obj[k]
    verdicts = []
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "verdict" and isinstance(v, str):
                    verdicts.append((path + "." + k, v))
                elif isinstance(v, (dict, list)):
                    walk(v, path + "." + k)
        elif isinstance(o, list):
            for n, v in enumerate(o):
                walk(v, path + "[" + str(n) + "]")
    walk(obj, "")
    return states, verdicts

results = {}
for uid in IDS:
    entry = wu[uid]
    op = entry["output_path"]
    abs_op = os.path.join(ROOT, op.replace("/", os.sep))
    r = {"unit": uid, "output_path": op}
    if not os.path.isfile(abs_op):
        r["exists"] = False
        results[uid] = r
        continue
    r["exists"] = True
    r["bytes"] = os.path.getsize(abs_op)
    r["non_empty"] = r["bytes"] > 0
    try:
        with open(abs_op, encoding="utf-8") as f:
            art = json.load(f)
        r["parses"] = True
    except Exception as e:
        r["parses"] = False
        r["parse_error"] = str(e)[:200]
        results[uid] = r
        continue
    states, verdicts = find_state(art)
    r["self_states"] = states
    r["verdicts"] = verdicts
    blocked_verdicts = [v for _, v in verdicts if v in ("BLOCKED", "FAILED")]
    r["blocked_states"] = {k: v for k, v in states.items() if v in ("BLOCKED", "FAILED")}
    r["self_blocked"] = bool(r["blocked_states"])
    r["blocked_target_verdicts"] = blocked_verdicts
    mp = os.path.join(ROOT, "command-center", "p2-wave", "probes", uid, "UNIT-ARTIFACT-MANIFEST.json")
    try:
        with open(mp, encoding="utf-8") as f:
            man = json.load(f)
        rows = man.get("artifacts", [])
        primary = [row for row in rows if isinstance(row, dict) and row.get("path") == op]
        if not primary:
            r["manifest_primary_row"] = False
            r["manifest_error"] = "no row for " + op
        else:
            claimed = primary[0].get("sha256")
            live = sha256_lf(abs_op)
            r["manifest_primary_row"] = True
            r["claimed_sha"] = claimed
            r["live_sha_lf"] = live
            r["sha_match"] = (claimed == live)
    except FileNotFoundError:
        r["manifest_primary_row"] = False
        r["manifest_error"] = "manifest missing"
    except Exception as e:
        r["manifest_error"] = str(e)[:200]
    try:
        with open(os.path.join(ROOT, "command-center", "receipts", uid + ".json"), encoding="utf-8") as f:
            rec = json.load(f)
        ra = [a for a in rec.get("artifacts", []) if a.get("path") == op]
        if ra:
            r["receipt_sha"] = ra[0].get("sha256")
            if "live_sha_lf" in r:
                r["receipt_sha_match"] = (r["receipt_sha"] == r["live_sha_lf"])
    except Exception as e:
        r["receipt_error"] = str(e)[:200]
    schema_ref = entry.get("output_schema")
    try:
        if isinstance(schema_ref, str):
            sp = os.path.join(ROOT, schema_ref.replace("/", os.sep))
            with open(sp, encoding="utf-8") as f:
                schema = json.load(f)
            base_uri = sp
        else:
            schema = schema_ref
            base_uri = None
        import jsonschema
        resolver = jsonschema.RefResolver(base_uri="file:///" + base_uri.replace("\\", "/"), referrer=schema) if base_uri else None
        errs = sorted(jsonschema.Draft202012Validator(schema, resolver=resolver).iter_errors(art), key=lambda e: list(e.absolute_path))
        r["schema_errors"] = [{"path": "/" + "/".join(map(str, e.absolute_path)), "msg": e.message[:300]} for e in errs[:50]]
        r["schema_valid"] = len(errs) == 0
    except Exception as e:
        r["schema_valid"] = False
        r["schema_exception"] = str(e)[:300]
    results[uid] = r

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=1)

for uid, r in results.items():
    gates = {
        "exists": r.get("exists"), "non_empty": r.get("non_empty"),
        "parses": r.get("parses"), "not_self_blocked": not r.get("self_blocked", True),
        "sha_match": r.get("sha_match"), "schema_valid": r.get("schema_valid"),
    }
    bad = [k for k, v in gates.items() if not v]
    print(uid, "OK" if not bad else "FAIL[" + ",".join(bad) + "]")
print("DONE:static-battery")
