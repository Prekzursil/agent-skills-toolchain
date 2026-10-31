#!/usr/bin/env python3
"""INDEPENDENT REVIEWER battery, wave-3 shard-11 (12 units, IMP-0194..IMP-0261).
Written fresh by the wave-3 shard-11 reviewer agent. READ-ONLY over receipts:
never writes any reviewed artifact. Checks A,B,C2,C3,D,E,F,G per task contract.
Output: verify_out.json next to this script. Exit 0 only when all hold.
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except Exception:
    jsonschema = None
    Draft202012Validator = None
    Registry = None

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = [
    "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204", "IMP-0207",
    "IMP-0219", "IMP-0223", "IMP-0224", "IMP-0228", "IMP-0229", "IMP-0261",
]
SELF_BAD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 600
ASTINT = "file:///C:/Users/Prekzursil/source/ast-integrate"
P2G1 = "file:///C:/Users/Prekzursil/p2-g1"
IMP0261_DESCRIPTOR_REQUIRED = [
    "unit_id", "artifact_paths", "spec_anchor", "evidence", "test_ids",
    "negative_control_ids", "reviewer_verdict", "residual_unknowns",
]


def digest(p):
    raw = p.read_bytes().replace(bytes([13, 10]), bytes([10]))
    return hashlib.sha256(raw).hexdigest(), len(raw)


def raw_digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_core_validator():
    if Draft202012Validator is None:
        return None
    sch = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8")
    )
    core = dict(sch["$defs"]["receipt_core"])
    core["$defs"] = sch["$defs"]
    Draft202012Validator.check_schema(core)
    return Draft202012Validator(core)


def make_file_uri_registry():
    if Registry is None:
        return None
    docs = {}
    for name in ("artifact-class-profiles.schema.json", "receipt.schema.json"):
        docs[name] = json.loads(
            (REPO / "platform" / "schema" / name).read_text(encoding="utf-8")
        )
    reg = Registry()
    for base in (ASTINT, P2G1):
        for name, contents in docs.items():
            uri = base + "/platform/schema/" + name
            res = Resource.from_contents(contents, default_specification=DRAFT202012)
            reg = reg.with_resource(uri, res)
    return reg


def load_class_validator(schema_rel, reg):
    if Draft202012Validator is None:
        return None, "jsonschema-unavailable"
    shim = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    ref = str(shim.get("$ref") or "")
    if not ref:
        Draft202012Validator.check_schema(shim)
        return Draft202012Validator(shim, registry=reg), None
    m = re.match(r"^(file://[^#]+)#", ref)
    if m is None:
        return None, "unresolvable-dollarref"
    phys_uri = m.group(1)
    phys_rel = phys_uri.replace(ASTINT, "").replace(P2G1, "").lstrip("/")
    if not (REPO / phys_rel).is_file():
        return None, "physical-schema-absent:" + phys_rel
    phys = json.loads((REPO / phys_rel).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(shim)
    return Draft202012Validator(shim, registry=reg), None


def probe_cmds(uid, receipt, pdir):
    cmds = []

    def add(cmd):
        c = str(cmd).strip()
        if c and c not in cmds:
            cmds.append(c)

    for item in (receipt.get("named_probes") or []):
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            add(item["command"])
    ret_path = pdir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception:
            ret = {}
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                add(item["command"])
    for p in sorted(pdir.glob("probe[0-9]*.py")):
        add("PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/" + uid + "/" + p.name)
    return cmds


def winify(cmd, env):
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=([^ ]+) +", cmd)
        if m is None:
            return cmd
        env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
        cmd = cmd[m.end():]


def main():
    cat = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    byid = {u.get("id"): u for u in cat["work_units"] if isinstance(u, dict)}
    core_v = load_core_validator()
    reg = make_file_uri_registry()
    results = {}
    for uid in UNITS:
        rep = {"fails": [], "notes": [], "pending_closure": False, "probes": []}
        cu = byid.get(uid)
        if cu is None:
            rep["fails"].append("catalog-entry-absent")
            results[uid] = rep
            continue
        out_rel = str(cu.get("output_path") or "").replace(chr(92), "/")
        out = REPO / out_rel
        if not out.is_file() or out.stat().st_size == 0:
            rep["fails"].append("artifact-absent-or-empty:" + out_rel)
            results[uid] = rep
            continue
        try:
            receipt = json.loads(out.read_text(encoding="utf-8"))
        except Exception as exc:
            rep["fails"].append("unparseable:" + type(exc).__name__)
            results[uid] = rep
            continue
        st = str(receipt.get("state") or "").upper()
        if st in SELF_BAD:
            if uid == "IMP-0223" and st == "BLOCKED":
                fr = receipt.get("failure") if isinstance(receipt.get("failure"), dict) else {}
                cls = fr.get("classification") or []
                if "reviewer-absent" in cls:
                    rep["pending_closure"] = True
                    rep["notes"].append("builder-BLOCKED reviewer-absent: pending-closure candidate")
                else:
                    rep["fails"].append("self-BLOCKED-not-reviewer-absent:" + ",".join(map(str, cls)))
            else:
                rep["fails"].append("self-declared:" + st)
        if st != "SUCCESS" and not rep["pending_closure"]:
            rep["fails"].append("state-not-SUCCESS:" + st)
        rev = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
        if rep["pending_closure"]:
            if rev:
                rep["fails"].append("pending-closure-but-reviewer-present")
        else:
            if rev.get("verdict") != "PASS":
                rep["fails"].append("reviewer-verdict:" + repr(rev.get("verdict")))
            if rev.get("independent") is not True:
                rep["fails"].append("reviewer-independent-not-true")
        rep["notes"].append("reviewer_id=" + repr(rev.get("reviewer_id")))
        ret_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
        if ret_path.is_file():
            try:
                ret_doc = json.loads(ret_path.read_text(encoding="utf-8"))
                st_ret = str(ret_doc.get("status") or ret_doc.get("state") or "").upper()
                if st_ret in SELF_BAD:
                    rep["fails"].append("subagent-return:" + st_ret)
            except Exception:
                rep["fails"].append("subagent-return-unparseable")
        text = out.read_text(encoding="utf-8")
        sentinel = str(cu.get("completion_sentinel") or "")
        if sentinel and sentinel not in text:
            rep["fails"].append("sentinel-absent:" + sentinel)
        if core_v is not None:
            try:
                errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
                rep["notes"].append("strict-errors=" + str(len(errs)))
                for e in errs[:6]:
                    where = "/".join(str(x) for x in e.absolute_path) or "<root>"
                    rep["fails"].append("schema:" + where + "::" + e.message[:180])
                if len(errs) > 6:
                    rep["fails"].append("schema:more:" + str(len(errs) - 6))
            except Exception as exc:
                rep["fails"].append("c2-crash:" + type(exc).__name__ + ":" + str(exc)[:120])
        else:
            rep["notes"].append("jsonschema-unavailable")
        schema_decl = str(cu.get("output_schema") or "")
        schema_rel = schema_decl.split(" ")[0].replace(chr(92), "/")
        if schema_rel:
            if not (REPO / schema_rel).is_file():
                rep["fails"].append("output-schema-file-absent:" + schema_rel)
            elif reg is not None:
                cv, err = load_class_validator(schema_rel, reg)
                if err:
                    rep["fails"].append("outschema:" + err)
                else:
                    try:
                        errs = sorted(cv.iter_errors(receipt), key=lambda e: list(e.absolute_path))
                        rep["notes"].append("outschema-errors=" + str(len(errs)))
                        for e in errs[:6]:
                            where = "/".join(str(x) for x in e.absolute_path) or "<root>"
                            rep["fails"].append("outschema:" + where + "::" + e.message[:180])
                        if len(errs) > 6:
                            rep["fails"].append("outschema:more:" + str(len(errs) - 6))
                    except Exception as exc:
                        rep["fails"].append("c3-crash:" + type(exc).__name__ + ":" + str(exc)[:120])
            else:
                rep["notes"].append("referencing-unavailable")
        if "profile=" in schema_decl:
            missing = [k for k in IMP0261_DESCRIPTOR_REQUIRED if k not in receipt]
            if missing:
                rep["fails"].append("descriptor-required-missing:" + ",".join(missing))
            else:
                rep["notes"].append("descriptor-required=all-present")
        man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        snap_paths = [out, man_path]
        if not man_path.is_file():
            rep["fails"].append("manifest-absent")
            results[uid] = rep
            continue
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            rep["fails"].append("manifest-unparseable:" + type(exc).__name__)
            results[uid] = rep
            continue
        if not isinstance(man, dict):
            rep["fails"].append("manifest-not-object")
            results[uid] = rep
            continue
        rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
        prim = [a for a in rows if str(a.get("path") or "").replace(chr(92), "/") == out_rel]
        if not prim:
            rep["fails"].append("manifest-primary-row-absent")
        else:
            p0 = prim[0]
            if p0.get("present") is not True:
                rep["fails"].append("manifest-primary-present-not-true")
            live_sha, live_n = digest(out)
            if str(p0.get("sha256") or "") != live_sha:
                rep["fails"].append("manifest-primary-sha man=" + str(p0.get("sha256"))[:12] + " live=" + live_sha[:12])
            raw_n = out.stat().st_size
            if p0.get("bytes") not in (raw_n, live_n):
                rep["fails"].append("manifest-primary-bytes man=" + str(p0.get("bytes")) + " raw=" + str(raw_n) + " norm=" + str(live_n))
        for a in rows:
            rel = str(a.get("path") or "").replace(chr(92), "/")
            fp = REPO / rel
            if not fp.is_file():
                rep["fails"].append("manifest-row-absent:" + rel)
                continue
            snap_paths.append(fp)
            s2, n2 = digest(fp)
            raw_n2 = fp.stat().st_size
            if s2 != str(a.get("sha256") or ""):
                rep["fails"].append("manifest-row-sha:" + rel + " man=" + str(a.get("sha256"))[:12] + " live=" + s2[:12])
            if a.get("bytes") not in (raw_n2, n2):
                rep["fails"].append("manifest-row-bytes:" + rel + " man=" + str(a.get("bytes")) + " raw=" + str(raw_n2) + " norm=" + str(n2))
        rep["notes"].append("manifest-rows=" + str(len(rows)))
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        cmds = probe_cmds(uid, receipt, pdir)
        if not cmds:
            rep["fails"].append("no-live-probes-found")
            results[uid] = rep
            continue
        pre = {p: raw_digest(p) for p in snap_paths if p.is_file()}
        ok_runs = 0
        for cmd in cmds:
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env.pop("PYTHONPATH", None)
            env.pop("AST_INTEGRATE_ROOT", None)
            cmd = winify(cmd, env)
            toks = cmd.split(" ")
            if "-B" in toks:
                i = toks.index("-B")
                argv = [sys.executable, "-B"] + toks[i + 1:]
            else:
                argv = [sys.executable] + toks[1:]
            pname = Path(argv[-1]).name
            t0 = time.time()
            try:
                cp = subprocess.run(
                    argv, cwd=str(REPO), env=env, capture_output=True, text=True,
                    timeout=PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
                )
                rc, so, se = cp.returncode, cp.stdout or "", cp.stderr or ""
            except subprocess.TimeoutExpired:
                rep["fails"].append("probe-timeout:" + pname)
                rep["probes"].append({"cmd": cmd, "rc": "timeout"})
                continue
            rep["probes"].append({
                "cmd": cmd, "rc": rc, "secs": round(time.time() - t0, 1),
                "success_marker": "SUCCESS:" in so,
                "failed_marker": "FAILED:" in (so + se),
                "tail": (so + se).strip()[-160:],
            })
            if rc != 0:
                rep["fails"].append("probe-rc:" + pname + "=" + str(rc))
            if "SUCCESS:" not in so:
                rep["fails"].append("probe-no-success-marker:" + pname)
            if "FAILED:" in so or "FAILED:" in se:
                tail = so + se
                k = tail.find("FAILED:")
                rep["fails"].append("probe-failed-marker:" + pname + "::" + tail[k:k + 140])
            if rc == 0 and "SUCCESS:" in so and "FAILED:" not in (so + se):
                ok_runs += 1
        rep["notes"].append("probes-ok=" + str(ok_runs) + "/" + str(len(cmds)))
        post = {p: raw_digest(p) for p in pre}
        for p, before in pre.items():
            if post.get(p) != before:
                rep["fails"].append("probe-mutated-reviewed-artifact:" + p.name)
        results[uid] = rep
    out_doc = {"wave": "p2-g1-wave-3", "shard": 11, "units": results}
    (Path(__file__).resolve().parent / "verify_out.json").write_text(
        json.dumps(out_doc, indent=1), encoding="utf-8"
    )
    print("=" * 100)
    n_pass = 0
    n_pending = 0
    for uid in UNITS:
        rep = results.get(uid, {"fails": ["no-result"], "notes": []})
        tag = "PASS"
        if rep["fails"]:
            tag = "FAIL"
        elif rep.get("pending_closure"):
            tag = "PASS-PENDING-CLOSURE"
            n_pending += 1
        else:
            n_pass += 1
        print(uid, tag)
        for f in rep["fails"]:
            print("    - " + f)
        for nline in rep["notes"]:
            print("    # " + nline)
    print("=" * 100)
    print("wave-3 shard-11: " + str(n_pass) + " confirmed, " + str(n_pending)
          + " pending-closure, " + str(len(UNITS) - n_pass - n_pending) + " failing")
    n_bad = sum(1 for r in results.values() if r["fails"])
    if n_bad == 0:
        print("SUCCESS:w3s11-review all units hold all applicable checks")
        return 0
    print("FAILED:w3s11-review " + str(n_bad) + "/" + str(len(UNITS)) + " units failing")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
