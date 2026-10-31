"""Independent reviewer live re-verification for wave-2 shard 5 (12 units).
Read-only. Checks: artifact exists/nonempty/parses/not-self-blocked, manifest
sha256 (CRLF normalized), output_schema, live probes, receipt admission."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
AST_DIR = Path.home() / "source" / "ast-integrate"
AST_BASE = "file:///" + AST_DIR.as_posix() + "/"
CRLF = bytes([13, 10])
LF = bytes([10])
UNITS = ["CNF-0173", "CNF-0177", "CNF-0178", "CNF-0180", "CNF-0188", "CNL-0076",
         "IMP-0003", "IMP-0013", "IMP-0014", "IMP-0018", "IMP-0020", "IMP-0022"]

catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wus = {u["id"]: u for u in catalog.get("work_units", []) if isinstance(u, dict)}


def norm_sha(raw):
    return hashlib.sha256(raw.replace(CRLF, LF)).hexdigest()


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def collect_refs(node, out):
    if isinstance(node, dict):
        r = node.get("$ref")
        if isinstance(r, str) and r.startswith(AST_BASE):
            out.add(r)
        for v in node.values():
            collect_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_refs(v, out)


schema_cache = {}


def get_schema(rel):
    if rel not in schema_cache:
        schema_cache[rel] = load_json(REPO / rel)
    return schema_cache[rel]


def build_registry():
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
    resources = {}
    seen = set()
    queue = [get_schema(wus[x]["output_schema"].replace("\\", "/")) for x in UNITS]
    while queue:
        doc = queue.pop(0)
        k = id(doc)
        if k in seen:
            continue
        seen.add(k)
        found = set()
        collect_refs(doc, found)
        for uri in sorted(found):
            base = uri.split("#", 1)[0]
            if base in resources:
                continue
            own = Path(base[8:])
            trel = base[len(AST_BASE):]
            tp = own if own.exists() else (AST_DIR / trel)
            if not tp.exists():
                print("WARN registry target missing:", base)
                continue
            tdoc = load_json(tp)
            frag = uri.split("#", 1)[1] if "#" in uri else ""
            if frag.startswith("/$defs/"):
                if frag[7:] not in (tdoc.get("$defs") or {}):
                    print("WARN fragment absent:", base, frag)
                    continue
            resources[base] = Resource.from_contents(tdoc, default_specification=DRAFT202012)
            queue.append(tdoc)
    return Registry(resources=resources)


REGISTRY = build_registry()


def schema_check(uid, doc):
    from jsonschema import Draft202012Validator
    v = Draft202012Validator(get_schema(wus[uid]["output_schema"].replace("\\", "/")), registry=REGISTRY)
    return sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))


results = {}
for uid in UNITS:
    r = {"checks": {}, "probe_rows": [], "warns": []}
    out_rel = wus[uid]["output_path"].replace("\\", "/")
    art_p = REPO / out_rel
    doc = None
    if not art_p.exists():
        r["checks"]["artifact"] = "FAIL missing " + out_rel
    else:
        raw = art_p.read_bytes()
        if len(raw) == 0:
            r["checks"]["artifact"] = "FAIL 0 bytes"
        else:
            try:
                doc = json.loads(raw.decode("utf-8-sig"))
                r["checks"]["parse"] = "OK"
            except Exception as exc:
                r["checks"]["parse"] = "FAIL " + type(exc).__name__ + ": " + str(exc)[:110]
            st = doc.get("state") if isinstance(doc, dict) else None
            r["state"] = st
            if st in ("BLOCKED", "FAILED"):
                r["checks"]["not_self_blocked"] = "FAIL state=" + str(st)
            else:
                r["checks"]["not_self_blocked"] = "OK state=" + str(st)
    # manifest
    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not mp.exists():
        r["checks"]["manifest"] = "FAIL missing"
    else:
        man = load_json(mp)
        arts = man.get("artifacts") or []
        prim = [a for a in arts if a.get("role") == "primary"]
        if len(prim) != 1:
            r["checks"]["manifest"] = "FAIL " + str(len(prim)) + " primary rows"
        elif prim[0].get("path", "").replace("\\", "/") != out_rel:
            r["checks"]["manifest"] = "FAIL primary path " + str(prim[0].get("path")) + " != " + out_rel
        else:
            live = norm_sha(art_p.read_bytes())
            if live != prim[0].get("sha256"):
                r["checks"]["manifest"] = ("FAIL sha manifest=" + str(prim[0].get("sha256"))[:16]
                                           + " live=" + live[:16])
            else:
                r["checks"]["manifest"] = "OK " + live[:12]
                nraw = len(art_p.read_bytes())
                nnorm = len(art_p.read_bytes().replace(CRLF, LF))
                r["bytes_note"] = "row=" + str(prim[0].get("bytes")) + " live_raw=" + str(nraw) + " live_norm=" + str(nnorm)
        for a in arts:
            if a.get("role") == "primary":
                continue
            ap = REPO / str(a.get("path", "")).replace("\\", "/")
            if not ap.exists():
                r["warns"].append("supporting-missing:" + str(a.get("path")))
            elif norm_sha(ap.read_bytes()) != a.get("sha256"):
                r["warns"].append("supporting-sha-stale:" + str(a.get("path")))
    # schema
    if isinstance(doc, dict):
        errs = schema_check(uid, doc)
        if errs:
            r["checks"]["output_schema"] = ("FAIL " + str(len(errs)) + " errors; first: "
                                            + str(list(errs[0].absolute_path)) + " " + errs[0].message[:110])
        else:
            r["checks"]["output_schema"] = "OK"
    # live probes
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    probes = sorted(pdir.glob("probe*.py")) if pdir.exists() else []
    if not probes:
        r["checks"]["probes_live"] = "FAIL no probe scripts in " + pdir.name
    else:
        for pr in probes:
            rc, tail = None, ""
            try:
                cp = subprocess.run([sys.executable, "-B", str(pr)], cwd=str(REPO),
                                    capture_output=True, text=True, timeout=300)
                rc = cp.returncode
                lines = (cp.stdout or "").strip().splitlines()
                if lines:
                    tail = lines[-1][:150]
                elif (cp.stderr or "").strip():
                    tail = cp.stderr.strip().splitlines()[-1][:150]
            except subprocess.TimeoutExpired:
                rc, tail = "TIMEOUT", ""
            except Exception as exc:
                rc, tail = "SPAWN-ERR", type(exc).__name__
            r["probe_rows"].append({"probe": pr.name, "rc": rc, "tail": tail})
        bad = [p for p in r["probe_rows"] if p["rc"] != 0]
        r["checks"]["probes_live"] = ("OK " + str(len(r["probe_rows"])) + " probes" if not bad
                                      else "FAIL " + ", ".join(str(p["probe"]) + " rc=" + str(p["rc"]) for p in bad))
    results[uid] = r

# receipt admission via the estate gate for receipt-typed artifacts
gate_rows = {}
for uid in UNITS:
    out_rel = wus[uid]["output_path"].replace("\\", "/")
    if "/receipts/" not in "/" + out_rel:
        continue
    art_p = REPO / out_rel
    if not art_p.exists():
        gate_rows[uid] = "SKIP artifact missing"
        continue
    try:
        cp = subprocess.run([sys.executable, "-B", str(REPO / "command-center" / "receipt_validate.py"), str(art_p)],
                            cwd=str(REPO), capture_output=True, text=True, timeout=120)
        outv = (cp.stdout or "") + (cp.stderr or "")
        flat = " ".join(outv.split())
        gate_rows[uid] = "rc=" + str(cp.returncode) + " :: " + flat[:170]
    except Exception as exc:
        gate_rows[uid] = "GATE-SPAWN-ERR " + type(exc).__name__ + " " + str(exc)[:80]

print("=" * 96)
n_pass = 0
for uid in UNITS:
    r = results[uid]
    fails = [k for k, v in r["checks"].items() if str(v).startswith("FAIL")]
    verdict = "PASS" if not fails else "FAIL"
    if verdict == "PASS":
        n_pass += 1
    print(uid, verdict, "| state=", str(r.get("state")), "| probes:", str(r["checks"].get("probes_live"))[:60])
    for k in sorted(r["checks"]):
        print("    ", k, ":", r["checks"][k][:150])
    for p in r["probe_rows"]:
        print("     probe", p["probe"], "rc=", str(p["rc"]), "|", p["tail"][:110])
    for w in r["warns"]:
        print("     warn:", w[:150])
    if r.get("bytes_note"):
        print("     bytes:", r["bytes_note"])
    if uid in gate_rows:
        print("     receipt_gate:", gate_rows[uid][:180])
print("=" * 96)
print("SUMMARY:", str(n_pass) + "/" + str(len(UNITS)), "units PASS full live re-verification")
