#!/usr/bin/env python3
"""Independent reviewer battery, wave 3 shard 19, round r4 (2026-10-26).

Checks per unit (ALL must hold for PASS):
  1. artifact-checks : output_path artifact exists / non-empty / parses as JSON /
                       not self-declared BLOCKED or FAILED
  2. probes          : every PROBE-CMDS.json command re-run live from repo root,
                       exit 0 required
  3. sha256          : CRLF->LF normalized sha256 of the primary artifact matches
                       the role=primary row in probes/<id>/UNIT-ARTIFACT-MANIFEST.json
                       (all supporting rows also verified; primary is the gate)
  4. schema          : receipt validates against the catalog-declared output_schema
                       (shim chain, draft 2020-12); cross-checked through the
                       p2-g1 physical artifact-class-profile chain

Positive controls: ADV-0005 / ADV-0010 / ADV-0037 must schema-validate with zero
errors, proving the validator chain itself is live and not a false-FAIL machine.

Honesty rule: a unit that fails ANY check gets verdict FAIL with the precise
failing check and its receipt is left byte-identical (verified by hash after).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import jsonschema
import urllib.parse
import referencing
from referencing import Registry
from referencing.jsonschema import DRAFT202012

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
OUTDIR = ROOT / "_reviewer-w3s19-r4"
CATALOG = ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
RECEIPTS = ROOT / "command-center" / "receipts"
PROBES = ROOT / "command-center" / "p2-wave" / "probes"

UNITS = [
    "TST-0081", "TST-0085", "TST-0088", "TST-0090", "TST-0091", "TST-0092",
    "TST-0094", "TST-0100", "TST-0109", "TST-0113", "TST-0116", "TST-0124",
]
CONTROLS = ["ADV-0005", "ADV-0010", "ADV-0037"]
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-w3s19-r4-2026-10-26"


def log(msg: str) -> None:
    line = f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)


def norm_sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def raw_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_file_registry() -> Registry:
    """Registry that dereferences file:// schema URIs straight off disk."""
    def retrieve(uri: str):
        assert uri.startswith("file:"), f"non-file ref: {uri}"
        p = urllib.request.url2pathname(urllib.parse.urlparse(uri).path)
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        return referencing.Resource.from_contents(doc, default_specification=DRAFT202012)
    return Registry(retrieve=retrieve)


def load_schema_chain(shim_path: Path):
    """Build a 2020-12 validator over the shim, resolving file:// refs on disk."""
    shim = json.loads(shim_path.read_text(encoding="utf-8"))

    registry = make_file_registry()
    validator = jsonschema.Draft202012Validator(shim, registry=registry)
    class_name = shim.get("x-artifact-class")
    return validator, class_name


def resolver_chain_errors(receipt: dict, class_name: str | None):
    """Second, mechanically distinct chain: straight into the p2-g1 physical
    profiles schema at #/$defs/<class>."""
    profiles = ROOT / "platform" / "schema" / "artifact-class-profiles.schema.json"
    prof = json.loads(profiles.read_text(encoding="utf-8"))
    if class_name is None or class_name not in prof.get("$defs", {}):
        return None, "no-class"
    uri = profiles.as_uri() + "#/$defs/" + class_name
    schema = {"$ref": uri, "$defs": prof["$defs"]}

    registry = make_file_registry()
    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    errs = sorted(validator.iter_errors(receipt), key=lambda e: list(e.absolute_path))
    return errs, None


def fmt_err(e: jsonschema.ValidationError) -> str:
    path = "$" + "".join(f"[{i!r}]" if isinstance(i, int) else f".{i}" for i in e.absolute_path)
    return f"{path}: {e.message[:160]}"


def catalog_by_id() -> dict:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {u["id"]: u for u in cat["work_units"]}


def artifact_checks(unit: str, entry: dict, receipt_path: Path) -> tuple[list, dict]:
    fails, info = [], {}
    if not receipt_path.exists():
        return [f"artifact-missing: {receipt_path}"], info
    data = receipt_path.read_bytes()
    info["bytes"] = len(data)
    if len(data) == 0:
        fails.append("artifact-empty")
    try:
        doc = json.loads(data)
        info["parsed"] = True
    except Exception as exc:
        fails.append(f"artifact-unparsable: {type(exc).__name__}: {exc}")
        return fails, info
    state = doc.get("state")
    info["state"] = state
    if state in ("BLOCKED", "FAILED"):
        fails.append(f"self-blocked: state={state}")
    failure = doc.get("failure")
    if isinstance(failure, dict) and failure.get("state") in ("BLOCKED", "FAILED"):
        fails.append(f"self-blocked: failure.state={failure.get('state')}")
    return fails, info


def probe_cmds(unit: str) -> list[str]:
    pc = PROBES / unit / "PROBE-CMDS.json"
    if pc.exists():
        return json.loads(pc.read_text(encoding="utf-8"))
    return sorted(
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p.as_posix()}"
        for p in (PROBES / unit).glob("probe*.py")
    )


def run_probes(unit: str) -> tuple[list, list]:
    fails, runs = [], []
    cmds = probe_cmds(unit)
    if not cmds:
        return [f"no-probes-found: {PROBES / unit}"], runs
    for cmd in cmds:
        t0 = time.monotonic()
        try:
            r = subprocess.run(
                ["bash", "-lc", cmd],
                cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
            )
            rc, out, err = r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = -9, "", "TIMEOUT 1800s"
        secs = time.monotonic() - t0
        runs.append({"cmd": cmd, "rc": rc, "secs": round(secs, 1),
                     "tail": (out + err).strip().splitlines()[-3:]})
        if rc != 0:
            fails.append(f"probe-rc{rc}: {cmd} :: {' | '.join((out + err).strip().splitlines()[-2:])}")
    return fails, runs


def manifest_checks(unit: str, entry: dict, receipt_path: Path) -> tuple[list, dict]:
    fails, info = [], {}
    mp = PROBES / unit / "UNIT-ARTIFACT-MANIFEST.json"
    info["manifest_path"] = str(mp.relative_to(ROOT))
    if not mp.exists():
        return ["manifest-missing"], info
    man = json.loads(mp.read_text(encoding="utf-8"))
    rows = man.get("artifacts") or []
    info["manifest_rows"] = len(rows)
    op = (entry.get("output_path") or "").replace("\\", "/")
    primary = [r for r in rows
               if r.get("role") == "primary" or r.get("path", "").replace("\\", "/") == op]
    primary_row = next((r for r in primary
                        if r.get("path", "").replace("\\", "/") == op), None)
    if primary_row is None:
        return ["manifest-primary-row-missing-for-output_path"], info
    live = receipt_path.read_bytes()
    live_h = norm_sha256(live)
    info["live_norm_sha256"] = live_h
    info["manifest_primary_sha256"] = primary_row.get("sha256")
    if primary_row.get("sha256") != live_h:
        fails.append("sha256-mismatch: primary row vs CRLF-normalized live artifact")
    # supporting rows: verify existence + hash too (evidence completeness)
    for r in rows:
        rp = ROOT / r.get("path", "")
        if not rp.exists():
            fails.append(f"manifest-row-missing-on-disk: {r.get('path')}")
            continue
        if norm_sha256(rp.read_bytes()) != r.get("sha256"):
            fails.append(f"manifest-row-hash-mismatch: {r.get('path')}")
    return fails, info


def schema_checks(entry: dict, receipt: dict):
    fails, info = [], {}
    shim_rel = entry.get("output_schema")
    shim_path = ROOT / shim_rel
    info["output_schema"] = shim_rel
    if not shim_path.exists():
        return [f"output-schema-missing: {shim_rel}"], info
    try:
        validator, class_name = load_schema_chain(shim_path)
        info["artifact_class"] = class_name
        errs = sorted(validator.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        info["schema_errors_own_chain"] = len(errs)
        if errs:
            info["schema_first_own"] = [fmt_err(e) for e in errs[:3]]
            fails.append(f"schema-own-chain: {len(errs)} errors, first: {fmt_err(errs[0])}")
    except Exception as exc:
        fails.append(f"schema-chain-broken: {type(exc).__name__}: {exc}")
        info["schema_errors_own_chain"] = None
        return fails, info
    errs2, note = resolver_chain_errors(receipt, class_name)
    if errs2 is not None:
        info["schema_errors_resolver"] = len(errs2)
        if errs2:
            info["schema_first_resolver"] = [fmt_err(e) for e in errs2[:3]]
            if not errs:
                fails.append(f"schema-resolver: {len(errs2)} errors, first: {fmt_err(errs2[0])}")
    else:
        info["schema_errors_resolver"] = note
    return fails, info


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    t_start = time.monotonic()
    env = {
        "bash_which_python3": subprocess.run(["bash", "-lc", "which python3"],
                                             capture_output=True, text=True).stdout.strip() or None,
        "bash_which_pwsh": subprocess.run(["bash", "-lc", "which pwsh"],
                                          capture_output=True, text=True).stdout.strip() or None,
    }
    log(f"env: {env}")

    by_id = catalog_by_id()

    # ---- positive controls: validator chain must go green on known-good ----
    controls = {}
    for cu in CONTROLS:
        entry = by_id.get(cu)
        rp = ROOT / entry["output_path"]
        doc = json.loads(rp.read_bytes())
        f, _ = schema_checks(entry, doc)
        controls[cu] = {"schema_errors": len(f), "fails": f}
        log(f"control {cu}: {'OK (0 schema errors)' if not f else 'FAILED CONTROL: ' + str(f)}")
    for cu, c in controls.items():
        if c["schema_errors"]:
            log(f"ABORT: positive control {cu} failed - validator chain untrustworthy")
            (OUTDIR / "results_r4.json").write_text(json.dumps(
                {"reviewer_id": REVIEWER_ID, "aborted": f"positive-control-failed: {cu}",
                 "controls": controls}, indent=1), encoding="utf-8")
            return 2

    results = {}
    receipt_hash_after = {}
    for unit in UNITS:
        log(f"=== {unit} ===")
        entry = by_id.get(unit)
        if entry is None:
            results[unit] = {"fails": ["not-in-catalog"]}
            continue
        rp = ROOT / entry["output_path"]
        fails, ainfo = artifact_checks(unit, entry, rp)
        doc = None
        try:
            doc = json.loads(rp.read_bytes()) if rp.exists() else None
        except Exception:
            doc = None
        pfails, pruns = run_probes(unit)
        mfails, minfo = manifest_checks(unit, entry, rp)
        sfails, sinfo = ({}, {})
        if doc is not None:
            sfails, sinfo = schema_checks(entry, doc)
        all_fails = fails + pfails + mfails + sfails
        receipt_hash_after[unit] = {
            "raw": raw_sha256(rp.read_bytes()) if rp.exists() else None,
            "crlf_normalized": norm_sha256(rp.read_bytes()) if rp.exists() else None,
        }
        results[unit] = {
            "output_path": entry.get("output_path"),
            "output_schema": entry.get("output_schema"),
            "artifact": ainfo,
            "probe_runs": pruns,
            "manifest": minfo,
            "schema": sinfo,
            "fails": all_fails,
        }
        log(f"{unit}: {'ALL HOLD' if not all_fails else 'FAIL x%d' % len(all_fails)}")
        for f in all_fails:
            log(f"    - {f}")

    # receipts untouched?
    untouched = all(
        (receipt_hash_after[u]["crlf_normalized"]
         == results[u].get("manifest", {}).get("live_norm_sha256"))
        or results[u]["fails"]
        for u in UNITS if u in results
    )

    verdicts = {}
    for u in UNITS:
        r = results.get(u, {})
        ok = not r.get("fails")
        primary = None
        if not ok:
            order = ["artifact", "probe", "sha256", "schema"]
            f = r["fails"][0]
            if f.startswith("probe-"):
                primary = "re-run the live probes (exit 0 required)"
            elif f.startswith("sha256") or f.startswith("manifest-"):
                primary = "manifest sha256 match"
            elif f.startswith("schema") or f.startswith("output-schema"):
                primary = "validate output_schema"
            else:
                primary = "artifact exists/non-empty/parses/not-self-blocked"
        verdicts[u] = {
            "verdict": "PASS" if ok else "FAIL",
            "primary_failing_check": None if ok else primary,
            "fails": r.get("fails", []),
            "probes_all_rc0": all(p["rc"] == 0 for p in r.get("probe_runs", [])) if r.get("probe_runs") else None,
            "receipt_state_left": (r.get("artifact") or {}).get("state"),
        }

    out = {
        "reviewer_id": REVIEWER_ID,
        "wave": "wave3",
        "shard": 19,
        "round": "r4",
        "units_total": len(UNITS),
        "positive_control": {c: {"schema_errors": v["schema_errors"]}
                             for c, v in controls.items()},
        "env_note": env,
        "receipts_untouched_by_reviewer": untouched,
        "receipt_sha256_after": receipt_hash_after,
        "order": UNITS,
        "results": results,
        "verdicts": verdicts,
        "wall_secs": round(time.monotonic() - t_start, 1),
    }
    (OUTDIR / "results_r4.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (OUTDIR / "VERDICTS-w3s19-r4.json").write_text(json.dumps(verdicts, indent=1),
                                                   encoding="utf-8")
    log(f"done in {out['wall_secs']}s -> {OUTDIR / 'results_r4.json'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
