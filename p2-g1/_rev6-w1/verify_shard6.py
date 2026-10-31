"""INDEPENDENT REVIEWER wave1 shard6 - adversarial per-unit verification.

Checks per unit (ALL must hold for PASS):
  C1 catalog entry with output_path/output_schema
  C2 artifact exists, non-empty, parses, not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  C3 completion sentinel present
  C4 probes/<uid>/ has SUBAGENT-RETURN.json (not self-blocked) + UNIT-ARTIFACT-MANIFEST.json
  C5 live named probes re-run by THIS process, every exit code == 0
  C6 recomputed sha256 (CRLF->LF) of live artifact matches manifest row (path equal, present true)
  C7 artifact validates against catalog output_schema via the live resolver
  C8 reviewer closure: verdict PASS and independent is True
"""
import hashlib, json, os, subprocess, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["CNF-0180", "CNF-0188", "CNL-0076", "IMP-0003", "IMP-0013",
         "IMP-0014", "IMP-0018", "IMP-0020", "IMP-0022"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
sys.path.insert(0, str(REPO / "platform" / "lib"))
os.environ.setdefault("AST_INTEGRATE_ROOT", str(REPO))
import schema_resolver  # noqa: E402

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by_id = {u.get("id"): u for u in cat.get("work_units", [])}


def sha_lf(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd, timeout=2700):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    hook = str(REPO / "command-center/p2-wave/seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([hook, str(REPO), str(REPO / "tools"),
        str(REPO / "tools/measure-guard"), str(REPO / "platform/lib"),
        str(REPO / "tools/agentspec"), env.get("PYTHONPATH", "")])
    exe = sys.executable.replace("\\", "/")
    wrap = (REPO / "command-center/p2-wave/seed-stage/g1_python.py")
    if "python3" in cmd:
        cmd = cmd.replace("python3", exe + " " + wrap.as_posix(), 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=timeout, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def measure(uid):
    m = subprocess.run([sys.executable, "-I",
                        str(REPO / "command-center/p2-wave/_measure_one_delivered.py"), uid],
                       cwd=str(REPO), capture_output=True, text=True, timeout=3600)
    return m.returncode, (m.stdout or "").strip(), (m.stderr or "").strip()


results = {}
for uid in UNITS:
    c = {}
    u = by_id.get(uid)
    c["C1_catalog_entry"] = bool(u)
    out_rel = (u.get("output_path") or "").replace("\\", "/") if u else ""
    op = REPO / out_rel if out_rel else None
    art = None
    if op is None or not op.is_file() or op.stat().st_size <= 0:
        c["C2_artifact_parse"] = "artifact-missing-or-empty"
    else:
        try:
            art = json.loads(op.read_text(encoding="utf-8"))
            st = str((art or {}).get("state") or "").upper()
            c["C2_artifact_parse"] = ("self-declared:" + st) if st in NOT_DELIVERING else True
        except Exception as e:
            c["C2_artifact_parse"] = "parse-error:" + type(e).__name__
    if op is not None and op.is_file() and u and u.get("completion_sentinel"):
        c["C3_sentinel"] = u.get("completion_sentinel") in op.read_text(encoding="utf-8")
    else:
        c["C3_sentinel"] = False
    pdir = REPO / "command-center/p2-wave/probes" / uid
    ret_p, man_p = pdir / "SUBAGENT-RETURN.json", pdir / "UNIT-ARTIFACT-MANIFEST.json"
    ret = man = None
    try:
        ret = json.loads(ret_p.read_text(encoding="utf-8")) if ret_p.is_file() else None
        man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.is_file() else None
    except Exception:
        pass
    c["C4_probe_dir"] = bool(ret) and bool(man)
    if ret:
        st_ret = str(ret.get("status") or ret.get("state") or "").upper()
        if st_ret in NOT_DELIVERING:
            c["C4_probe_dir"] = "return:" + st_ret
    # C5: re-run every named probe OURSELVES from SUBAGENT-RETURN
    cmds = []
    if isinstance(ret, dict):
        for item in (ret.get("named_probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmds.append(item["command"].strip())
        for item in (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                cmd = item["command"].strip()
                if cmd and cmd not in cmds:
                    cmds.append(cmd)
    rcs = []
    fail_tail = None
    for cmd in cmds:
        rc, tail = run(cmd)
        rcs.append(rc)
        if rc != 0:
            fail_tail = tail[-1200:]
            break
    c["_probe_rcs"] = rcs
    if fail_tail:
        c["_probe_fail_tail"] = fail_tail
    mrc, mout, merr = measure(uid)
    c["_measure_rc"] = mrc
    lines = mout.splitlines() if mout else []
    c["_measure_tail"] = lines[-2:] if lines else [merr.strip()[-300:]]
    c["C5_probes_live"] = (mrc == 0) and bool(rcs) and all(r == 0 for r in rcs)
    # C6: my own sha recomputation vs manifest row
    if man and op and op.is_file():
        sha, nb = sha_lf(op)
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        match = [a for a in rows
                 if str(a.get("path") or "").replace("\\", "/") == out_rel
                 and str(a.get("sha256") or "") == sha and a.get("present") is True]
        c["_live_sha"] = sha
        c["C6_manifest_sha"] = True if match else \
            "mismatch (live " + sha[:12] + "..., " + str(len(rows)) + " unit rows)"
    else:
        c["C6_manifest_sha"] = "manifest-or-artifact-missing"
    # C7: live-resolver schema validation
    try:
        errs = schema_resolver.validate_artifact(art, (u or {}).get("output_schema"))
        c["C7_output_schema"] = True if not errs else errs[:6]
    except Exception as e:
        c["C7_output_schema"] = "resolver:" + type(e).__name__ + ":" + str(e)
    # C8: reviewer closure
    rv = (art or {}).get("reviewer") or {}
    ok = (rv.get("verdict") == "PASS") and (rv.get("independent") is True)
    c["C8_reviewer_closure"] = True if ok else json.dumps(rv)[:200]
    results[uid] = c

out_path = REPO / "_rev6-w1" / "verify_results.json"
out_path.write_text(json.dumps(results, indent=1), encoding="utf-8", newline="\n")
HARD = ["C1_catalog_entry", "C2_artifact_parse", "C3_sentinel", "C4_probe_dir",
        "C5_probes_live", "C6_manifest_sha", "C7_output_schema", "C8_reviewer_closure"]
for uid, c in results.items():
    bad = [k for k in HARD if c.get(k) is not True]
    if bad:
        detail = "; ".join(k + "=" + repr(c.get(k))[:200] for k in bad)
        print("FAIL " + uid + "  -> " + detail)
    else:
        print("PASS " + uid)
print()
print("detail written: " + str(out_path))
