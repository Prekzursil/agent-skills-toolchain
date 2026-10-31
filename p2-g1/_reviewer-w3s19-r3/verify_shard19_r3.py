#!/usr/bin/env python3
"""r3 battery - independent reviewer wave3 shard19, resumed run.

Same contract as r2 (dual schema instruments + positive control + probe
re-runs + CRLF-normalized manifest re-hash), plus:
  - receipt sha256 captured BEFORE and AFTER the whole battery (proves
    the reviewer left every receipt byte-unchanged)
  - environment transport note: PATH visibility of pwsh/powershell for
    the probe subprocess (explains TST-0100 probe2's environment-dependence)
"""
import hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_reviewer-w3s19-r3"
UNITS = ["TST-0081", "TST-0085", "TST-0088", "TST-0090", "TST-0091", "TST-0092",
         "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116", "TST-0124"]


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha_norm(p):
    raw = p.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(), len(raw), len(raw.replace(b"\r\n", b"\n"))


def sha_raw(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------- instrument F1: own jsonschema chain ----------
import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_TAIL = re.compile(r"(platform/schema/|command-center/schema/)([^#]+)")


def _retrieve(uri):
    m = SCHEMA_TAIL.search(uri.replace("\\", "/"))
    if not m:
        raise RuntimeError("unmapped ref uri: " + uri)
    fp = REPO / m.group(1) / m.group(2)
    return Resource.from_contents(json.loads(fp.read_text(encoding="utf-8")), default_specification=DRAFT202012)


REG = Registry(retrieve=_retrieve)
DEF_PTR = re.compile(r"([^#]+)#[/]?\$defs/(.+)$")


def own_chain_errors(instance, shim_ref):
    shim = load_json(REPO / shim_ref)
    ptr = shim.get("x-physical-definition") or shim.get("$ref") or ""
    m = DEF_PTR.match(ptr)
    if not m:
        raise RuntimeError("no physical pointer on shim " + shim_ref)
    phys_rel, cls = m.group(1), m.group(2)
    mm = SCHEMA_TAIL.search(phys_rel.replace("\\", "/"))
    phys_path = REPO / mm.group(1) / mm.group(2)
    phys = load_json(phys_path)
    sub = phys["$defs"][cls]
    rid = phys.get("$id") or ("file:///" + str(phys_path).replace("\\", "/"))
    reg = REG.with_resource(rid, Resource.from_contents(phys, default_specification=DRAFT202012))
    v = jsonschema.Draft202012Validator(sub, registry=reg)
    return [str(e.json_path) + ": " + e.message for e in sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))]


# ---------- instrument F2: blessed resolver ----------
RESOLVER_SNIPPET = (
    "import json, sys\n"
    "sys.path.insert(0, r'C:/Users/Prekzursil/p2-g1/platform/lib')\n"
    "import schema_resolver as sr\n"
    "doc = json.load(sys.stdin)\n"
    "errs = sr.validate_artifact(doc, sys.argv[1])\n"
    "print(json.dumps(errs))\n"
)


def blessed_errors(instance, ref):
    r = subprocess.run([sys.executable, "-I", "-c", RESOLVER_SNIPPET, ref],
                       input=json.dumps(instance), capture_output=True, text=True,
                       timeout=180, cwd=str(REPO))
    if r.returncode != 0:
        return ["resolver-crash: " + (r.stderr or "")[-400:]]
    return json.loads(r.stdout)


# ---------- positive control: known-clean receipts must validate 0/0 ----------
def positive_control(cat_by_id):
    ctrl = {}
    for uid in ("ADV-0005", "ADV-0010", "ADV-0037"):
        e = cat_by_id.get(uid)
        if not e:
            ctrl[uid] = "no-catalog-entry"
            continue
        ap = REPO / e["output_path"]
        if not ap.is_file():
            ctrl[uid] = "artifact-missing"
            continue
        doc = load_json(ap)
        try:
            n1 = len(own_chain_errors(doc, e["output_schema"]))
        except Exception as ex:
            ctrl[uid] = "own-chain-crash:" + str(ex)[:100]
            continue
        n2 = len(blessed_errors(doc, e["output_schema"]))
        ctrl[uid] = {"own": n1, "resolver": n2}
    return ctrl


def probe_commands(uid):
    """Named probe commands: PROBE-CMDS.json, else SUBAGENT-RETURN named_probes,
    else manifest probe rows in the program's canonical env-prefix form."""
    pdir = REPO / "command-center/p2-wave/probes" / uid
    pc = pdir / "PROBE-CMDS.json"
    if pc.is_file():
        return load_json(pc), "PROBE-CMDS.json"
    srj = pdir / "SUBAGENT-RETURN.json"
    if srj.is_file():
        doc = load_json(srj)
        cmds = [p.get("command") for p in (doc.get("named_probes") or []) if p.get("command")]
        if cmds:
            return cmds, "SUBAGENT-RETURN.json"
    man = load_json(pdir / "UNIT-ARTIFACT-MANIFEST.json")
    cmds = []
    for a in man.get("artifacts", []):
        rp = a.get("path", "").replace("\\", "/")
        if re.search(r"/probe\d+.*\.py$", rp):
            cmds.append("PYTHONDONTWRITEBYTECODE=1 python3 -B " + rp)
    return cmds, "manifest-rows"


def main():
    cat = load_json(REPO / "command-center/WORK-UNIT-CATALOG.json")
    wu = {u["id"]: u for u in cat["work_units"]}

    # environment transport note (interprets probe rc in THIS run's env)
    which_pwsh = subprocess.run(["bash", "-c", "command -v pwsh; command -v powershell; echo PATH=$PATH"],
                                capture_output=True, text=True, timeout=30, cwd=str(REPO))
    env_note = {"bash_which_pwsh": None, "bash_which_powershell": None,
                "path_has_powershell7_dir": "PowerShell" in (which_pwsh.stdout or "")}
    for line in (which_pwsh.stdout or "").splitlines():
        if line.startswith("PATH="):
            continue
        if line.endswith("pwsh") and env_note["bash_which_pwsh"] is None:
            env_note["bash_which_pwsh"] = line
        elif line.endswith("powershell") and env_note["bash_which_powershell"] is None:
            env_note["bash_which_powershell"] = line

    # receipts-before hash map (prove untouched at the end)
    receipts_before = {}
    for uid in UNITS:
        ap = REPO / wu[uid]["output_path"]
        receipts_before[uid] = sha_raw(ap) if ap.is_file() else None

    ctrl = positive_control(wu)
    print("POSITIVE-CONTROL:", json.dumps(ctrl), flush=True)
    print("ENV-NOTE:", json.dumps(env_note), flush=True)

    results = {}
    order = []
    for uid in UNITS:
        t0 = time.time()
        info = {"unit": uid, "fails": [], "notes": []}
        order.append(uid)
        entry = wu.get(uid)
        if not entry:
            info["fails"].append("catalog: entry missing")
            results[uid] = info
            print("[" + uid + "] FAIL catalog-missing", flush=True)
            continue
        op, osch = entry["output_path"], entry["output_schema"]
        sentinel = entry.get("completion_sentinel", "")
        info["output_path"] = op
        info["output_schema"] = osch
        ap = REPO / op
        if not ap.is_file():
            info["fails"].append("artifact-missing:" + op)
            results[uid] = info
            continue
        if ap.stat().st_size == 0:
            info["fails"].append("artifact-empty")
        try:
            doc = load_json(ap)
        except Exception as e:
            info["fails"].append("artifact-unparseable:" + str(e)[:120])
            results[uid] = info
            continue
        selfblock = None
        for fld in ("state", "status", "verdict", "result", "disposition"):
            v = str(doc.get(fld) or "").upper()
            if v in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT"):
                selfblock = fld + "=" + v
                break
        if selfblock:
            info["fails"].append("self-declared-" + selfblock)
        info["receipt_state"] = doc.get("state")
        rv0 = doc.get("reviewer") or {}
        info["pre_reviewer"] = {k: rv0.get(k) for k in ("reviewer_id", "verdict", "independent")}
        if sentinel and sentinel not in ap.read_text(encoding="utf-8", errors="replace"):
            info["fails"].append("completion_sentinel-absent:" + sentinel)
        # probes (bash transport)
        pdir = REPO / "command-center/p2-wave/probes" / uid
        cmds, src = probe_commands(uid)
        info["probe_source"] = src + ":" + str(len(cmds))
        runs = []
        if not cmds:
            info["fails"].append("no-named-probes-found")
        else:
            for cmd in cmds:
                t1 = time.time()
                try:
                    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True,
                                       timeout=900, cwd=str(REPO))
                    rc, tail = r.returncode, (r.stdout or "") + (r.stderr or "")
                except subprocess.TimeoutExpired:
                    rc, tail = 124, "TIMEOUT-900s"
                runs.append({"cmd": cmd, "rc": rc, "secs": round(time.time() - t1, 1)})
                if rc != 0:
                    info["fails"].append("probe-rc" + str(rc) + ":" + cmd[-70:] + " :: " + tail[-240:].replace("\n", " | "))
            for pf in sorted(pdir.glob("probe*.py")):
                txt = pf.read_text(encoding="utf-8", errors="replace")
                if uid not in txt and op not in txt and "receipt" not in txt:
                    info["fails"].append("probe-vacuous:" + pf.name)
        info["probe_runs"] = runs
        # manifest rows
        man_p = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_p.is_file():
            info["fails"].append("manifest-missing")
            info["manifest_rows"] = 0
        else:
            try:
                man = load_json(man_p)
                rows = man.get("artifacts", [])
                info["manifest_rows"] = len(rows)
                for a in rows:
                    rp = a.get("path", "").replace("\\", "/")
                    fp = REPO / rp
                    if not fp.is_file():
                        info["fails"].append("manifest-row-missing:" + rp)
                        continue
                    h, rawlen, normlen = sha_norm(fp)
                    if h != a.get("sha256"):
                        info["fails"].append("manifest-sha-mismatch:" + rp + " live=" + h[:12] + " row=" + str(a.get("sha256"))[:12])
                    declared = a.get("bytes")
                    if declared is not None and declared not in (rawlen, normlen):
                        info["fails"].append("manifest-bytes-mismatch:" + rp + " raw=" + str(rawlen) + " norm=" + str(normlen) + " row=" + str(declared))
                    if rp == op.replace("\\", "/"):
                        info["primary_row_ok"] = (h == a.get("sha256"))
            except Exception as e:
                info["fails"].append("manifest-unparseable:" + str(e)[:120])
        # schema both instruments
        try:
            e1 = own_chain_errors(doc, osch)
        except Exception as e:
            e1 = ["own-chain-crash:" + str(e)[:200]]
        e2 = blessed_errors(doc, osch)
        info["schema_errors_own_chain"] = len(e1)
        info["schema_errors_resolver"] = len(e2)
        info["schema_first_own"] = e1[:5]
        info["schema_first_resolver"] = e2[:5]
        if e1:
            info["fails"].append("schema-own-chain:" + str(len(e1)) + " errors, first: " + e1[0][:140])
        if e2:
            info["fails"].append("schema-resolver:" + str(len(e2)) + " errors, first: " + e2[0][:140])
        info["verdict"] = "PASS" if not info["fails"] else "FAIL"
        info["secs"] = round(time.time() - t0, 1)
        results[uid] = info
        print("[" + uid + "] " + info["verdict"] + " own=" + str(len(e1)) + " res=" + str(len(e2))
              + " probes_rc0=" + str(sum(1 for x in runs if x["rc"] == 0)) + "/" + str(len(runs))
              + " fails=" + str(len(info["fails"])) + " (" + str(info["secs"]) + "s)", flush=True)

    # receipts-after proof
    receipts_after = {}
    untouched = True
    for uid in UNITS:
        ap = REPO / wu[uid]["output_path"]
        h2 = sha_raw(ap) if ap.is_file() else None
        receipts_after[uid] = h2
        if h2 != receipts_before[uid]:
            untouched = False
    summary = {
        "reviewer_id": "claude-opus-5-5-independent-reviewer-w3s19-r3-2026-10-26",
        "wave": "wave3", "shard": 19, "round": "r3",
        "units_total": len(UNITS),
        "positive_control": ctrl,
        "env_note": env_note,
        "receipts_untouched_by_reviewer": untouched,
        "receipt_sha256_after": receipts_after,
        "order": order, "results": results,
        "pass_count": sum(1 for r in results.values() if r["verdict"] == "PASS"),
    }
    (OUT / "results_r3.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("RECEIPTS-UNTOUCHED:", str(untouched), flush=True)
    print("DONE: " + str(summary["pass_count"]) + "/" + str(len(UNITS)) + " PASS", flush=True)


if __name__ == "__main__":
    main()
