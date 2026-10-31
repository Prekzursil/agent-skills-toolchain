#!/usr/bin/env python3
"""INDEPENDENT REVIEWER wave-2 shard-1 verification (12 ADV units).

Reviewer-owned instrument. Reuses ONLY the canonical probe-runner helpers
(run_cmd / probe_commands) from _measure_one_delivered.py so the live probes
run under the declared invocation; every other check is computed here fresh:

  R1 catalog entry present with output_path/output_schema/dependencies
  R2 artifact at catalog output_path: exists, non-empty, >= receipt min bytes
  R3 artifact parses as JSON
  R4 artifact not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT (top-level state/status)
  R5 catalog completion_sentinel present in artifact text
  R6 output_schema file exists and artifact validates (jsonschema)
  R7 probes/<uid>/UNIT-ARTIFACT-MANIFEST.json parses, has a row for uid at
     output_path with present=true
  R8 live sha256 (CRLF->LF normalized) recomputed POST-probe == manifest row
     sha256, live bytes == row bytes
  R9 SUBAGENT-RETURN.json parses, status not in NOT_DELIVERING
  R10 named probes re-run live, each exit 0

Outputs _rev-w2-shard1/verify_out.json + a compact table. Exit 0 iff ALL units
pass all checks.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "ADV-0037", "ADV-0038", "ADV-0040", "ADV-0090", "ADV-0091", "ADV-0096",
    "ADV-0100", "ADV-0109", "ADV-0110", "ADV-0117", "ADV-0119", "ADV-0123",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBES_ROOT = REPO / "command-center" / "p2-wave" / "probes"

spec = importlib.util.spec_from_file_location(
    "measure_one", REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
)
M = importlib.util.module_from_spec(spec)
sys.modules["measure_one"] = M
spec.loader.exec_module(M)


def load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - reviewer wants the reason
        return exc


def norm_sha(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def schema_errors(art_doc, schema_path: Path) -> list[str]:
    try:
        import jsonschema

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        cls = jsonschema.validators.validator_for(schema)
        validator = cls(schema)
        return [
            f"{list(e.absolute_path)}: {e.message}" for e in validator.iter_errors(art_doc)
        ][:5]
    except Exception as exc:  # noqa: BLE001
        return [f"schema-instrument-error: {type(exc).__name__}: {exc}"]


def verify(uid: str, catalog: dict, wu_index: dict) -> dict:
    checks: dict[str, object] = {}
    ok = True

    def gate(name: str, passed: bool, detail=""):
        nonlocal ok
        checks[name] = {"pass": bool(passed), "detail": detail}
        if not passed:
            ok = False

    # R1 catalog
    cat = wu_index.get(uid)
    gate("R1-catalog-entry", cat is not None, "" if cat else "catalog entry missing")
    if cat is None:
        return {"uid": uid, "ok": False, "checks": checks}
    out_rel = str(cat.get("output_path") or "").replace("\\", "/")
    gate("R1-output_path", bool(out_rel), out_rel)
    schema_rel = str(cat.get("output_schema") or "").replace("\\", "/")
    gate("R1-output_schema", bool(schema_rel), schema_rel)
    deps = cat.get("dependencies") or []
    dep_states = {}
    for d in deps:
        rp = REPO / "command-center" / "receipts" / f"{d}.json"
        dep_doc = load_json(rp) if rp.is_file() else None
        dep_states[d] = (
            dep_doc.get("state") if isinstance(dep_doc, dict) else "RECEIPT-ABSENT"
        )
    bad_deps = {d: s for d, s in dep_states.items() if s in NOT_DELIVERING}
    gate("R1-dependencies", not bad_deps, json.dumps(dep_states))
    checks["dependencies"] = dep_states

    # R2/R3/R4/R5 artifact (pre-probe parse pass)
    art_path = REPO / out_rel if out_rel else REPO / "__none__"
    gate("R2-artifact-exists", art_path.is_file(), str(art_path))
    art_bytes = art_path.stat().st_size if art_path.is_file() else 0
    gate("R2-nonempty", art_bytes > 0, f"{art_bytes}B")
    rcp = REPO / "command-center" / "receipts" / f"{uid}.json"
    rec = load_json(rcp)
    gate("R2-receipt-parses", isinstance(rec, dict), f"state={rec.get('state') if isinstance(rec, dict) else type(rec).__name__}")
    min_b = rec.get("min_bytes_threshold") if isinstance(rec, dict) else None
    if isinstance(min_b, int) and min_b > 0:
        gate("R2-min-bytes", art_bytes >= min_b, f"{art_bytes} >= {min_b}")
    raw_text = art_path.read_text(encoding="utf-8") if art_path.is_file() else ""
    art_doc = load_json(art_path)
    gate("R3-artifact-parses", not isinstance(art_doc, Exception), "" if not isinstance(art_doc, Exception) else str(art_doc))
    st = ""
    if isinstance(art_doc, dict):
        st = str(art_doc.get("state") or art_doc.get("status") or "").upper()
    gate("R4-not-self-blocked", st not in NOT_DELIVERING, f"state={st!r}")
    sent = str(cat.get("completion_sentinel") or "")
    gate("R5-catalog-sentinel-in-artifact", (not sent) or (sent in raw_text), f"len(sent)={len(sent)}")

    # R6 schema
    schema_path = REPO / schema_rel if schema_rel else REPO / "__none__"
    gate("R6-schema-file-exists", schema_path.is_file(), schema_rel)
    if schema_path.is_file() and not isinstance(art_doc, Exception):
        errs = schema_errors(art_doc, schema_path)
        gate("R6-schema-valid", not errs, "; ".join(errs)[:300])

    # R9 subagent return
    ret_path = PROBES_ROOT / uid / "SUBAGENT-RETURN.json"
    ret = load_json(ret_path)
    gate("R9-return-parses", isinstance(ret, dict), str(type(ret).__name__))
    st_ret = str((ret or {}).get("status") or (ret or {}).get("state") or "").upper() if isinstance(ret, dict) else "?"
    gate("R9-return-not-blocked", st_ret not in NOT_DELIVERING, st_ret)

    # R10 live probes (canonical named-probe invocation)
    probe_dir = PROBES_ROOT / uid
    cmds = M.probe_commands(uid, ret if isinstance(ret, dict) else None, probe_dir)
    checks["probe_commands"] = cmds
    gate("R10-probes-declared", len(cmds) >= 1, f"{len(cmds)} commands")
    probe_results = []
    probes_ok = len(cmds) >= 1
    for i, cmd in enumerate(cmds, 1):
        t0 = time.time()
        try:
            code, tail = M.run_cmd(cmd)
        except Exception as exc:  # noqa: BLE001
            code, tail = -1, f"{type(exc).__name__}: {exc}"
        dt = round(time.time() - t0, 1)
        probe_results.append({"i": i, "cmd": cmd, "rc": code, "secs": dt, "tail": tail[-400:]})
        if code != 0:
            probes_ok = False
    gate("R10-probes-exit0", probes_ok, "; ".join(f"p{r['i']}:rc={r['rc']}" for r in probe_results))
    checks["probe_results"] = probe_results

    # R7/R8 manifest + POST-probe live sha
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    man = load_json(man_path)
    gate("R7-manifest-parses", isinstance(man, dict), str(type(man).__name__))
    rows = [
        a
        for a in ((man or {}).get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == uid
    ] if isinstance(man, dict) else []
    gate("R7-manifest-row", len(rows) >= 1, f"{len(rows)} rows for {uid}")
    match_row = None
    live_sha = live_bytes = None
    row_sha = row_bytes = None
    if rows and art_path.is_file():
        live_sha, live_bytes = norm_sha(art_path)
        for a in rows:
            if str(a.get("path") or "").replace("\\", "/") == out_rel and a.get("present") is True:
                match_row = a
                row_sha = a.get("sha256")
                row_bytes = a.get("bytes")
        gate(
            "R8-sha-match-post-probe",
            match_row is not None and row_sha == live_sha,
            f"live={str(live_sha)[:16]} manifest={str(row_sha)[:16]}",
        )
        gate(
            "R8-bytes-match",
            match_row is not None and row_bytes == live_bytes,
            f"live={live_bytes} manifest={row_bytes}",
        )
        checks["primary_row_role"] = match_row.get("role") if match_row else None
    checks["sha_live"] = live_sha
    checks["sha_manifest"] = row_sha

    return {"uid": uid, "ok": ok, "checks": checks}


def main() -> int:
    catalog = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    if not isinstance(catalog, dict):
        print("FAILED:catalog unparseable")
        return 2
    wu_index = {u.get("id"): u for u in catalog.get("work_units") or [] if isinstance(u, dict)}
    results = []
    for uid in UNITS:
        r = verify(uid, catalog, wu_index)
        results.append(r)
        bad = [k for k, v in r["checks"].items() if isinstance(v, dict) and v.get("pass") is False]
        print(f"{'PASS' if r['ok'] else 'FAIL'} {uid}" + (f"  failing: {bad}" if bad else ""))
        sys.stdout.flush()
    out = REPO / "_rev-w2-shard1" / "verify_out.json"
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    n_ok = sum(1 for r in results if r["ok"])
    print(f"SUMMARY {n_ok}/{len(results)} units fully verified; detail -> {out}")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
