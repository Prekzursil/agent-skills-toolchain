#!/usr/bin/env python3
"""INDEPENDENT REVIEWER wave-3 shard-21 (12 units) - read-only verification.

Written fresh by the wave-3 shard-21 reviewer agent (never a builder of these
units). Units taken verbatim from the builder shard dispatch:
TST-0151, TST-0155, TST-0158, TST-0161, TST-0162, TST-0163, TST-0164,
TST-0165, TST-0166, TST-0168, TST-0169, TST-0171.

Per unit, mechanically verifies:
  A  artifact at catalog output_path: exists, non-empty, parses as JSON,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT for a content reason
     (a BLOCKED carrying failure.classification reviewer-absent is the
     expected builder terminal and is closable by this reviewer)
  B  receipt closure consistency: state=SUCCESS requires recorded
     reviewer.verdict == PASS and reviewer.independent == true
  E  catalog completion_sentinel appears verbatim in the receipt text
  I  receipt unit_id matches
  C  output_schema validation via platform/lib/schema_resolver.validate_artifact
     against the catalog-declared physical schema (fail-closed resolver)
  D  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: parse; primary row
     (role=primary, path == output_path) present=true with sha256 + bytes
     matching a live recompute over CRLF-normalized bytes; every other row
     present on disk with a matching digest
  F  every manifest-registered probe script re-executed live by the
     reviewer from repo cwd: rc == 0, SUCCESS marker present, FAILED
     marker absent; at least one probe per unit

Read-only: never mutates a receipt or manifest. Verdicts go to
_reviewer-w3s21/verify_out.json.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver  # noqa: E402

OUT_JSON = REPO / "_reviewer-w3s21" / "verify_out.json"
SELF_BAD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 600
UNITS = [
    "TST-0151", "TST-0155", "TST-0158", "TST-0161", "TST-0162", "TST-0163",
    "TST-0164", "TST-0165", "TST-0166", "TST-0168", "TST-0169", "TST-0171",
]


def digest(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def check(uid, cat_unit):
    res = {"unit": uid, "checks": {}, "probe_runs": []}
    ck = res["checks"]

    def setck(name, ok, detail=""):
        ck[name] = {"ok": bool(ok), "detail": str(detail)}

    if not cat_unit:
        setck("catalog-entry-present", False, "no catalog entry")
        return res
    setck("catalog-entry-present", True)
    op = cat_unit.get("output_path") or ""
    osch = cat_unit.get("output_schema") or ""
    sentinel = cat_unit.get("completion_sentinel") or ("SUCCESS:" + uid)
    setck("catalog-output_path-agrees", op == "command-center/receipts/%s.json" % uid, op)

    art = REPO / op
    if not art.is_file():
        setck("artifact-exists", False, op)
        return res
    setck("artifact-exists", True, op)
    if art.stat().st_size <= 0:
        setck("artifact-nonempty", False, "0 bytes")
        return res
    setck("artifact-nonempty", True, "%d bytes" % art.stat().st_size)
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        setck("artifact-parses", False, str(exc))
        return res
    setck("artifact-parses", True, "%d bytes" % art.stat().st_size)

    state = str(doc.get("state") or "").upper()
    fc = []
    fblock = doc.get("failure")
    if isinstance(fblock, dict):
        fc = [str(x) for x in (fblock.get("classification") or [])]
    if state in SELF_BAD:
        closable = (state == "BLOCKED") and (fc == ["reviewer-absent"])
        setck("not-self-blocked", closable,
              "state=%s classification=%s closable=%s" % (state, fc, closable))
    else:
        setck("not-self-blocked", True, state)

    setck("unit_id-match", doc.get("unit_id") == uid, str(doc.get("unit_id")))
    setck("sentinel-in-receipt", sentinel in text, sentinel)

    rev = doc.get("reviewer") or {}
    if state == "SUCCESS":
        ok = (rev.get("verdict") == "PASS") and (rev.get("independent") is True)
        setck("closure-consistent", ok, json.dumps(
            {k: rev.get(k) for k in ("reviewer_id", "verdict", "independent")},
            sort_keys=True))
    else:
        ok = (rev.get("verdict") != "PASS") or (rev.get("independent") is not True)
        setck("closure-consistent", ok,
              "unclosed terminal carries no PASS closure" if ok
              else "terminal carries a PASS closure")

    setck("catalog-output_schema-present", bool(osch), osch)
    if osch:
        try:
            errs = schema_resolver.validate_artifact(doc, osch)
        except Exception as exc:
            errs = ["resolver-error: %s" % exc]
        setck("output_schema-valid", not errs,
              "%d error(s): %s" % (len(errs), " | ".join(errs[:8])))
    return res


def check_manifest_and_probes(uid, res):
    ck = res["checks"]

    def setck(name, ok, detail=""):
        ck[name] = {"ok": bool(ok), "detail": str(detail)}

    op = "command-center/receipts/%s.json" % uid
    art = REPO / op
    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not mp.is_file():
        setck("manifest-present", False, str(mp))
        return res
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        setck("manifest-present", False, "unparseable: %s" % exc)
        return res
    setck("manifest-present", True)
    rows = man.get("artifacts") or []
    prim = [r for r in rows if r.get("role") == "primary"]
    if len(prim) != 1:
        setck("manifest-primary-row", False, "%d primary rows" % len(prim))
        return res
    p0 = prim[0]
    if p0.get("path") != op:
        setck("manifest-primary-row", False, "primary path %r != %r" % (p0.get("path"), op))
        return res
    if not p0.get("present"):
        setck("manifest-primary-row", False, "present != true")
        return res
    sha, n = digest(art)
    if (p0.get("sha256") != sha) or (p0.get("bytes") != n):
        setck("manifest-primary-sha", False,
              "manifest=(%s,%s) live=(%s,%s)" % (p0.get("sha256"), p0.get("bytes"), sha, n))
        return res
    setck("manifest-primary-sha", True, "%s... %dB (CRLF-normalized)" % (sha[:16], n))
    bad_support = []
    for r in rows:
        if r.get("role") == "primary":
            continue
        sp = REPO / str(r.get("path"))
        if not sp.is_file():
            bad_support.append("%s:absent" % r.get("path"))
            continue
        s2, n2 = digest(sp)
        if r.get("sha256") != s2:
            bad_support.append("%s:sha-mismatch" % r.get("path"))
        elif r.get("bytes") not in (n2, sp.stat().st_size):
            bad_support.append("%s:bytes-mismatch(%s vs %s)" % (r.get("path"), r.get("bytes"), n2))
    setck("manifest-supporting-rows", not bad_support,
          "; ".join(bad_support[:8]) or ("%d rows ok" % (len(rows) - 1)))

    prefix = "command-center/p2-wave/probes/%s/probe" % uid
    probes = [r for r in rows
              if str(r.get("path", "")).startswith(prefix)
              and str(r.get("path", "")).endswith(".py")]
    if not probes:
        setck("probes-registered", False, "no probe rows in manifest")
        return res
    setck("probes-registered", True, "%d probes" % len(probes))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    all_ok = True
    for r in probes:
        sp = REPO / str(r["path"])
        t0 = time.time()
        try:
            run = subprocess.run([sys.executable, "-B", str(sp)], cwd=str(REPO),
                                 capture_output=True, text=True, env=env,
                                 timeout=PROBE_TIMEOUT_S)
            out = (run.stdout or "") + (run.stderr or "")
            rc = run.returncode
        except subprocess.TimeoutExpired:
            out = "TIMEOUT after %ds" % PROBE_TIMEOUT_S
            rc = 124
        dt = round(time.time() - t0, 1)
        ok = (rc == 0) and ("SUCCESS:" in out) and ("FAILED:" not in out)
        all_ok = all_ok and ok
        res["probe_runs"].append({
            "probe": Path(r["path"]).name, "rc": rc, "secs": dt, "ok": ok,
            "tail": out[-500:],
        })
        setck("probe-live:%s" % Path(r["path"]).name, ok, "rc=%s in %ss" % (rc, dt))
    setck("probes-all-exit0", all_ok, "%d probes" % len(probes))
    return res


def main():
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u.get("id"): u for u in cat.get("work_units", []) if isinstance(u, dict)}
    out = {"reviewer": "independent-reviewer-w3s21", "wave": 3, "shard": 21,
           "units": [], "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    t0 = time.time()
    for uid in UNITS:
        r = check(uid, byid.get(uid))
        if "verdict" not in r:
            r = check_manifest_and_probes(uid, r)
        r["verdict"] = "PASS" if all(c["ok"] for c in r["checks"].values()) else "FAIL"
        r["failing"] = [k for k, v in r["checks"].items() if not v["ok"]]
        out["units"].append(r)
        print("%s: %s%s" % (uid, r["verdict"], ("  failing=%s" % r["failing"]) if r["failing"] else ""))
        sys.stdout.flush()
    out["wall_secs"] = round(time.time() - t0, 1)
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    npass = sum(1 for u in out["units"] if u["verdict"] == "PASS")
    print("")
    print("%d/%d units PASS; results -> %s" % (npass, len(UNITS), OUT_JSON))
    return 0 if npass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
