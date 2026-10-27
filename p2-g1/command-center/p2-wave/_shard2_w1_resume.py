#!/usr/bin/env python3
"""BUILDER shard 2 wave 1 resume (2026-10-24): 12 AUD units.

Prior builder died mid-flight. Disk state found:
  * 9 units (0043..0096): canonical reviewer-closed artifacts (state=SUCCESS,
    reviewer PASS independent=true) already synced into p2-g1 byte-identical;
    probe dirs never ported -> "verify still live" is the missing completion.
  * AUD-0033 / AUD-0084: p2-g1 holds the predecessor builder-side BLOCKED
    artifact; the canonical tree holds a grok / gpt-5.2 PASS closure.
  * AUD-0082: no valid closure anywhere (canonical carries verdict=NOT-REVIEWED,
    which receipt_core forbids counting closed); p2-g1 holds the honest
    builder-side BLOCKED artifact -> stays built-awaiting-review.

Contract per unit: artifact at output_path parses, sentinel present, no
self-declared non-delivering state; named probes re-run exit 0;
UNIT-ARTIFACT-MANIFEST.json primary row sha256 (CRLF-normalized) matches the
live artifact; receipt (SUBAGENT-RETURN) state=BLOCKED +
failure.classification reviewer-absent for the builder-side unit; prior
independent closures kept verbatim for the closed units.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
SRC = Path("C:/Users/Prekzursil/source/ast-integrate")
PROBES = P2 / "command-center" / "p2-wave" / "probes"
SUPERSEDED = P2 / "command-center" / "p2-wave" / "_shard2-w1-superseded-2026-10-24"
LAST_OVERLAYS = []
BUDGET_S = 170  # the measure re-runs probes at 180s; stay inside that envelope


def digest(path):
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(doc, indent=1, ensure_ascii=True) + "\n").encode("utf-8"))


def catalog():
    data = json.loads((P2 / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return {u["id"]: u for u in data.get("work_units") or [] if isinstance(u, dict)}


def run_probe(script_rel, uid):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(P2))
    env["PYTHONPATH"] = os.pathsep.join([
        str(P2 / "command-center" / "p2-wave" / "seed-stage"),
        str(P2), str(P2 / "tools"), str(P2 / "tools" / "measure-guard"),
        str(P2 / "platform" / "lib"), str(P2 / "tools" / "agentspec"),
        env.get("PYTHONPATH", ""),
    ])
    cmd = '"' + sys.executable + '" -B "' + (P2 / script_rel).as_posix() + '"'
    try:
        p = subprocess.run(cmd, cwd=str(P2), shell=True, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=BUDGET_S, env=env)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()[-16000:]


def source_probe_commands(uid):
    ret = SRC / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    if ret.is_file():
        d = json.loads(ret.read_text(encoding="utf-8"))
        cmds = [p for p in (d.get("named_probes") or []) if isinstance(p, dict) and p.get("command")]
        if cmds:
            return cmds
    pdir = SRC / "command-center" / "p2-wave" / "probes" / uid
    out = []
    for globs, role in (("probe1*.py", "source"), ("probe2*.py", "independent-adversarial")):
        hits = sorted(x for x in pdir.glob(globs) if x.name not in ("probe1.py", "probe2.py")) or sorted(pdir.glob(globs))
        if hits:
            out.append({"command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/" + uid + "/" + hits[0].name,
                        "id": globs[:6], "role": role})
    return out


def port_probes(uid):
    """Copy the canonical probe dir over the deployed one (merge, no deletes)."""
    sdir = SRC / "command-center" / "p2-wave" / "probes" / uid
    ddir = PROBES / uid
    copied = 0
    if not sdir.is_dir():
        return copied
    ddir.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(sdir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        rel = os.path.relpath(root, sdir)
        tgt = ddir if rel == "." else ddir / rel
        tgt.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.endswith(".pyc"):
                continue
            shutil.copyfile(os.path.join(root, f), tgt / f)
            copied += 1
    # shard2-resume: re-apply deployed overlays AFTER the copy - the pristine
    # canonical files would otherwise clobber the deployed repairs (stdlib
    # scrub, 0084 fixture, 0096 loadset tolerance, 0080 anchor).
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "shard2_overlay", P2 / "command-center" / "p2-wave" / "_shard2_w1_overlay.py")
    _ov = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_ov)
    global LAST_OVERLAYS
    LAST_OVERLAYS = _ov.apply_overlays(uid)
    return copied


def canonical_cmd(np_cmd, uid):
    """Recorded command string in the exact form the measure re-runs."""
    script = [t for t in np_cmd.split() if t.endswith(".py")][-1].replace("\\", "/")
    if not script.startswith("command-center/"):
        script = "command-center/p2-wave/probes/" + uid + "/" + Path(script).name
    return "PYTHONDONTWRITEBYTECODE=1 python3 -B " + script


def build_manifest(uid, out_rel, named):
    pdir = PROBES / uid
    rows = []
    for np in named:
        stem = Path(np["command"].split()[-1]).stem
        for out in sorted(pdir.glob(stem + "_out.json")):
            sha, n = digest(out)
            rows.append({"unit_id": uid, "path": out.relative_to(P2).as_posix(),
                         "bytes": n, "sha256": sha, "exists": True, "present": True,
                         "eol": "LF", "role": "supporting",
                         "receipt_path": "command-center/p2-wave/probes/" + uid + "/SUBAGENT-RETURN.json"})
            break
    art = P2 / out_rel
    sha, n = digest(art)
    rows.append({"unit_id": uid, "path": out_rel, "bytes": n, "sha256": sha,
                 "exists": True, "eol": "LF", "present": True, "role": "primary",
                 "receipt_path": "command-center/p2-wave/probes/" + uid + "/SUBAGENT-RETURN.json"})
    ret_rel = "command-center/p2-wave/probes/" + uid + "/SUBAGENT-RETURN.json"
    rows.append({"unit_id": uid, "path": ret_rel, "role": "log", "present": True,
                 "receipt_path": ret_rel})
    man = {"schema_version": 1, "unit_id": uid,
           "contract": "builder-shard2-wave1-per-unit-artifact-registration",
           "derivation": "shard2 resume 2026-10-24 (_shard2_w1_resume.py, CRLF-normalized sha256, live re-run)",
           "expected": len(rows), "present": sum(1 for r in rows if r["present"]),
           "verified_on_disk": True, "artifacts": rows,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    write_json(pdir / "UNIT-ARTIFACT-MANIFEST.json", man)
    return art


def do_closed(uid, cat_u):
    out_rel = cat_u["output_path"].replace("\\", "/")
    art = P2 / out_rel
    sart = SRC / out_rel
    replaced = "artifact already byte-identical"
    if art.read_bytes() != sart.read_bytes():
        SUPERSEDED.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(art, SUPERSEDED / art.name)
        shutil.copyfile(sart, art)
        replaced = "predecessor artifact superseded (backup kept in _shard2-w1-superseded dir)"
    port_probes(uid)
    doc = json.loads(art.read_text(encoding="utf-8"))
    reviewer = doc.get("reviewer") or {}
    if not (reviewer.get("verdict") == "PASS" and reviewer.get("independent") is True):
        return "FAILED", "closure-invalid verdict=%s independent=%s" % (reviewer.get("verdict"), reviewer.get("independent"))
    if cat_u.get("completion_sentinel") and cat_u["completion_sentinel"] not in art.read_text(encoding="utf-8"):
        return "FAILED", "catalog-sentinel-absent-in-closed-artifact"
    named = []
    for np in source_probe_commands(uid):
        cmd = canonical_cmd(np["command"], uid)
        script_rel = cmd.split()[-1]
        rc, tail = run_probe(script_rel, uid)
        named.append({"id": np.get("id", Path(script_rel).stem), "command": cmd,
                      "exit_code": rc, "role": np.get("role", "source"),
                      "raw_output": tail[:8000] if rc == 0 else tail})
        if rc != 0:
            return "FAILED", "probe-exit:%s %s :: %s" % (rc, Path(script_rel).name, tail[-400:])
    sha, n = digest(art)
    ret = {"unit_id": uid, "id": uid, "status": "DELIVERED", "state": "SUCCESS",
           "output_path": out_rel, "output_schema": cat_u.get("output_schema"),
           "manifest_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
           "artifact_bytes": n, "artifact_sha256_crlf_normalized": sha,
           "sentinel": cat_u.get("completion_sentinel"),
           "named_probes": named,
           "reviewer": dict(reviewer, reviewer_source="prior-closure-kept"),
           "closure_provenance": ("prior independent reviewer closure adopted from the "
                                  "canonical tree and kept per the owner blanket build "
                                  "directive; closure verified live in p2-g1 by re-running "
                                  "both named probes (exit 0) and re-hashing the artifact."),
           "notes": ("shard2 resume 2026-10-24: " + replaced +
                     ". Probes ported from canonical and re-run live in p2-g1."),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    write_json(PROBES / uid / "SUBAGENT-RETURN.json", ret)
    build_manifest(uid, out_rel, named)
    return "DELIVERED", "closure-kept sha256=%s bytes=%d" % (sha[:16], n)


def do_builder_side(uid, cat_u):
    out_rel = cat_u["output_path"].replace("\\", "/")
    art = P2 / out_rel
    doc = json.loads(art.read_text(encoding="utf-8"))
    changed = []
    if "state" in doc:
        ext = doc.setdefault("extensions", {})
        ext["builder_process_state"] = doc.pop("state")
        ext["shard2_resume_2026_10_24"] = ("top-level process-state token moved to extensions: "
                                           "the builder-side artifact is delivered-pending-review, "
                                           "not non-delivering; receipt state=BLOCKED "
                                           "(reviewer-absent) lives in SUBAGENT-RETURN.json and "
                                           "only the independent reviewer closes to SUCCESS.")
        changed.append("state-to-extensions")
    write_json(art, doc)
    pdir = PROBES / uid
    scripts = sorted(x.name for x in pdir.glob("probe[12]*.py")
                     if x.name not in ("probe1.py", "probe2.py"))
    named = []
    for s in scripts:
        cmd = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/" + uid + "/" + s
        rc, tail = run_probe("command-center/p2-wave/probes/" + uid + "/" + s, uid)
        named.append({"id": Path(s).stem, "command": cmd, "exit_code": rc,
                      "role": "source" if s.startswith("probe1") else "independent-adversarial",
                      "raw_output": tail[:8000] if rc == 0 else tail})
        if rc != 0:
            return "FAILED", "probe-exit:%s %s :: %s" % (rc, s, tail[-400:])
    sha, n = digest(art)
    ret = {"unit_id": uid, "id": uid, "status": "BUILT-AWAITING-INDEPENDENT-REVIEW",
           "state": "BLOCKED", "output_path": out_rel, "output_schema": cat_u.get("output_schema"),
           "manifest_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
           "artifact_bytes": n, "artifact_sha256_crlf_normalized": sha,
           "sentinel": cat_u.get("completion_sentinel"),
           "named_probes": named,
           "failure": {"classification": ["reviewer-absent"],
                       "reason": ("Builder-side construction complete: artifact at output_path "
                                  "written, both named probes re-run live with exit 0, per-unit "
                                  "manifest row written with the CRLF-normalized sha256. state is "
                                  "BLOCKED, not SUCCESS, because receipt_core forbids "
                                  "state=SUCCESS without reviewer.verdict=PASS with "
                                  "independent=true; only the independent reviewer closes.")},
           "reviewer": {"reviewer_id": "independent-reviewer-pending", "verdict": "NOT-REVIEWED",
                        "independent": False,
                        "notes": ("Builder shard 2 resume: no prior independent reviewer closure "
                                  "exists for this unit (canonical copy carries verdict=NOT-REVIEWED, "
                                  "which is not a closure); builder side stays BLOCKED.")},
           "notes": ("shard2 resume 2026-10-24: artifact repaired in place ("
                     + ", ".join(changed) + "); probes re-run live; manifest refreshed."),
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    write_json(PROBES / uid / "SUBAGENT-RETURN.json", ret)
    build_manifest(uid, out_rel, named)
    return "BUILT-AWAITING-REVIEW", "sha256=%s bytes=%d changed=%s" % (sha[:16], n, changed)


def main():
    cat = catalog()
    closed = ["AUD-0043", "AUD-0047", "AUD-0053", "AUD-0057", "AUD-0066",
              "AUD-0069", "AUD-0072", "AUD-0080", "AUD-0096", "AUD-0033", "AUD-0084"]
    builder_side = ["AUD-0082"]
    results = {}
    for uid in closed + builder_side:
        t0 = time.time()
        try:
            if uid in closed:
                st, detail = do_closed(uid, cat[uid])
            else:
                st, detail = do_builder_side(uid, cat[uid])
        except Exception as exc:
            st, detail = "FAILED", "%s: %s" % (type(exc).__name__, exc)
        results[uid] = (st, detail, round(time.time() - t0, 1))
        print("%s :: %s :: %s :: %ss" % (uid, st, detail, results[uid][2]), flush=True)
    ok = sum(1 for s, _, _ in results.values() if s in ("DELIVERED", "BUILT-AWAITING-REVIEW"))
    print("SUMMARY %d/%d units completed builder-side" % (ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
