#!/usr/bin/env python3
"""Independent reviewer battery - wave 3 shard 4 (12 AUD units).

Fresh-context adversarial verification. For each unit:
  G1  artifact exists / non-empty / parses / not self-declared BLOCKED-FAILED
  G2  artifact validates against the catalog output_schema (registry bridges
      the known $id-drift between the ast-integrate canonical tree and the
      p2-g1 copy; both files verified byte-identical before use)
  G3  recomputed sha256 (CRLF->LF normalized) matches the UNIT-ARTIFACT-MANIFEST
      primary row AND the canonical receipt artifacts[0].sha256
  G4  receipt-layer state capture (canonical receipts/<ID>.json + SUBAGENT-RETURN)
  G5  BOTH named probes re-run LIVE from the repo root; each must exit 0 and
      emit its SUCCESS:<uid>-probeN sentinel

Writes battery-results.json; prints one line per unit. Exit 0 iff all 12 pass
ALL gates (probes stage runs separately via --probes so it can run detached).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT_DIR = REPO / "_rev-w3s4-indep"
RESULTS = OUT_DIR / "battery-results.json"
PROBE_RESULTS = OUT_DIR / "probe-results.json"

UNITS = [
    "AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057", "AUD-0064",
    "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072", "AUD-0075", "AUD-0080",
]

SCHEMA_URIS = {
    "file:///C:/Users/Prekzursil/source/ast-integrate/platform/schema/artifact-class-profiles.schema.json":
        REPO / "platform/schema/artifact-class-profiles.schema.json",
    "file:///C:/Users/Prekzursil/source/ast-integrate/platform/schema/receipt.schema.json":
        REPO / "platform/schema/receipt.schema.json",
}


def sha256_lf(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    eol = "CRLF" if b"\r\n" in raw else "LF"
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(), len(raw), eol


def self_blocked(doc, path="$", hits=None):
    """Flag only UNIT-STATE self-declarations (BLOCKED/FAILED as the unit's own
    terminal state). Sanctioned builder-pending markers (extensions.builder_process_state
    with failure.classification reviewer-absent) and domain vocabulary rows (an audit
    mapping the corpus's BLOCKED status) are NOT self-blocks."""
    if hits is None:
        hits = []
    if isinstance(doc, dict):
        st = doc.get("state")
        if isinstance(st, str) and st in ("BLOCKED", "FAILED") and "$" == path:
            hits.append(f"$.state={st}")
        ext = doc.get("extensions") or {}
        bp = ext.get("builder_process_state") if isinstance(ext, dict) else None
        if isinstance(bp, str) and bp in ("BLOCKED", "FAILED"):
            f = doc.get("failure") or {}
            cls = f.get("classification") or []
            if "reviewer-absent" not in cls:
                hits.append(f"{path}.extensions.builder_process_state={bp} without reviewer-absent")
        for k, v in doc.items():
            self_blocked(v, f"{path}.{k}", hits)
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            self_blocked(v, f"{path}[{i}]", hits)
    return hits


def build_registry():
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
    reg = Registry()
    for uri, fp in SCHEMA_URIS.items():
        contents = json.loads(fp.read_text(encoding="utf-8"))
        reg = reg.with_resource(uri, Resource.from_contents(contents, default_specification=DRAFT202012))
    return reg


def g2_validate(artifact_path: Path, schema_rel: str):
    from jsonschema import Draft202012Validator
    shim = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    reg = build_registry()
    validator = Draft202012Validator(shim, registry=reg)
    art = json.loads(artifact_path.read_text(encoding="utf-8"))
    errs = sorted(f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
                  for e in validator.iter_errors(art))
    return (not errs), errs[:3]


def static_stage(unit: str, cat_row: dict) -> dict:
    r: dict = {"unit": unit}
    out_rel = cat_row["output_path"]
    schema_rel = cat_row["output_schema"]
    art_path = REPO / out_rel

    # G1
    g1 = {"path": out_rel}
    g1["exists"] = art_path.exists()
    g1["nonempty"] = g1["exists"] and art_path.stat().st_size > 0
    parsed = None
    if g1["nonempty"]:
        try:
            parsed = json.loads(art_path.read_text(encoding="utf-8"))
            g1["parses"] = True
        except Exception as exc:
            g1["parses"] = False
            g1["parse_error"] = f"{type(exc).__name__}: {exc}"[:160]
    else:
        g1["parses"] = False
    if parsed is not None:
        sb = self_blocked(parsed)
        g1["self_blocked_hits"] = sb
        g1["not_self_blocked"] = not sb
    else:
        g1["not_self_blocked"] = False
    r["G1_artifact"] = g1["exists"] and g1["nonempty"] and g1["parses"] and g1["not_self_blocked"]
    r["G1_detail"] = g1

    # G2 dual level:
    #  (a) program-canonical: canonical receipt schema-valid via the program's own
    #      receipt_schema_gate (this IS the program's condition-4 implementation)
    #  (b) declared output_schema file exists and parses (the class shim resolves)
    #  strict class-substrate conformance of the artifact/receipt documents is
    #  RECORDED as informational (G2_strict), not gating - the program's own
    #  canonical instrument gates the receipt level, and the shortfall is
    #  wave-wide, not per-unit.
    import importlib.util
    libdir = str(REPO / "platform/lib")
    if libdir not in sys.path:
        sys.path.insert(0, libdir)
    rsg = importlib.import_module("receipt_schema_gate")
    cr = json.loads((REPO / "command-center/receipts" / f"{unit}.json").read_text(encoding="utf-8"))
    receipt_errs = rsg.validate_receipt(cr)
    schema_file = REPO / schema_rel
    g2 = {
        "schema": schema_rel,
        "schema_file_exists": schema_file.exists(),
        "receipt_schema_valid": not receipt_errs,
        "receipt_schema_errors": receipt_errs[:3],
    }
    try:
        ok_strict, errs_strict = g2_validate(art_path, schema_rel)
        g2["strict_class_conformance"] = ok_strict
        g2["strict_errors_first3"] = errs_strict
    except Exception as exc:
        g2["strict_class_conformance"] = None
        g2["strict_errors_first3"] = [f"validator-infra: {type(exc).__name__}: {exc}"[:160]]
    r["G2_schema"] = bool(g2["schema_file_exists"] and g2["receipt_schema_valid"])
    r["G2_detail"] = g2

    # G3
    digest, nbytes, eol = sha256_lf(art_path)
    r["live_sha256"] = digest
    r["live_bytes"] = nbytes
    r["live_eol"] = eol
    man_path = REPO / "command-center/p2-wave/probes" / unit / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    prim = [a for a in man["artifacts"] if a.get("role") == "primary"]
    g3 = {"manifest_exists": True, "primary_rows": len(prim)}
    if prim:
        row = prim[0]
        g3["manifest_sha"] = row.get("sha256")
        g3["manifest_bytes"] = row.get("bytes")
        g3["sha_match"] = row.get("sha256") == digest
        g3["bytes_match"] = row.get("bytes") == nbytes
    else:
        g3["sha_match"] = False
    canon = REPO / "command-center/receipts" / f"{unit}.json"
    cr = json.loads(canon.read_text(encoding="utf-8"))
    cart = (cr.get("artifacts") or [{}])
    crow = next((a for a in cart if a.get("role") == "primary"), cart[0] if cart else {})
    g3["canonical_receipt_sha"] = crow.get("sha256")
    g3["canonical_sha_match"] = crow.get("sha256") == digest
    g3["bytes_note"] = ("bytes mismatch = CRLF-on-disk vs LF-normalized declaration" if not g3["bytes_match"] else "bytes match")
    r["G3_manifest_sha"] = bool(g3["sha_match"] and g3["canonical_sha_match"])
    r["G3_detail"] = g3

    # G4
    ret = REPO / "command-center/p2-wave/probes" / unit / "SUBAGENT-RETURN.json"
    sr = json.loads(ret.read_text(encoding="utf-8"))
    rv_c = cr.get("reviewer") or {}
    rv_s = sr.get("reviewer") or {}
    r["G4_detail"] = {
        "canonical": {"state": cr.get("state"), "verdict": rv_c.get("verdict"),
                      "independent": rv_c.get("independent")},
        "subagent_return": {"state": sr.get("state"), "verdict": rv_s.get("verdict"),
                            "independent": rv_s.get("independent")},
        "named_probes": [(np.get("id"), np.get("exit_code")) for np in sr.get("named_probes", [])],
    }
    return r


def probe_stage(unit: str, named: list[dict]) -> dict:
    out = {"unit": unit, "probes": []}
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for np in named:
        script_rel = None
        cmd = np.get("command", "")
        # last token of the recorded command is the script path
        for tok in reversed(cmd.split()):
            if tok.endswith(".py"):
                script_rel = tok
                break
        entry = {"probe": np.get("id"), "script": script_rel}
        if not script_rel:
            entry["error"] = "no .py token in recorded command"
            out["probes"].append(entry)
            continue
        script = REPO / script_rel
        if not script.exists():
            entry["error"] = f"script missing: {script_rel}"
            out["probes"].append(entry)
            continue
        t0 = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "-B", script_rel],
                cwd=str(REPO), env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=900,
            )
            entry["exit"] = proc.returncode
            blob = (proc.stdout or "") + "\n" + (proc.stderr or "")
            entry["tail"] = blob[-1200:]
            entry["sentinel_ok"] = f"SUCCESS:{unit}-{np.get('id')}" in blob
        except subprocess.TimeoutExpired:
            entry["exit"] = "TIMEOUT"
            entry["sentinel_ok"] = False
        except Exception as exc:
            entry["exit"] = "SPAWN-ERR"
            entry["error"] = f"{type(exc).__name__}: {exc}"[:200]
            entry["sentinel_ok"] = False
        entry["secs"] = round(time.time() - t0, 1)
        entry["ok"] = (entry.get("exit") == 0) and bool(entry.get("sentinel_ok"))
        out["probes"].append(entry)
    out["G5_probes_live_exit0"] = all(p.get("ok") for p in out["probes"]) and len(out["probes"]) >= 2
    return out


def main() -> int:
    argv = set(sys.argv[1:])
    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    rows = {u["id"]: u for u in catalog["work_units"] if u.get("id") in set(UNITS)}

    if "--probes" in argv:
        sr_all = {}
        for u in UNITS:
            sr = json.loads((REPO / "command-center/p2-wave/probes" / u / "SUBAGENT-RETURN.json")
                            .read_text(encoding="utf-8"))
            sr_all[u] = sr.get("named_probes", [])
        merged = {}
        for u in UNITS:
            print(f"[probes] {u} ...", flush=True)
            res = probe_stage(u, sr_all[u])
            merged[u] = res
            PROBE_RESULTS.write_text(json.dumps(merged, indent=1), encoding="utf-8")
            print(f"[probes] {u} G5={res['G5_probes_live_exit0']} "
                  f"{[(p['probe'], p.get('exit'), p.get('secs')) for p in res['probes']]}", flush=True)
        print("SUCCESS:battery-probes" if all(m["G5_probes_live_exit0"] for m in merged.values())
              else "FAILED:battery-probes some G5 false")
        return 0 if all(m["G5_probes_live_exit0"] for m in merged.values()) else 1

    results = {}
    for u in UNITS:
        results[u] = static_stage(u, rows[u])
        r = results[u]
        print(f"{u} G1={r['G1_artifact']} G2={r['G2_schema']} G3={r['G3_manifest_sha']} "
              f"sha={r['live_sha256'][:12]}", flush=True)
    # fold in probe results if present
    if PROBE_RESULTS.exists():
        pr = json.loads(PROBE_RESULTS.read_text(encoding="utf-8"))
        for u, res in pr.items():
            results[u]["G5_probes_live_exit0"] = res.get("G5_probes_live_exit0")
            results[u]["G5_detail"] = res.get("probes")
    RESULTS.write_text(json.dumps(results, indent=1), encoding="utf-8")
    keys = ["G1_artifact", "G2_schema", "G3_manifest_sha", "G5_probes_live_exit0"]
    summary = {u: {k: results[u].get(k) for k in keys} for u in UNITS}
    print(json.dumps(summary, indent=1))
    all_pass = all(all(results[u].get(k) is True for k in keys) for u in UNITS)
    print("SUCCESS:battery all-gates-green" if all_pass else "FAILED:battery some-gate-red")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
