#!/usr/bin/env python3
"""Wave-3 shard-9 (review:w3s9) INDEPENDENT REVIEWER battery - 12 units.

Units (from the live workflow journal wf_a81de287-702, review:w3s9 = awaitIds[108:120]):
  IMP-0022 IMP-0031 IMP-0035 IMP-0036 IMP-0037 IMP-0038
  IMP-0041 IMP-0044 IMP-0051 IMP-0068 IMP-0070 IMP-0084

Contract checks per unit (fail-closed; ANY failure => unit FAIL):
  A. artifact at catalog output_path: exists, non-empty, parses JSON,
     not self-declared BLOCKED/FAILED (state==SUCCESS)
  B. probes/<id>/UNIT-ARTIFACT-MANIFEST.json row for the output_path:
     sha256(live bytes, CRLF->LF normalized) == row sha256 (raw also recorded)
  C. live probes re-run BY THE REVIEWER: every recorded receipt probe command
     that is mechanically runnable + every probe script in the probes dir
     (+ recorded extras) exits 0; catalog tests_required .py files via pytest
  D. output_schema: estate-canonical platform/lib/schema_resolver.validate_artifact
     (composite "A + B" aware) + raw whole-doc draft-2020-12 against the declared
     shim with foreign file:// refs redirected onto THIS checkout;
     secondary declared schema validated against its located document where one exists
  E. closure predicate: receipt reviewer.verdict==PASS and reviewer.independent==True
     (receipt_core forbids state=SUCCESS without both)

This script NEVER writes receipts or manifests. Read-only over the estate tree.
Output: _reviewer-w3s9/battery_out.json + SUCCESS:/FAILED: lines on stdout.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CC = REPO / "command-center"
PROBES_ROOT = CC / "p2-wave" / "probes"
OUT = Path(__file__).resolve().parent / "battery_out.json"
PROBE_TIMEOUT = 600

UNITS = [
    "IMP-0022", "IMP-0031", "IMP-0035", "IMP-0036", "IMP-0037", "IMP-0038",
    "IMP-0041", "IMP-0044", "IMP-0051", "IMP-0068", "IMP-0070", "IMP-0084",
]

# Recorded receipt probes that are extra named scripts (not probe*.py prefix)
EXTRA_SCRIPTS = {
    "IMP-0038": ["scenario.py"],
    "IMP-0051": ["negative_control.py", "run_required_tests.py"],
}
# Writer scripts that must never be executed by a reviewer
WRITER_NAMES = {"emit_receipt.py", "write_receipts.py"}

RUNNABLE_RE = re.compile(
    r"^\s*(?:[A-Z_][A-Z0-9_]*=\S+\s+)*(?:python3?|node)\b"
)


def norm_sha256(path: Path) -> tuple[str, str, int]:
    b = path.read_bytes()
    n = len(b)
    return (
        hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest(),
        hashlib.sha256(b).hexdigest(),
        n,
    )


def run_cmd(cmd: str) -> dict:
    import os  # noqa: PLC0415
    t0 = time.time()
    try:
        p = subprocess.run(
            ["bash", "-c", cmd],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PROBE_TIMEOUT,
            env=dict(os.environ),
        )
        return {
            "cmd": cmd,
            "exit": p.returncode,
            "stdout_tail": (p.stdout or "")[-500:],
            "stderr_tail": (p.stderr or "")[-300:],
            "seconds": round(time.time() - t0, 1),
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": "TIMEOUT", "stdout_tail": "", "stderr_tail": "",
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"cmd": cmd, "exit": "SPAWN-ERROR", "error": str(e),
                "stdout_tail": "", "stderr_tail": "", "seconds": 0.0}


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------- schema instruments ---------------- #

def canonical_schema_errors(doc, declared: str) -> dict:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver  # noqa: PLC0415
    try:
        errs = schema_resolver.validate_artifact(doc, declared)
        return {"ok": not errs, "errors": errs[:6], "n": len(errs)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "errors": [f"resolver exception: {e}"], "n": 1}


FOREIGN = "file:///C:/Users/Prekzursil/source/ast-integrate/"


def raw_schema_errors(doc, declared: str) -> dict:
    """Precedent instrument: whole-doc draft-2020-12 against the declared shim,
    foreign file:// refs redirected onto THIS checkout. Composite-aware: head part."""
    try:
        import warnings  # noqa: PLC0415
        warnings.simplefilter("ignore")
        from referencing import Registry, Resource  # noqa: PLC0415
        import jsonschema  # noqa: PLC0415

        head = (declared or "").split(" profile=")[0].split(" + ")[0].split(" (")[0].strip()

        def _retrieve(uri: str):
            if uri.startswith(FOREIGN):
                local = REPO / uri[len(FOREIGN):]
            elif uri.startswith("file:///"):
                local = Path(uri[len("file:///"):])
            else:
                raise FileNotFoundError(uri)
            return Resource.from_contents(json.loads(local.read_text(encoding="utf-8")))

        schema = load_json(REPO / head)
        reg = Registry(retrieve=_retrieve)
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        validator = cls(schema, registry=reg)
        errs = sorted(validator.iter_errors(doc), key=lambda e: [str(x) for x in e.absolute_path])
        firsts = "; ".join(
            "$" + "/".join(map(str, e.absolute_path))[:60] + ": " + e.message[:110]
            for e in errs[:3]
        )
        return {"ok": not errs, "n": len(errs), "first": firsts, "head": head}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "n": 1, "first": f"raw validator exception: {e}", "head": declared}


def secondary_schema_check(unit: dict, receipt: dict) -> dict:
    """For composite 'A + B' declarations: validate the located secondary doc."""
    declared = unit.get("output_schema") or ""
    if " + " not in declared:
        return {"composite": False}
    second = declared.split(" + ", 1)[1].split(" profile=")[0].split(" (")[0].strip()
    out = {"composite": True, "secondary_schema": second, "validated": []}
    candidates: list[Path] = []
    uid = unit["id"]
    # named documents in the probes dir
    name_by_schema = {
        "divergence-decision.schema.json": ["packets.json"],
        "error-taxonomy.schema.json": ["taxonomy-document.json"],
        "probe-control.schema.json": ["probe-control-document.json"],
        "lockfile.schema.json": ["lockfile-document.json"],
    }
    base = second.replace("\\", "/").split("/")[-1]
    for cand in name_by_schema.get(base, []):
        p = PROBES_ROOT / uid / cand
        if p.is_file():
            candidates.append(p)
    if not candidates:
        out["note"] = "no located secondary document in probes dir; receipt part is the contract artifact"
        return out
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver  # noqa: PLC0415
    for p in candidates:
        try:
            doc = load_json(p)
            errs = schema_resolver.validate_artifact(doc, second)
            out["validated"].append({"doc": p.name, "ok": not errs, "errors": errs[:4]})
        except Exception as e:  # noqa: BLE001
            out["validated"].append({"doc": p.name, "ok": False, "errors": [f"exception: {e}"]})
    return out


# ---------------- probe collection ---------------- #

def collect_probes(uid: str, receipt: dict, unit: dict) -> tuple[list[str], list[str]]:
    """Return (runnable_commands, skipped_prose)."""
    cmds: list[str] = []
    prose: list[str] = []
    seen: set[str] = set()

    def add(c: str):
        c = c.strip()
        if not c or c in seen:
            return
        seen.add(c)
        if RUNNABLE_RE.match(c):
            cmds.append(c)
        else:
            prose.append(c)

    # 1. recorded receipt probe commands
    for ev in receipt.get("evidence", []):
        for pr in (ev.get("probes") or []):
            c = pr.get("command")
            if isinstance(c, str):
                add(c)
    # 2. probe scripts in the probes dir (probe*.py) + recorded extras, never writers
    pdir = PROBES_ROOT / uid
    if pdir.is_dir():
        for f in sorted(pdir.iterdir()):
            n = f.name
            if n in WRITER_NAMES or not n.endswith(".py"):
                continue
            rel = f.relative_to(REPO).as_posix()
            if n.startswith("probe") or n in EXTRA_SCRIPTS.get(uid, []):
                add(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}")
    # 3. catalog tests_required (*.py entries) via pytest
    for t in unit.get("tests_required") or []:
        if isinstance(t, str) and ".py" in t:
            path = t.split("::")[0].strip()
            if (REPO / path).is_file():
                add(f"python3 -m pytest -q {path}")
            else:
                prose.append(f"tests_required MISSING FILE: {t}")
        elif isinstance(t, str):
            prose.append(f"tests_required (non-file): {t}")
    return cmds, prose


# ---------------- per-unit battery ---------------- #

def review_unit(uid: str, unit: dict) -> dict:
    res: dict = {"unit_id": uid, "checks": {}, "probe_results": []}
    out_path = REPO / unit["output_path"]
    declared_schema = unit.get("output_schema")

    # A. artifact
    a = {"exists": out_path.is_file()}
    if a["exists"]:
        raw = out_path.read_bytes()
        a["bytes"] = len(raw)
        a["nonempty"] = len(raw) > 0
        try:
            doc = load_json(out_path)
            a["parses"] = True
        except Exception as e:  # noqa: BLE001
            doc = None
            a["parses"] = False
            a["parse_error"] = str(e)[:200]
        if doc is not None:
            a["state"] = doc.get("state")
            a["self_blocked"] = doc.get("state") in ("BLOCKED", "FAILED")
    res["checks"]["artifact_ok"] = bool(
        a.get("exists") and a.get("nonempty") and a.get("parses") and not a.get("self_blocked")
    )
    res["artifact"] = a
    if doc is None:
        res["verdict"] = "FAIL"
        res["failing_check"] = "artifact missing/unparseable at catalog output_path"
        return res

    # B. manifest sha
    m = {}
    mpath = PROBES_ROOT / uid / "UNIT-ARTIFACT-MANIFEST.json"
    m["manifest_exists"] = mpath.is_file()
    if m["manifest_exists"]:
        try:
            man = load_json(mpath)
            rows = man.get("artifacts") or []
            op_posix = out_path.relative_to(REPO).as_posix()
            row = next((r for r in rows if isinstance(r, dict) and r.get("path") == op_posix), None)
            if row is None:  # older shapes: row-level unit_id
                row = next((r for r in rows if isinstance(r, dict) and r.get("unit_id") == uid), None)
                m["row_match_mode"] = "unit_id-row" if row else "NONE"
            else:
                m["row_match_mode"] = "output_path-row"
            if row:
                lf_sha, raw_sha, n = norm_sha256(out_path)
                m["row_sha256"] = row.get("sha256")
                m["live_lf_sha256"] = lf_sha
                m["live_raw_sha256"] = raw_sha
                m["live_bytes"] = n
                m["row_bytes"] = row.get("bytes")
                m["sha_match_LF"] = row.get("sha256") == lf_sha
                m["sha_match_RAW"] = row.get("sha256") == raw_sha
            else:
                m["error"] = "no manifest row for the output_path artifact"
        except Exception as e:  # noqa: BLE001
            m["error"] = f"manifest parse error: {e}"
    res["manifest"] = m
    res["checks"]["manifest_sha_row_matches"] = bool(m.get("sha_match_LF"))

    # C. live probes
    cmds, prose = collect_probes(uid, doc, unit)
    res["skipped_prose"] = prose
    probe_fail = []
    for c in cmds:
        r = run_cmd(c)
        res["probe_results"].append(r)
        # exit 0 required; non-empty stdout guard against no-op-green probes
        # (pytest -q prints a summary on pass, so it is exempt from the guard)
        if r["exit"] != 0:
            probe_fail.append(c)
        elif r.get("stdout_tail", "").strip() == "" and "pytest" not in c:
            probe_fail.append(c + "  [EMPTY-STDOUT no-op-green guard]")
    res["checks"]["probes_rerun_exit0"] = not probe_fail
    res["probe_failures"] = probe_fail
    res["n_probes_run"] = len(cmds)

    # D. schema
    d = {"declared": declared_schema}
    d["canonical"] = canonical_schema_errors(doc, declared_schema)
    d["raw"] = raw_schema_errors(doc, declared_schema)
    d["secondary"] = secondary_schema_check(unit, doc)
    sec_ok = True
    if d["secondary"].get("composite"):
        vals = d["secondary"].get("validated") or []
        sec_ok = all(v.get("ok") for v in vals) if vals else True  # no located doc -> receipt part is the artifact
    res["schema"] = d
    res["checks"]["output_schema_validates"] = bool(
        d["canonical"]["ok"] and d["raw"]["ok"] and sec_ok
    )

    # E. closure predicate
    rv = doc.get("reviewer") or {}
    res["reviewer_block"] = {
        "verdict": rv.get("verdict"),
        "independent": rv.get("independent"),
        "reviewer_id": rv.get("reviewer_id"),
    }
    res["checks"]["closure_pass_independent"] = bool(
        rv.get("verdict") == "PASS" and rv.get("independent") is True
    )

    # final
    all_hold = all(res["checks"].values())
    res["verdict"] = "CONFIRMED-PASS" if all_hold else "FAIL"
    if not all_hold:
        failed = [k for k, v in res["checks"].items() if not v]
        res["failing_check"] = ", ".join(failed)
    return res


def main() -> int:
    cat = load_json(CC / "WORK-UNIT-CATALOG.json")
    byid = {u["id"]: u for u in cat["work_units"]}
    results = []
    for uid in UNITS:
        unit = byid.get(uid)
        if unit is None:
            results.append({"unit_id": uid, "verdict": "FAIL",
                            "failing_check": "no catalog entry"})
            continue
        t0 = time.time()
        r = review_unit(uid, unit)
        r["review_seconds"] = round(time.time() - t0, 1)
        results.append(r)
        mark = "SUCCESS" if r["verdict"] == "CONFIRMED-PASS" else "FAILED"
        print(f"{mark}:{uid} [{r['verdict']}] failing={r.get('failing_check','-')} "
              f"probes={r.get('n_probes_run')} schema_canon_ok={r.get('schema',{}).get('canonical',{}).get('ok')} "
              f"({r['review_seconds']}s)", flush=True)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    n_pass = sum(1 for r in results if r["verdict"] == "CONFIRMED-PASS")
    print(f"SUMMARY {n_pass}/{len(results)} CONFIRMED-PASS; detail -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
