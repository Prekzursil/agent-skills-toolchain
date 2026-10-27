#!/usr/bin/env python3
"""Phase C: final adversarial verification, all 12 units, post-closure state.

Per unit:
  V1  artifact exists / non-empty / parses / not self-declared not-delivering
  V2  catalog completion_sentinel verbatim in artifact text
  V3  SUBAGENT-RETURN parses; status not not-delivering
  V4  live probe re-run (reviewer-executed) - every rc == 0
  V5  manifest primary row: present + sha256 == recomputed live sha (CRLF->LF)
      + every other present-true row's file exists
  V6  strict output_schema validation (repo-blessed schema_resolver) - 0 errors
  V7  receipt_core validation (independent chain) - 0 errors
  V8  canonical program measure re-run - SUCCESS:delivered
  V9  closure validity: state SUCCESS + reviewer PASS + independent true

FAIL -> verdict FAIL with the precise failing check; receipt left unchanged.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "platform" / "lib"))
import schema_resolver  # noqa: E402 repo-blessed validator
from jsonschema import Draft202012Validator, RefResolver  # noqa: E402

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_p2shard5-w3-review"
UNITS = ["AUD-0082", "AUD-0084", "AUD-0095", "AUD-0096", "BLD-0001",
         "BLD-0002", "BLD-0010", "BLD-0016", "BLD-0023", "BLD-0024",
         "BLD-0027", "BLD-0028"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
ENV_PREFIX = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+")


def digest_lf(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_probe(cmd: str) -> tuple[int, str]:
    import os
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    while True:
        m = ENV_PREFIX.match(cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=2700, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def run_measure(uid: str) -> tuple[int, str]:
    import os
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    exe = str(sys.executable).replace("\\", "/")
    cmd = f'"{exe}" -I command-center/p2-wave/_measure_one_delivered.py {uid}'
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    while True:
        m = ENV_PREFIX.match(cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=3600, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def probe_cmds(uid: str) -> list[str]:
    sr = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json")
                    .read_text(encoding="utf-8"))
    cmds = []
    for np in (sr.get("named_probes") or []):
        if isinstance(np, dict) and isinstance(np.get("command"), str):
            c = np["command"].strip()
            if c and c not in cmds:
                cmds.append(c)
    return cmds


def schema_errors(doc, schema_rel: str) -> list[str]:
    return schema_resolver.validate_artifact(doc, schema_rel)


_receipt_validator = None


def receipt_core_errors(doc) -> list[str]:
    global _receipt_validator
    if _receipt_validator is None:
        schema = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
        entry = {"allOf": [{"$ref": "#/$defs/receipt_core"}], "$defs": schema["$defs"]}
        resolver = RefResolver(base_uri=(REPO / "platform/schema/receipt.schema.json").as_uri(),
                               referrer=schema)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _receipt_validator = Draft202012Validator(entry, resolver=resolver)
    errs = sorted(_receipt_validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}"
            for e in errs[:8]]


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wu = {u["id"]: u for u in cat["work_units"]}
    report = {}
    for uid in UNITS:
        entry = wu[uid]
        out_rel = str(entry["output_path"]).replace("\\", "/")
        art_path = REPO / out_rel
        r: dict = {"output_path": out_rel}
        fails: list[str] = []

        # V1
        if not art_path.is_file() or art_path.stat().st_size <= 0:
            r["verdict"] = "FAIL"
            r["reason"] = "V1 artifact-absent-or-empty"
            report[uid] = r
            continue
        text = art_path.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except Exception as exc:  # noqa: BLE001
            r["verdict"] = "FAIL"
            r["reason"] = f"V1 unparseable {type(exc).__name__}"
            report[uid] = r
            continue
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            fails.append(f"V1 self-declared:{st}")

        # V2
        sentinel = str(entry.get("completion_sentinel") or "")
        if not sentinel or sentinel not in text:
            fails.append("V2 sentinel-absent")

        # V3
        sr_path = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
        try:
            sr = json.loads(sr_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            fails.append(f"V3 return-unparseable {type(exc).__name__}")
            sr = {}
        else:
            st_ret = str(sr.get("status") or sr.get("state") or "").upper()
            if st_ret in NOT_DELIVERING:
                fails.append(f"V3 return:{st_ret}")

        # V4 live probes
        probe_res = []
        for i, c in enumerate(probe_cmds(uid), 1):
            rc, out = run_probe(c)
            probe_res.append({"cmd": c, "rc": rc,
                              "tail": out[-220:].replace("\n", " | ")})
            if rc != 0:
                fails.append(f"V4 probe[{i}] rc={rc}: {out[-160:]}")

        # V5 manifest
        man = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json")
                         .read_text(encoding="utf-8"))
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid]
        live = digest_lf(art_path)
        primary = [a for a in rows
                   if str(a.get("path") or "").replace("\\", "/") == out_rel]
        if not primary:
            fails.append("V5 manifest-primary-row-absent")
        else:
            if primary[0].get("present") is not True:
                fails.append("V5 primary-row present!=true")
            if str(primary[0].get("sha256") or "") != live:
                fails.append(f"V5 sha-mismatch recorded={str(primary[0].get('sha256'))[:16]} live={live[:16]}")
        missing = [str(a.get("path")) for a in rows
                   if a is not primary[0] and a.get("present") is True
                   and not (REPO / str(a.get("path") or "").replace("\\", "/")).is_file()]
        if missing:
            fails.append(f"V5 present-rows-absent-on-disk {missing[:3]}")

        # V6 output_schema (repo-blessed)
        sch_errs = schema_errors(doc, str(entry["output_schema"]))
        if sch_errs:
            fails.append(f"V6 output_schema x{len(sch_errs)}: " + " ;; ".join(e[:130] for e in sch_errs[:3]))

        # V7 receipt_core
        rc_errs = receipt_core_errors(doc)
        if rc_errs:
            fails.append(f"V7 receipt_core x{len(rc_errs)}: " + " ;; ".join(e[:130] for e in rc_errs[:3]))

        # V8 canonical measure
        mrc, mout = run_measure(uid)
        r["measure"] = {"rc": mrc, "line": (mout.splitlines() or [""])[-1][:120]}
        if mrc != 0 or f"SUCCESS:delivered {uid}" not in mout:
            fails.append(f"V8 measure rc={mrc} {mout[-160:]}")

        # V9 closure
        rev = doc.get("reviewer") or {}
        if doc.get("state") != "SUCCESS" or rev.get("verdict") != "PASS" or rev.get("independent") is not True:
            fails.append(f"V9 closure-invalid state={doc.get('state')} verdict={rev.get('verdict')} ind={rev.get('independent')}")

        r["sha256_live"] = live
        r["probes"] = probe_res
        r["schema_errors_n"] = len(sch_errs)
        r["receipt_core_errors_n"] = len(rc_errs)
        r["verdict"] = "PASS" if not fails else "FAIL"
        if fails:
            r["reasons"] = fails
        report[uid] = r

    (OUT / "final-verify.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    n_pass = sum(1 for v in report.values() if v["verdict"] == "PASS")
    for uid, v in report.items():
        line = f"{uid:9} {v['verdict']:5}"
        if v["verdict"] == "FAIL":
            line += "  " + " ;; ".join(x[:110] for x in v.get("reasons", [])[:2])
        else:
            line += f"  sha={v['sha256_live'][:12]} probes0={all(p['rc']==0 for p in v['probes'])} sch={v['schema_errors_n']} rc={v['receipt_core_errors_n']} measure={v['measure']['line'][:40]}"
        print(line)
    print(f"SUMMARY {n_pass}/{len(UNITS)} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
