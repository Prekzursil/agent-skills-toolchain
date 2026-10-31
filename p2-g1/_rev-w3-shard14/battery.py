"""Independent reviewer battery - wave 3 shard 14 (12 units).

Re-derives every closing condition from the contract. Does NOT reuse builder
verify scripts. Per unit:
  A1 exists / A2 non-empty / A3 parses / A4 not-self-blocked
  A5 schema (own jsonschema pass against the PHYSICAL schema, not the shim
     absolute ref)
  A6 digests: CRLF->LF-normalized sha256 recomputed vs probe manifest row
     (sha + bytes + present + manifest receipt_state)
  A7 reviewer closure valid: verdict=PASS, independent=true, reviewer_id
     present and != author
  B  live probes re-run by THIS reviewer: exit 0 AND a SUCCESS marker
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IDS = ["IMP-0430", "IMP-0435", "IMP-0437", "IMP-0439", "IMP-0442", "IMP-0448",
       "IMP-0450", "IMP-0460", "IMP-0466", "IMP-0467", "IMP-0468", "IMP-0470"]

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
WU = {u.get("id"): u for u in cat["work_units"]}


def physical_schema(shim_path_rel: str):
    """Resolve the catalog-declared schema shim to its PHYSICAL definition
    inside THIS checkout (bytes verified identical to the absolute ref target)."""
    shim = json.loads((REPO / shim_path_rel).read_text(encoding="utf-8"))
    ref = shim.get("$ref") or ""
    m = re.match(r"^file:///.+#/\$defs/(.+)$", ref)
    frag = m.group(1) if m else None
    xphys = shim.get("x-physical-definition") or ""
    phys_rel = xphys.split("#")[0] if xphys else None
    if not (frag and phys_rel):
        raise RuntimeError(
            "cannot resolve physical schema for %s: ref=%r xphys=%r" % (shim_path_rel, ref, xphys))
    doc = json.loads((REPO / phys_rel).read_text(encoding="utf-8"))
    sub = doc.get("$defs", {}).get(frag)
    if sub is None:
        raise RuntimeError("fragment $defs/%s missing from %s" % (frag, phys_rel))

    def resolve(node, depth=0):
        if depth > 8:
            return node
        if isinstance(node, dict):
            r = node.get("$ref")
            if isinstance(r, str) and r.startswith("#/$defs/"):
                tgt = doc.get("$defs", {}).get(r.split("/")[-1])
                if tgt is not None:
                    merged = {k: v for k, v in tgt.items() if k != "$ref"}
                    extra = {k: v for k, v in node.items() if k != "$ref"}
                    for k, v in extra.items():
                        if k == "properties" and isinstance(v, dict) and isinstance(merged.get("properties"), dict):
                            merged["properties"] = {**merged["properties"], **v}
                        else:
                            merged[k] = v
                    return resolve(merged, depth + 1)
            return {k: resolve(v, depth) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(x, depth) for x in node]
        return node

    return resolve(sub), phys_rel + "#/$defs/" + frag


from jsonschema import Draft202012Validator  # noqa: E402


def lf_sha(p: Path):
    raw = p.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


results = {}
for uid in IDS:
    row = {"unit_id": uid, "checks": {}, "probe_runs": []}
    checks = row["checks"]
    entry = WU.get(uid)
    if entry is None:
        checks["catalog-entry"] = "FAIL: missing from WORK-UNIT-CATALOG"
        results[uid] = row
        continue
    out_rel = entry["output_path"]
    out_path = REPO / out_rel
    if not out_path.is_file():
        checks["A1-exists"] = "FAIL: artifact absent at catalog output_path %s" % out_rel
        results[uid] = row
        continue
    checks["A1-exists"] = "PASS (%s)" % out_rel
    nbytes = out_path.stat().st_size
    checks["A2-nonempty"] = "PASS" if nbytes > 0 else "FAIL: zero-byte artifact"
    try:
        doc = json.loads(out_path.read_text(encoding="utf-8"))
        checks["A3-parses"] = "PASS"
    except Exception as e:
        checks["A3-parses"] = "FAIL: %s" % e
        results[uid] = row
        continue
    state = doc.get("state")
    if state != "SUCCESS":
        checks["A4-not-blocked"] = "FAIL: top-level state=%r" % state
    elif isinstance(doc.get("failure"), dict):
        checks["A4-not-blocked"] = "FAIL: top-level failure object present (self-declared failure)"
    else:
        blob = out_path.read_text(encoding="utf-8", errors="replace")
        ra = re.search(r"reviewer-absent", blob)
        checks["A4-not-blocked"] = ("PASS" if not ra else
                                    "FAIL: reviewer-absent marker in receipt: " +
                                    blob[max(0, ra.start() - 80):ra.end() + 80])
    try:
        schema, where = physical_schema(entry["output_schema"])
        errs = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            first = errs[0]
            checks["A5-schema"] = "FAIL: %s :: %s: %s" % (where, list(first.path), first.message[:220])
        else:
            checks["A5-schema"] = "PASS (%s)" % where
    except Exception as e:
        checks["A5-schema"] = "FAIL: resolver error %s" % e
    man_rel = "command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid
    man_p = REPO / man_rel
    if not man_p.is_file():
        checks["A6-digest"] = "FAIL: manifest absent %s" % man_rel
    else:
        man = json.loads(man_p.read_text(encoding="utf-8"))
        mstate = man.get("receipt_state")
        rows = [a for a in man.get("artifacts", []) if a.get("path") == out_rel]
        if not rows:
            checks["A6-digest"] = "FAIL: manifest %s has no row for %s" % (man_rel, out_rel)
        else:
            a0 = rows[0]
            live_sha, live_len = lf_sha(out_path)
            rec_sha = str(a0.get("sha256") or "")
            rec_bytes = a0.get("bytes")
            prob = []
            if live_sha != rec_sha:
                prob.append("sha mismatch recorded=%s live=%s" % (rec_sha[:12], live_sha[:12]))
            if rec_bytes != live_len:
                prob.append("bytes mismatch recorded=%s live=%s" % (rec_bytes, live_len))
            if a0.get("present") is not True:
                prob.append("present!=true")
            if mstate not in ("SUCCESS",):
                prob.append("manifest receipt_state=%r" % mstate)
            checks["A6-digest"] = ("PASS (sha+bytes+present+manifest-state)" if not prob
                                   else "FAIL: " + "; ".join(prob))
    rev = doc.get("reviewer") or {}
    author = str(doc.get("produced_by") or doc.get("builder") or "")
    rid = str(rev.get("reviewer_id") or "")
    prob = []
    if rev.get("verdict") != "PASS":
        prob.append("verdict=%r" % rev.get("verdict"))
    if rev.get("independent") is not True:
        prob.append("independent=%r" % rev.get("independent"))
    if not rid:
        prob.append("reviewer_id missing")
    if author and rid and rid == author:
        prob.append("self-review: reviewer_id==author %r" % rid)
    checks["A7-reviewer"] = "PASS" if not prob else "FAIL: " + "; ".join(prob)
    probes = sorted((REPO / "command-center/p2-wave/probes" / uid).glob("probe*.py"))
    ok_all = True
    if not probes:
        checks["B-probes"] = "FAIL: no probe*.py in probe dir"
        ok_all = False
    for pp in probes:
        t0 = time.time()
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        prer = {"probe": pp.name}
        try:
            cp = subprocess.run([sys.executable, "-B", str(pp)], cwd=str(REPO),
                                capture_output=True, text=True, timeout=900, env=env)
            out = (cp.stdout or "") + (cp.stderr or "")
            marker_ok = "SUCCESS:" in out
            entry_ok = cp.returncode == 0 and marker_ok
            prer.update({"rc": cp.returncode, "success_marker": bool(marker_ok),
                         "secs": round(time.time() - t0, 2),
                         "tail": (out.strip().splitlines()[-1][:170] if out.strip() else "")})
            if cp.returncode != 0:
                prer["verdict"] = "FAIL rc=%d" % cp.returncode
            elif not marker_ok:
                prer["verdict"] = "FAIL exit0 but no SUCCESS marker"
            if not entry_ok:
                ok_all = False
        except subprocess.TimeoutExpired:
            prer["verdict"] = "FAIL timeout>900s"
            ok_all = False
        row["probe_runs"].append(prer)
    if "B-probes" not in checks:
        n_ok = len([p for p in row["probe_runs"] if "verdict" not in p])
        checks["B-probes"] = ("PASS %d/%d probes exit0+marker" % (n_ok, len(row["probe_runs"]))
                              if ok_all else "FAIL (see probe_runs)")
    results[uid] = row

(REPO / "_rev-w3-shard14/results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
n_fail = sum(1 for r in results.values() if any(v.startswith("FAIL") for v in r["checks"].values()))
print("BATTERY-DONE units=%d failing_units=%d" % (len(results), n_fail))
for uid, r in results.items():
    bad = [k for k, v in r["checks"].items() if v.startswith("FAIL")]
    print(uid, "PASS" if not bad else "FAIL:" + ",".join(bad))
