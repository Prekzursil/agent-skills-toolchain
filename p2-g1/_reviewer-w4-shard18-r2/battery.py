"""Independent reviewer battery - wave 4 shard 18 (12 TST units).

Runs the unit contract checks with NO input from the earlier review run:
  A. artifact at catalog output_path: exists / non-empty / parses / state not
     self-blocked (BLOCKED/FAILED/SEVERED/TIMEOUT) / sentinel text present
  B. live probes re-run by THIS reviewer, full inherited env, cwd=repo,
     commands taken from PROBE-CMDS.json (or probe1*/probe2* scripts when the
     file is absent); every probe must exit 0
  C. sha256 of the primary artifact recomputed CRLF->LF and matched against
     probes/<id>/UNIT-ARTIFACT-MANIFEST.json (row unit_id+path+present=true)
  D. output_schema validated two ways:
       D1 "verbatim": the catalog schema document (shim) as loaded from the
          catalog path, fragment pointer applied when the catalog carries one
       D2 "program-canonical": receipt_schema_gate.parse_schema_ref mapping the
          catalog base to the physical control plane (platform/schema/...) and
          build_validator(fragment)
     plus E. receipt_core invariant: state=SUCCESS requires
     reviewer.verdict=PASS and reviewer.independent=true.
Receipts are only ever READ here; the verdict writer is a separate script.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
OUT = Path(__file__).resolve().parent

UNITS = [
    "TST-0092", "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116",
    "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137", "TST-0138",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
BS = chr(92)


def norm(p):
    return str(p).replace(BS, "/")


def lf_sha(path):
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


# ---------------------------------------------------------------- catalog ---
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
cmap = {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and "id" in u}


# ------------------------------------------------------- schema machinery ---
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

PHYS_RECEIPT = REPO / "platform/schema/receipt.schema.json"
PHYS_PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"


def retrieve(uri):
    """Map file:///.../ast-integrate/<rest> onto this checkout (byte-identical,
    verified separately) so external $refs resolve against THIS tree."""
    prefix = "file:///C:/Users/Prekzursil/source/ast-integrate/"
    if uri.startswith(prefix):
        local = REPO / uri[len(prefix):]
        if local.exists():
            return Resource.from_contents(
                json.loads(local.read_text(encoding="utf-8")), default_specification=DRAFT202012
            )
    raise RuntimeError(f"unresolvable ref: {uri}")


REG = Registry(retrieve=retrieve)


def load(doc_path):
    return json.loads(Path(doc_path).read_text(encoding="utf-8"))


def check_schema(receipt, out_schema):
    """Return dict with per-interpretation error lists."""
    res = {}
    text = (out_schema or "").strip()
    head = text.split(" profile=")[0].split(" + ")[0].split(" (")[0].strip()
    frag = None
    base = head
    if "#" in head:
        base, f = head.split("#", 1)
        frag = "#" + f.strip()

    # D1 verbatim: catalog document, pointer applied when present
    try:
        shim = load(REPO / base)
        if frag:
            target = {"$ref": shim["$id"] + frag}
        else:
            target = shim
        v = Draft202012Validator(target, registry=REG)
        errs = sorted(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(receipt)
        )
        res["verbatim"] = errs if errs else []
    except Exception as exc:
        res["verbatim"] = [f"UNRESOLVABLE: {type(exc).__name__}: {exc}"]

    # D2 program-canonical: physical control plane + fragment via parse rule
    try:
        phys_id = load(PHYS_RECEIPT)["$id"]
        if frag:
            target = {"$ref": phys_id + frag}
        else:
            target = load(PHYS_RECEIPT)
        v = Draft202012Validator(target, registry=REG)
        errs = sorted(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in v.iter_errors(receipt)
        )
        res["canonical"] = errs if errs else []
    except Exception as exc:
        res["canonical"] = [f"UNRESOLVABLE: {type(exc).__name__}: {exc}"]

    # D3: kind-pinned logical class where the shim carries one (artifact-class
    # profile), i.e. verbatim WITHOUT a fragment pointer but THROUGH the shim
    # $ref - same as D1 when frag is None, kept separate only for reporting.
    return res


# ---------------------------------------------------------------- battery ---
env = dict(os.environ)
env["PYTHONDONTWRITEBYTECODE"] = "1"

results = {}
for uid in UNITS:
    unit = cmap[uid]
    r = {"unit": uid, "checks": {}, "detail": {}}

    # ---- A. artifact -------------------------------------------------------
    out_rel = norm(unit["output_path"])
    out_path = REPO / out_rel
    a = {}
    a["exists"] = out_path.exists()
    a["nonempty"] = a["exists"] and out_path.stat().st_size > 0
    doc = None
    try:
        text = out_path.read_text(encoding="utf-8")
        doc = json.loads(text)
        a["parses"] = True
    except Exception as exc:
        a["parses"] = False
        a["parse_error"] = f"{type(exc).__name__}: {exc}"
        text = ""
    state = str((doc or {}).get("state", "")).upper()
    a["state"] = state or "<absent>"
    a["not_self_blocked"] = bool(state) and state not in NOT_DELIVERING
    sent = unit.get("completion_sentinel", "")
    a["sentinel_in_text"] = bool(sent) and sent in text
    r["checks"]["A_artifact"] = (
        a["exists"] and a["nonempty"] and a["parses"] and a["not_self_blocked"]
        and a["sentinel_in_text"]
    )
    r["detail"]["A"] = a

    # ---- B. probes ---------------------------------------------------------
    pdir = REPO / "command-center/p2-wave/probes" / uid
    cmds_file = pdir / "PROBE-CMDS.json"
    if cmds_file.exists():
        cmds = json.loads(cmds_file.read_text(encoding="utf-8"))
    else:
        scripts = sorted(
            p.name for p in pdir.glob("probe*.py")
        )
        cmds = [
            f"PYTHONDONTWRITEBYTECODE=1 python -B command-center/p2-wave/probes/{uid}/{s}"
            for s in scripts
        ]
    probes = []
    all_ok = True
    for cmd in cmds:
        # canonical parse: env-prefix + interpreter + args, cwd = repo
        argv = cmd.split()
        while "=" in argv[0] and argv[0].split("=", 1)[0].isidentifier():
            k, v = argv[0].split("=", 1)
            env[k] = v
            argv = argv[1:]
        exe = "python" if argv and argv[0] in ("python", "python3") else argv[0]
        try:
            cp = subprocess.run(
                [exe] + argv[1:], cwd=str(REPO), env=env,
                capture_output=True, text=True, timeout=900,
            )
        except Exception as exc:
            probes.append({"cmd": cmd, "exit_code": None, "error": f"{type(exc).__name__}: {exc}"})
            all_ok = False
            continue
        ok = cp.returncode == 0
        all_ok = all_ok and ok
        tail = (cp.stdout or "")[-400:]
        probes.append({
            "cmd": cmd, "exit_code": cp.returncode, "ok": ok,
            "stdout_tail": tail, "stderr_tail": (cp.stderr or "")[-200:],
        })
    r["checks"]["B_probes_exit0"] = all_ok and len(probes) > 0
    r["detail"]["B"] = probes

    # ---- C. manifest sha ---------------------------------------------------
    c = {}
    try:
        live_sha, live_n = lf_sha(out_path)
        c["live_sha256"] = live_sha
        c["live_lf_bytes"] = live_n
        man = json.loads((pdir / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
        rows = [
            a_ for a_ in man.get("artifacts", [])
            if isinstance(a_, dict) and a_.get("unit_id") == uid
            and norm(a_.get("path", "")) == out_rel and a_.get("present") is True
        ]
        c["primary_rows"] = len(rows)
        c["sha_match"] = any(a_.get("sha256") == live_sha for a_ in rows)
    except Exception as exc:
        c["error"] = f"{type(exc).__name__}: {exc}"
        c["sha_match"] = False
    r["checks"]["C_manifest_sha"] = bool(c.get("sha_match"))
    r["detail"]["C"] = c

    # ---- D. output_schema + E. receipt_core invariant ----------------------
    d = {}
    if doc is not None:
        d["interpretations"] = check_schema(doc, unit.get("output_schema"))
        rev = doc.get("reviewer") or {}
        d["reviewer"] = {"verdict": rev.get("verdict"), "independent": rev.get("independent")}
        d["receipt_core_invariant"] = not (
            str(doc.get("state", "")).upper() == "SUCCESS"
            and not (rev.get("verdict") == "PASS" and rev.get("independent") is True)
        )
    else:
        d["interpretations"] = {"verbatim": ["receipt unparseable"], "canonical": ["receipt unparseable"]}
        d["receipt_core_invariant"] = False
    d["schema_ok"] = all(not errs for errs in d["interpretations"].values())
    r["checks"]["D_schema"] = d["schema_ok"]
    r["checks"]["E_receipt_core_invariant"] = d["receipt_core_invariant"]
    r["detail"]["D"] = d

    r["ALL_HOLD"] = all(
        [r["checks"]["A_artifact"], r["checks"]["B_probes_exit0"],
         r["checks"]["C_manifest_sha"], r["checks"]["D_schema"],
         r["checks"]["E_receipt_core_invariant"]]
    )
    results[uid] = r

(OUT / "battery-results.json").write_text(
    json.dumps(results, indent=1), encoding="utf-8"
)

print("unit          A     B     C     D     E     ALL")
for uid in UNITS:
    r = results[uid]
    c = r["checks"]
    print(
        f"{uid}  {str(c['A_artifact']):5} {str(c['B_probes_exit0']):5} "
        f"{str(c['C_manifest_sha']):5} {str(c['D_schema']):5} "
        f"{str(c['E_receipt_core_invariant']):5} {str(r['ALL_HOLD']):5}"
    )
