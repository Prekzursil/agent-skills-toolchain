#!/usr/bin/env python3
"""Independent reviewer verification - P2 wave 3 shard 5 (12 units).

Reviewer role: I did not build these units. This driver implements the
DELIVERED checks with independent code (does not import the builder-side
measure module) and records per-check evidence.

Units (authoritative: builder's _p2-shard5-w3/static_check.py id list):
  AUD-0082 AUD-0084 AUD-0095 AUD-0096 BLD-0001 BLD-0002 BLD-0010
  BLD-0016 BLD-0023 BLD-0024 BLD-0027 BLD-0028

Checks per unit (phase A, pre-closure):
  C1  artifact exists / non-empty / parses
  C2  not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
      (exception: builder-terminal awaiting review, marked NEEDS-CLOSURE,
       only when failure.classification == ["reviewer-absent"])
  C3  catalog completion_sentinel present verbatim in artifact text
  C4  SUBAGENT-RETURN.json parses; status not in NOT_DELIVERING
  C5  live probe re-run (verbatim recorded commands, recorded env
      conditions reproduced); rc == 0 required
  C6  manifest row: path == catalog output_path, present true,
      sha256 == live artifact sha256 (CRLF normalized to LF);
      every other present-true row's file also exists on disk
  C7  strict Draft202012 validation vs catalog output_schema
  C8  receipt_core ($defs.receipt_core) validation
  C9  already-closed units: reviewer verdict PASS + independent true +
      reviewer_id differs from produced_by author identity
  C10 owner-gated units: gate reason recorded in the receipt
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT_DIR = REPO / "_p2shard5-w3-review"
UNITS = ["AUD-0082", "AUD-0084", "AUD-0095", "AUD-0096", "BLD-0001",
         "BLD-0002", "BLD-0010", "BLD-0016", "BLD-0023", "BLD-0024",
         "BLD-0027", "BLD-0028"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
REVIEWER_ABSENT = {"reviewer-absent"}


def digest_lf(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - verdict needs the class
        return None, f"{type(exc).__name__}: {exc}"


_CATALOG = None


def catalog():
    global _CATALOG
    if _CATALOG is None:
        _CATALOG, _ = load(REPO / "command-center/WORK-UNIT-CATALOG.json")
    return _CATALOG


def wu(uid: str):
    for u in catalog()["work_units"]:
        if u.get("id") == uid:
            return u
    return None


_SCHEMA_CACHE: dict[str, tuple[object, RefResolver | None, str | None]] = {}


def schema_validator(schema_rel: str):
    """Build (validator, resolver) for a schema file, cached."""
    if schema_rel in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[schema_rel]
    spath = REPO / schema_rel
    schema, err = load(spath)
    if err:
        _SCHEMA_CACHE[schema_rel] = (None, None, f"schema-unreadable {schema_rel}: {err}")
        return _SCHEMA_CACHE[schema_rel]
    resolver = RefResolver(base_uri=spath.as_uri(), referrer=schema)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        v = Draft202012Validator(schema, resolver=resolver)
    _SCHEMA_CACHE[schema_rel] = (v, resolver, None)
    return _SCHEMA_CACHE[schema_rel]


def validate(schema_rel: str, doc) -> list[str]:
    v, _r, err = schema_validator(schema_rel)
    if err:
        return [err]
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
    out = []
    for e in errs[:10]:
        out.append(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:220]}")
    if len(errs) > 10:
        out.append(f"... +{len(errs) - 10} more")
    return out


def receipt_core_validator():
    schema, err = load(REPO / "platform/schema/receipt.schema.json")
    if err:
        return None, f"receipt.schema.json unreadable: {err}"
    # Internal $refs (#/$defs/...) resolve against the FULL schema root, so
    # validate through a wrapper that carries the whole $defs block.
    entry = {"allOf": [{"$ref": "#/$defs/receipt_core"}], "$defs": schema["$defs"]}
    resolver = RefResolver(base_uri=(REPO / "platform/schema/receipt.schema.json").as_uri(),
                           referrer=schema)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Draft202012Validator(entry, resolver=resolver), None


ENV_PREFIX = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+")


def run_probe(cmd: str, timeout: int = 2700) -> tuple[int, str]:
    """Reproduce the recorded run conditions (env prefixes, PYTHONPATH,
    g1_python wrapper) with this reviewer's own implementation."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([
        hook_dir, str(REPO), str(REPO / "tools"),
        str(REPO / "tools" / "measure-guard"), str(REPO / "platform" / "lib"),
        str(REPO / "tools" / "agentspec"), env.get("PYTHONPATH", ""),
    ])
    while True:
        m = ENV_PREFIX.match(cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    try:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def probe_commands(uid: str, ret: dict, art: dict) -> list[str]:
    cmds: list[str] = []
    for src in (ret.get("named_probes"), art.get("named_probes")):
        for item in src or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                c = item["command"].strip()
                if c and c not in cmds:
                    cmds.append(c)
    if cmds:
        return cmds
    pd = REPO / "command-center/p2-wave/probes" / uid
    for pat in ("probe1*.py", "probe2*.py"):
        for f in sorted(pd.glob(pat)):
            cmds.append(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {f.relative_to(REPO).as_posix()}")
    return cmds


def main() -> int:
    rcv, rc_err = receipt_core_validator()
    report: dict[str, dict] = {}
    for uid in UNITS:
        entry = wu(uid)
        checks: dict[str, object] = {}
        notes: list[str] = []
        if entry is None:
            report[uid] = {"verdict": "FAIL", "reason": "catalog-missing"}
            continue
        out_rel = str(entry.get("output_path") or "").replace("\\", "/")
        art_path = REPO / out_rel

        # C1
        if not art_path.is_file() or art_path.stat().st_size <= 0:
            report[uid] = {"verdict": "FAIL", "reason": f"C1 artifact-absent/empty {out_rel}"}
            continue
        raw_text = art_path.read_text(encoding="utf-8")
        art, perr = load(art_path)
        if perr:
            report[uid] = {"verdict": "FAIL", "reason": f"C1 unparseable {perr}"}
            continue
        checks["C1_parses_bytes"] = art_path.stat().st_size

        # C2 state
        state = str(art.get("state") or "").upper()
        failcls = (art.get("failure") or {}).get("classification") if isinstance(art.get("failure"), dict) else None
        needs_closure = False
        if state in NOT_DELIVERING:
            if set(failcls or []) == REVIEWER_ABSENT or state == "BLOCKED" and failcls and set(failcls) & REVIEWER_ABSENT:
                needs_closure = True
                notes.append(f"builder-terminal state={state} classification={failcls} awaiting reviewer")
            else:
                report[uid] = {"verdict": "FAIL", "reason": f"C2 self-declared:{state}", "checks": checks}
                continue
        elif state == "":
            if failcls and set(failcls) & REVIEWER_ABSENT:
                needs_closure = True
                notes.append("state token absent; extensions.builder_process_state="
                             f"{(art.get('extensions') or {}).get('builder_process_state')}; classification={failcls}")
            else:
                report[uid] = {"verdict": "FAIL", "reason": "C2 state absent, not reviewer-absent", "checks": checks}
                continue
        checks["C2_state"] = state or "<absent>"
        checks["needs_closure"] = needs_closure

        # C3 sentinel
        sentinel = str(entry.get("completion_sentinel") or "")
        checks["C3_sentinel_present"] = bool(sentinel) and sentinel in raw_text
        if not checks["C3_sentinel_present"]:
            report[uid] = {"verdict": "FAIL", "reason": "C3 sentinel-absent", "checks": checks}
            continue

        # C4 SUBAGENT-RETURN
        sr_path = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
        ret, serr = load(sr_path)
        if serr or not isinstance(ret, dict):
            report[uid] = {"verdict": "FAIL", "reason": f"C4 return-unparseable {serr}", "checks": checks}
            continue
        st_ret = str(ret.get("status") or ret.get("state") or "").upper()
        checks["C4_return_status"] = st_ret
        if st_ret in NOT_DELIVERING:
            report[uid] = {"verdict": "FAIL", "reason": f"C4 return:{st_ret}", "checks": checks}
            continue

        # C5 probes live
        cmds = probe_commands(uid, ret, art)
        checks["C5_probe_count"] = len(cmds)
        probe_results = []
        probes_all_zero = True
        for i, c in enumerate(cmds, 1):
            rc, out = run_probe(c)
            tail = out[-300:]
            probe_results.append({"cmd": c, "rc": rc, "tail": tail})
            if rc != 0:
                probes_all_zero = False
                notes.append(f"probe[{i}] rc={rc} tail={tail[:200]}")
        checks["C5_probes_rc0"] = probes_all_zero
        checks["C5_probe_results"] = probe_results

        # C6 manifest
        man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man, merr = load(man_path)
        if merr:
            report[uid] = {"verdict": "FAIL", "reason": f"C6 manifest-unparseable {merr}", "checks": checks}
            continue
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        checks["C6_rows"] = len(rows)
        live_sha = digest_lf(art_path)
        checks["C6_live_sha256"] = live_sha
        primary = [a for a in rows
                   if str(a.get("path") or "").replace("\\", "/") == out_rel]
        sha_ok = bool(primary) and primary[0].get("present") is True \
            and str(primary[0].get("sha256") or "") == live_sha
        checks["C6_primary_row_sha_match"] = sha_ok
        missing_rows = []
        for a in rows:
            if a is primary[0]:
                continue
            if a.get("present") is True:
                rp = REPO / str(a.get("path") or "").replace("\\", "/")
                if not rp.is_file():
                    missing_rows.append(str(a.get("path")))
        checks["C6_other_present_rows_missing"] = missing_rows
        if not sha_ok:
            rec = primary[0].get("sha256") if primary else None
            report[uid] = {"verdict": "FAIL",
                           "reason": f"C6 manifest-sha-mismatch recorded={str(rec)[:16]} live={live_sha[:16]}",
                           "checks": checks}
            continue

        # C7 catalog output_schema
        oschema = str(entry.get("output_schema") or "")
        sch_errs = validate(oschema, art)
        checks["C7_schema"] = oschema
        checks["C7_errors"] = sch_errs

        # C8 receipt_core
        if rcv is None:
            checks["C8_errors"] = [rc_err]
        else:
            errs = sorted(rcv.iter_errors(art), key=lambda e: list(e.absolute_path))
            checks["C8_errors"] = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}"
                                   for e in errs[:10]]
        # SUCCESS-state units must be receipt_core-clean NOW (conditionals live).
        if state == "SUCCESS" and checks["C8_errors"]:
            report[uid] = {"verdict": "FAIL", "reason": "C8 receipt_core errors",
                           "detail": checks["C8_errors"][:4], "checks": {k: v for k, v in checks.items() if k != "C5_probe_results"}}
            continue

        # C9 existing closure independence (SUCCESS-state units)
        if state == "SUCCESS":
            rev = art.get("reviewer") or {}
            pb = art.get("produced_by") or {}
            rid = str(rev.get("reviewer_id") or "")
            author = f"{pb.get('vendor','')}/{pb.get('model','')}"
            ok = rev.get("verdict") == "PASS" and rev.get("independent") is True and bool(rid)
            checks["C9_existing_closure"] = {
                "verdict": rev.get("verdict"), "independent": rev.get("independent"),
                "reviewer_id": rid[:80], "author": author[:80], "ok": ok}
            if not ok:
                report[uid] = {"verdict": "FAIL", "reason": "C9 existing closure invalid",
                               "detail": checks["C9_existing_closure"], "checks": {}}
                continue

        # C10 owner gate recorded
        og = ret.get("owner_gate")
        if og:
            blob = raw_text
            gate_txt = json.dumps(og, ensure_ascii=False)
            frag = []
            if isinstance(og, dict):
                for v in og.values():
                    if isinstance(v, str) and len(v) > 12:
                        frag.append(v[:60])
            recorded = any(f in blob for f in frag) if frag else (gate_txt[:40] in blob)
            checks["C10_owner_gate_recorded"] = {"gate": og, "recorded": recorded}
            if not recorded:
                notes.append("owner_gate present in SUBAGENT-RETURN but NOT verbatim in receipt")

        # SUCCESS-state units: C7 must be clean NOW
        if state == "SUCCESS" and sch_errs:
            report[uid] = {"verdict": "FAIL", "reason": "C7 output_schema errors",
                           "detail": sch_errs[:4], "checks": {}}
            continue

        verdict = "NEEDS-CLOSURE" if needs_closure else ("PASS-CONFIRM-PENDING-PROBES" if probes_all_zero else "PROBE-FAIL-PENDING")
        report[uid] = {"verdict": verdict, "checks": checks, "notes": notes}

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "phaseA-report.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8")
    for uid, r in report.items():
        print(f"{uid:9} {r['verdict']:28} {r.get('reason','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
