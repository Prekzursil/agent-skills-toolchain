#!/usr/bin/env python3
"""INDEPENDENT REVIEWER battery - wave 2 shard 24 (8 units). NOT a builder.

verify : re-derive every contract check from live bytes; re-run the live
         probes (Git Bash AND pwsh7 per the units' reviewer_requirement);
         recompute the artifact sha256 and match the manifest row; validate
         the receipt against the catalog output_schema via TWO mechanically
         independent lanes; enforce receipt_core (SUCCESS needs
         reviewer.verdict=PASS + reviewer.independent=true).
close  : only when ALL checks hold, confirm the existing valid PASS closure
         stays SUCCESS and stamp an ADDITIVE wave2_shard24_review block
         (never touching the original reviewer closure). ANY failure leaves
         the receipt byte-untouched.

Usage: python -I battery.py [--close] [UID ...]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
RECEIPTS = REPO / "command-center" / "receipts"
OUT = REPO / "_p2shard24-w2-review"
REVIEWER_ID = "independent-reviewer-wave2-shard24-opus-fresh"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 900

UIDS = [
    "TST-0145", "TST-0150", "TST-0151", "TST-0155",
    "TST-0158", "TST-0161", "TST-0162", "TST-0163",
]

sys.path.insert(0, str(REPO / "platform" / "lib"))
import jsonschema  # noqa: E402
import schema_resolver as sres  # noqa: E402

PY_DIRS = [
    str(REPO / "command-center" / "p2-wave" / "seed-stage"),
    str(REPO),
    str(REPO / "tools"),
    str(REPO / "tools" / "measure-guard"),
    str(REPO / "platform" / "lib"),
    str(REPO / "tools" / "agentspec"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_sha(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def jload(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _base_env() -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    sep = os.pathsep
    env["PYTHONPATH"] = sep.join(PY_DIRS + [env.get("PYTHONPATH", "")])
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    return env


def strip_env_prefix(cmd: str, env: dict) -> str:
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            return cmd
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]


def run_bash(cmd: str) -> tuple[int, str]:
    env = _base_env()
    try:
        r = subprocess.run(
            ["bash", "-lc", cmd], cwd=str(REPO), env=env,
            capture_output=True, text=True, timeout=PROBE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()[-600:]


def run_pwsh(cmd: str) -> tuple[int, str]:
    env = _base_env()
    cmd2 = strip_env_prefix(cmd, env)
    exe = sys.executable.replace("\\", "/")
    cmd2 = cmd2.replace("python3", exe, 1)
    try:
        r = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", cmd2],
            cwd=str(REPO), env=env, capture_output=True, text=True,
            timeout=PROBE_TIMEOUT,
        )
    except FileNotFoundError:
        return 127, "pwsh-not-found"
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()[-600:]


def named_probe_commands(receipt: dict) -> list[str]:
    cmds = []
    for item in receipt.get("named_probes") or []:
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            cmds.append(item["command"].strip())
    if len(cmds) >= 2:
        return cmds
    return cmds


def fallback_probe_commands(uid: str) -> list[str]:
    d = PROBES / uid
    p1 = [p for p in sorted(d.glob("probe1*.py")) if p.name != "probe1.py"] or sorted(d.glob("probe1*.py"))
    p2 = [p for p in sorted(d.glob("probe2*.py")) if p.name != "probe2.py"] or sorted(d.glob("probe2*.py"))
    out = []
    for p in p1[:1] + p2[:1]:
        out.append(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p.relative_to(REPO).as_posix()}")
    if not out:
        run = d / "run_probes.py"
        if run.is_file():
            out.append(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {run.relative_to(REPO).as_posix()}")
    return out


def schema_lanes(artifact: dict, output_schema: str) -> tuple[list[str], list[str]]:
    """Two mechanically independent schema lanes."""
    # Lane 1: the program's resolver.
    try:
        lane1 = sres.validate_artifact(artifact, output_schema) or []
    except Exception as exc:  # noqa: BLE001
        lane1 = [f"resolver-error: {type(exc).__name__}: {exc}"]
    # Lane 2: manual fragment resolution + Draft 2020-12.
    lane2 = []
    try:
        m = re.match(r"^(.*?)#\s*/\$\defs/(\w+)$", output_schema)
        if m:
            schema_path = REPO / m.group(1)
            frag = m.group(2)
        else:
            schema_path = REPO / output_schema
            frag = None
        whole = json.loads(schema_path.read_text(encoding="utf-8"))
        target = whole["$defs"][frag] if frag else whole
        errs = sorted(
            jsonschema.Draft202012Validator(target).iter_errors(artifact),
            key=lambda e: list(e.path),
        )
        lane2 = [
            f"{list(e.path)}: {e.message[:160]}" for e in errs[:10]
        ]
    except Exception as exc:  # noqa: BLE001
        lane2 = [f"lane2-error: {type(exc).__name__}: {exc}"]
    return lane1, lane2


def review_unit(uid: str, units: dict, do_close: bool) -> dict:
    rep: dict = {"unit_id": uid}
    fails: list[str] = []

    unit = units.get(uid)
    if not unit:
        return {**rep, "verdict": "FAIL", "fail_reasons": ["catalog-entry-absent"]}
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel
    rep["output_path"] = out_rel

    # R1 artifact exists / non-empty
    if not out.is_file():
        return {**rep, "verdict": "FAIL", "fail_reasons": [f"artifact-absent:{out_rel}"]}
    raw = out.read_bytes()
    rep["bytes"] = len(raw)
    if len(raw) <= 0:
        fails.append("artifact-empty")

    # R2 parses / dict / not self-blocked / sentinel
    doc, err = jload(out)
    if doc is None:
        return {**rep, "verdict": "FAIL",
                "fail_reasons": [f"artifact-unparseable:{err}"]}
    if not isinstance(doc, dict):
        return {**rep, "verdict": "FAIL", "fail_reasons": ["artifact-not-object"]}
    st = str(doc.get("state") or "").upper()
    rep["state"] = st
    if st in NOT_DELIVERING:
        fails.append(f"self-declared:{st}")
    sentinel = str(unit.get("completion_sentinel") or f"SUCCESS:{uid}")
    if sentinel not in raw.decode("utf-8", errors="replace"):
        fails.append(f"completion-sentinel-absent:{sentinel}")

    # R3 receipt_core: SUCCESS requires reviewer PASS + independent
    rv = doc.get("reviewer") or {}
    rep["prior_reviewer"] = {
        "reviewer_id": rv.get("reviewer_id"),
        "verdict": rv.get("verdict"),
        "independent": rv.get("independent"),
        "fresh_context": rv.get("fresh_context"),
    }
    if st == "SUCCESS":
        if rv.get("verdict") != "PASS":
            fails.append("receipt-core:state=SUCCESS-without-reviewer-PASS")
        if rv.get("independent") is not True:
            fails.append("receipt-core:reviewer-not-independent")

    # R4 manifest row vs live artifact (CRLF-normalized sha)
    live_sha = norm_sha(raw)
    rep["live_norm_sha256"] = live_sha
    man_p = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_p.is_file():
        fails.append(f"manifest-absent:{man_p.relative_to(REPO).as_posix()}")
    else:
        man, merr = jload(man_p)
        if man is None:
            fails.append(f"manifest-unparseable:{merr}")
        else:
            rows = man if isinstance(man, list) else man.get("rows") or man.get("artifacts") or []
            row = None
            for rr in rows:
                if not isinstance(rr, dict):
                    continue
                rp = str(rr.get("path") or "").replace("\\", "/")
                if rp == out_rel or rp.endswith("/" + uid + ".json"):
                    row = rr
                    break
            if row is None:
                fails.append("manifest-row-for-unit-absent")
            else:
                rep["manifest_row"] = {
                    "sha256": row.get("sha256"),
                    "present": row.get("present", row.get("exists")),
                }
                if str(row.get("sha256") or "").lower() != live_sha:
                    fails.append("manifest-sha-mismatch")
                if row.get("present") is False or row.get("exists") is False:
                    fails.append("manifest-row-says-absent")

    # R5 schema validation, two independent lanes
    l1, l2 = schema_lanes(doc, str(unit.get("output_schema") or ""))
    rep["schema_lane_resolver_errors"] = l1[:6]
    rep["schema_lane_jsonschema_errors"] = l2[:6]
    if l1:
        fails.append("output-schema-invalid:resolver-lane:" + str(l1[0])[:160])
    if l2:
        fails.append("output-schema-invalid:jsonschema-lane:" + str(l2[0])[:160])

    # R6 live probe re-runs (bash + pwsh7), MY OWN runs
    cmds = named_probe_commands(doc) or fallback_probe_commands(uid)
    if not cmds:
        fails.append("probe-commands-unresolvable")
    probes = []
    for i, cmd in enumerate(cmds, 1):
        rb, ob = run_bash(cmd)
        rp, op = run_pwsh(cmd)
        probes.append({
            "cmd": cmd,
            "bash_rc": rb,
            "pwsh_rc": rp,
            "bash_tail": ob[-200:],
            "pwsh_tail": op[-200:],
        })
        if rb != 0:
            fails.append(f"probe{i}-bash-rc={rb}")
        if rp != 0:
            fails.append(f"probe{i}-pwsh-rc={rp}")
    rep["probes_rerun"] = probes

    # verdict
    if fails:
        return {**rep, "verdict": "FAIL", "fail_reasons": fails}

    # ALL hold: confirm the existing valid PASS closure; additive stamp only
    if do_close:
        stamp = {
            "reviewer_id": REVIEWER_ID,
            "confirmed_at": now_iso(),
            "mode": "confirm-existing-closure",
            "probe_reruns": {p["cmd"]: {"bash": p["bash_rc"], "pwsh": p["pwsh_rc"]}
                             for p in probes},
            "live_norm_sha256": live_sha,
            "manifest_row_matched": True,
            "schema_lanes_clean": True,
        }
        existing = doc.get("wave2_shard24_review")
        if isinstance(existing, dict) and existing.get("reviewer_id") == REVIEWER_ID:
            pass  # idempotent re-close
        else:
            doc["wave2_shard24_review"] = stamp
            out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        rep["closed"] = True
    return {**rep, "verdict": "PASS", "fail_reasons": []}


def main() -> int:
    do_close = "--close" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    uids = only or UIDS
    cat, err = jload(CATALOG)
    if cat is None:
        print("FAILED:catalog", err)
        return 1
    units = {u.get("id"): u for u in cat.get("work_units") or []}
    OUT.mkdir(exist_ok=True)
    reps = []
    n_pass = 0
    for uid in uids:
        t0 = time.time()
        r = review_unit(uid, units, do_close)
        r["seconds"] = round(time.time() - t0, 1)
        reps.append(r)
        if r["verdict"] == "PASS":
            n_pass += 1
            print(f"PASS:{uid} ({r['seconds']}s, {len(r.get('probes_rerun') or [])} probes x2 shells)")
        else:
            print(f"FAIL:{uid} " + " | ".join(x[:150] for x in r.get("fail_reasons", [])))
    (OUT / "review-report.json").write_text(
        json.dumps(reps, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    label = "ALL-GREEN" if n_pass == len(reps) else "PARTIAL"
    print(f"REVIEWER {label} {n_pass}/{len(reps)} (close={do_close})")
    return 0 if n_pass == len(reps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
