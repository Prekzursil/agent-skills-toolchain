#!/usr/bin/env python3
"""Reviewer w1 shard1 static checks."""
import hashlib
import json
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center/p2-wave/probes"
UNITS = ["ADV-0132", "ARC-0001", "ARC-0013", "ARC-0019", "ARC-0020",
         "ARC-0047", "ARC-0048", "ARC-0054", "ARC-0055", "ARC-0068",
         "AUD-0003", "AUD-0010"]
BAD = {"BLOCKED", "FAILED", "FAILURE", "ERROR"}


def norm_sha(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def selfblock(doc):
    hits = []
    if isinstance(doc, dict):
        for k in ("state", "status", "verdict", "result"):
            v = doc.get(k)
            if isinstance(v, str) and v.strip().upper() in BAD:
                hits.append(k + "=" + str(v))
        for k in doc:
            hits.extend(selfblock(doc[k]))
    elif isinstance(doc, list):
        for x in doc:
            hits.extend(selfblock(x))
    return hits


def main():
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = dict((u["id"], u) for u in cat["work_units"])
    report = {}
    all_ok = True
    for uid in UNITS:
        res = {}
        u = units.get(uid)
        if u is None:
            report[uid] = {"catalog": "MISSING"}
            all_ok = False
            continue
        out = REPO / u["output_path"].replace("\\", "/")
        schema_path = REPO / u["output_schema"].replace("\\", "/")
        if not out.is_file():
            res["exists"] = False
            all_ok = False
        else:
            res["exists"] = True
            raw = out.read_bytes()
            res["bytes"] = len(raw)
            if len(raw) == 0:
                res["nonempty"] = False
                all_ok = False
            else:
                res["nonempty"] = True
                try:
                    doc = json.loads(raw.decode("utf-8"))
                    res["parses"] = True
                except Exception as e:
                    res["parses"] = str(e)[:120]
                    all_ok = False
                res["self_blocked"] = selfblock(doc) or "none"
                sent = ("SUCCESS:" + uid).encode("utf-8")
                res["sentinel"] = sent in raw
                sha, n = norm_sha(out)
                res["sha"] = sha
                mf = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
                if not mf.is_file():
                    res["manifest"] = "MISSING"
                    res["sha_match"] = False
                    all_ok = False
                else:
                    m = json.loads(mf.read_text(encoding="utf-8"))
                    rows = [a for a in m.get("artifacts", []) if a.get("role") == "primary"]
                    if not rows:
                        res["manifest"] = "NO-PRIMARY-ROW"
                        res["sha_match"] = False
                        all_ok = False
                    else:
                        res["sha_match"] = rows[0].get("sha256") == sha
                        res["bytes_match"] = rows[0].get("bytes") == n
                        res["manifest_sha"] = rows[0].get("sha256")
                        if not res["sha_match"] or not res["bytes_match"]:
                            all_ok = False
                if res.get("parses") is True:
                    try:
                        import jsonschema
                        schema = json.loads(schema_path.read_text(encoding="utf-8"))
                        cls = getattr(jsonschema, "Draft202012Validator", None)
                        if cls is None:
                            cls = jsonschema.validators.validator_for(schema)
                        cls.check_schema(schema)
                        errs = list(cls(schema).iter_errors(doc))
                        res["schema_ok"] = not errs
                        res["schema_msg"] = "ok" if not errs else str(errs[0].message)[:150]
                        if errs:
                            all_ok = False
                    except ImportError:
                        res["schema_ok"] = None
                        res["schema_msg"] = "jsonschema lib missing"
                    except Exception as e:
                        res["schema_ok"] = False
                        res["schema_msg"] = str(e)[:150]
                        all_ok = False
        report[uid] = res
    outp = REPO / "_review-shard1-w1/static_checks_out.json"
    outp.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    for uid in UNITS:
        r = report.get(uid, {})
        print(uid, "=>", json.dumps(r, sort_keys=True)[:600])
    print("SUCCESS:static green" if all_ok else "FAILED:static red")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
