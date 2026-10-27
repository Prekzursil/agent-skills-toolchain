#!/usr/bin/env python3
# Independent reviewer battery - wave 2 shard 16.
# Re-derives every contract check from bytes. Exit 0 = unit PASS.
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

HOME = Path.home()
REPO = HOME / "p2-g1"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "SEVERED", "TIMEOUT"}
ENVPAT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+")
FAILS = []

def chk(cond, code):
    if not cond:
        FAILS.append(code)
    return bool(cond)

def norm_sha(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()

def load_json(p):
    return json.loads(p.read_text(encoding="utf-8"))

def run_probe(uid, cmd):
    while True:
        m = ENVPAT.match(cmd)
        if not m:
            break
        cmd = cmd[m.end():]
    parts = cmd.split()
    if parts and parts[0] in ("python3", "python"):
        parts[0] = sys.executable
    try:
        r = subprocess.run(parts, cwd=str(REPO), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        rc = r.returncode
        tail = ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        rc, tail = 124, "TIMEOUT"
    except Exception as exc:
        rc, tail = 125, type(exc).__name__
    lines = tail.splitlines() if tail else []
    marker = any(ln.startswith("SUCCESS") for ln in lines)
    last = lines[-1][:100] if lines else ""
    return rc, marker, last

def main(uid):
    del FAILS[:]
    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    unit = next((u for u in cat.get("work_units") or [] if u.get("id") == uid), None)
    if unit is None:
        print("VERDICT", uid, "FAIL catalog-entry-absent")
        return 1
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema_rel = str(unit.get("output_schema") or "").replace("\\", "/")
    sentinel = str(unit.get("completion_sentinel") or "")
    out = REPO / out_rel
    if not chk(out.is_file(), "artifact-absent"):
        print("VERDICT", uid, "FAIL", ";".join(FAILS))
        return 1
    size = out.stat().st_size
    chk(size > 0, "artifact-empty")
    raw = out.read_bytes()
    live = norm_sha(raw)
    try:
        doc = load_json(out)
        chk(isinstance(doc, dict), "artifact-not-dict")
    except Exception as exc:
        doc = None
        FAILS.append("artifact-unparseable-" + type(exc).__name__)
    if doc is None:
        print("VERDICT", uid, "FAIL", ";".join(FAILS))
        return 1
    st = str(doc.get("state") or "").upper()
    chk(st == "SUCCESS", "state-not-SUCCESS:" + (st or "NONE"))
    if sentinel:
        chk(sentinel in raw.decode("utf-8", errors="replace"), "sentinel-absent")
    chk(not isinstance(doc.get("failure"), dict), "failure-block-present")
    rev = doc.get("reviewer")
    if chk(isinstance(rev, dict), "reviewer-block-absent"):
        chk(str(rev.get("verdict") or "").upper() == "PASS", "verdict-not-PASS")
        chk(rev.get("independent") is True, "independent-not-true")
        chk(bool(str(rev.get("reviewer_id") or "").strip()), "reviewer-id-empty")
    man_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if chk(man_p.is_file(), "manifest-absent"):
        man = load_json(man_p)
        rows = [a for a in man.get("artifacts") or [] if isinstance(a, dict)
                and a.get("unit_id") == uid
                and str(a.get("path") or "").replace("\\", "/") == out_rel]
        chk(bool(rows), "manifest-row-absent")
        chk(any(a.get("sha256") == live and a.get("present") is True for a in rows),
            "manifest-sha-mismatch")
    ret_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    cmds = []
    if chk(ret_p.is_file(), "subagent-return-absent"):
        ret = load_json(ret_p)
        rst = str(ret.get("status") or ret.get("state") or "").upper()
        chk(rst not in NOT_DELIVERING, "return-status:" + rst)
        for item in (ret.get("named_probes") or ret.get("probes") or []):
            c = str(item.get("command") or "").strip()
            if c and c not in cmds:
                cmds.append(c)
    return (uid, out_rel, schema_rel, raw, doc, cmds, size)

def finish(uid, out_rel, schema_rel, raw, doc, probes, size):
    results = []
    if not probes:
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        probes = [str(p.relative_to(REPO)).replace("\\", "/")
                  for p in sorted(pdir.glob("probe1*.py")) + sorted(pdir.glob("probe2*.py"))]
    chk(len(probes) >= 1, "named-probes-absent")
    for i, c in enumerate(probes, 1):
        rc, marker, last = run_probe(uid, c)
        results.append((i, rc, marker, last))
        chk(rc == 0, "probe%d-rc-%d" % (i, rc))
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver
    try:
        errs = schema_resolver.validate_artifact(doc, schema_rel)
    except Exception as exc:
        errs = ["resolver-crash-" + type(exc).__name__]
    chk(len(errs) == 0, "schema-errors-%d" % len(errs))
    live = norm_sha(raw)
    ok = not FAILS
    print("VERDICT", uid, "PASS" if ok else "FAIL",
          "| bytes=%d live_sha=%s" % (size, live[:16]),
          "| schema_errs=%d" % len(errs))
    for i, rc, marker, last in results:
        print("  probe%d rc=%d marker=%s last=%s" % (i, rc, "Y" if marker else "N", last))
    for e in errs[:6]:
        print("  schema:", str(e)[:150])
    if FAILS:
        print("  FAIL-CHECKS:", ";".join(FAILS))
    return 0 if ok else 1

if __name__ == "__main__":
    r = main(sys.argv[1])
    raise SystemExit(finish(*r)) if isinstance(r, tuple) else SystemExit(r)
