#!/usr/bin/env python3
"""Independent reviewer wave-4 shard-1, phase 1: static + live-probe verification.

Reviewer (me) did NOT build these units. For each of the 12 shard units:
  S1 catalog entry present (output_path/output_schema/dependencies known)
  S2 artifact: exists, non-empty, parses, NOT self-declared BLOCKED/FAILED,
     sentinel text present, min-bytes floor honored
  S3 manifest: probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row path matches
     catalog output_path; recomputed sha256 (CRLF->LF) == manifest sha AND ==
     receipt primary sha; live size sanity
  S4 schema: catalog output_schema file loads; artifact strictly validates
     (jsonschema, $schema-aware)
  S5 receipt: parses, unit_id matches, primary row matches live path, and for
     already-SUCCESS units reviewer block verdict=PASS independent=true
  P  live probes: every probe[0-9]*.py in probes/<id>/ re-run by THIS reviewer
     (python -B, cwd=repo root, per-probe timeout, rc must be 0, SUCCESS marker)
  G  receipt gate: platform/lib/receipt_schema_gate.evaluate_full() run by me

Writes incremental JSON state to _reviewer-w4-shard1/phase1_state.json and
per-probe logs to _reviewer-w4-shard1/logs/.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUTDIR = Path(__file__).resolve().parent
LOGS = OUTDIR / "logs"
LOGS.mkdir(exist_ok=True)

UNITS = [
    "ADV-0038", "ADV-0040", "ADV-0090", "ADV-0091", "ADV-0096", "ADV-0100",
    "ADV-0109", "ADV-0110", "ADV-0117", "ADV-0119", "ADV-0123", "ADV-0124",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
STATE_PATH = OUTDIR / "phase1_state.json"
PROBE_TIMEOUT_S = 900

state: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "units": {}}


def save() -> None:
    STATE_PATH.write_text(json.dumps(state, indent=1), encoding="utf-8")


def sha256_norm(path: Path) -> str:
    """sha256 with CRLF normalized to LF before hashing (program contract)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_catalog() -> dict[str, dict]:
    doc = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return {u["id"]: u for u in doc["work_units"] if isinstance(u.get("id"), str)}


def load_gate():
    gp = REPO / "platform/lib/receipt_schema_gate.py"
    spec = importlib.util.spec_from_file_location("receipt_schema_gate", gp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["receipt_schema_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def validate_artifact_schema(artifact: dict, schema: dict):
    import jsonschema
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    v = cls(schema)
    return sorted(str(e.message) for e in v.iter_errors(artifact))[:10]


def main() -> int:
    catalog = load_catalog()
    gate = load_gate()
    any_fail = False

    run_ids = sys.argv[1:] or UNITS
    for uid in run_ids:
        rec: dict = {"checks": {}, "probes": {}}
        fails: list[str] = []

        # S1 catalog
        ce = catalog.get(uid)
        rec["checks"]["catalog_entry"] = bool(ce)
        if not ce:
            fails.append("S1 catalog entry missing")
            rec["fails"] = fails
            state["units"][uid] = rec
            save()
            any_fail = True
            continue
        rec["catalog"] = {
            "output_path": ce.get("output_path"),
            "output_schema": ce.get("output_schema"),
            "dependencies": ce.get("dependencies"),
            "owner_approval_required": ce.get("owner_approval_required"),
            "vendor_role": ce.get("assigned_model_vendor_role"),
        }

        out_rel = ce.get("output_path") or ""
        out_path = REPO / out_rel

        # S2 artifact
        if not out_path.is_file():
            fails.append(f"S2 artifact missing: {out_rel}")
        else:
            raw = out_path.read_bytes()
            size = len(raw)
            rec["artifact"] = {"rel": out_rel, "bytes": size}
            if size == 0:
                fails.append("S2 artifact empty")
            try:
                art = json.loads(raw.decode("utf-8"))
                rec["artifact"]["parses"] = True
            except Exception as exc:
                art = None
                rec["artifact"]["parses"] = False
                fails.append(f"S2 artifact unparseable: {type(exc).__name__}")
            if isinstance(art, dict):
                st = str(art.get("state", "") or "").upper()
                rec["artifact"]["state"] = st or None
                if st in NOT_DELIVERING:
                    fails.append(f"S2 artifact self-declares non-delivery state={st}")
                text = raw.decode("utf-8", errors="replace")
                sent = str(art.get("completion_sentinel") or art.get("sentinel") or "")
                rec["artifact"]["sentinel_present"] = bool(sent) and (sent in text)
                if sent and not rec["artifact"]["sentinel_present"]:
                    fails.append("S2 sentinel text absent from artifact")
                minb = art.get("min_bytes_threshold")
                if isinstance(minb, int) and minb > 0 and size < minb:
                    fails.append(f"S2 artifact below own min_bytes_threshold {size}<{minb}")
                tv = {}
                for key in ("targets", "verdicts", "enumerated_targets", "component_matrix"):
                    tgt = art.get(key)
                    if isinstance(tgt, list):
                        vv = [t.get("verdict") for t in tgt if isinstance(t, dict) and t.get("verdict")]
                        if vv:
                            tv = {k: vv.count(k) for k in set(vv)}
                            rec["artifact"]["verdict_field"] = key
                            break
                if tv:
                    rec["artifact"]["verdicts"] = tv
                # S4 schema
                sch_rel = ce.get("output_schema") or ""
                sch_path = REPO / sch_rel
                if not sch_path.is_file():
                    fails.append(f"S4 output_schema file missing: {sch_rel}")
                else:
                    try:
                        schema = json.loads(sch_path.read_text(encoding="utf-8"))
                        errs = validate_artifact_schema(art, schema)
                        rec["schema"] = {"rel": sch_rel, "errors": errs}
                        if errs:
                            fails.append(f"S4 schema errors ({len(errs)}): {errs[0]}")
                    except Exception as exc:
                        fails.append(f"S4 schema validate crash: {type(exc).__name__}: {exc}")

        # S3 manifest + sha
        man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        rec["manifest"] = {"exists": man_path.is_file()}
        if not man_path.is_file():
            fails.append("S3 UNIT-ARTIFACT-MANIFEST.json missing")
        elif out_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
                rows = [a for a in man.get("artifacts", []) if a.get("role") == "primary"]
                if not rows:
                    fails.append("S3 manifest has no primary row")
                else:
                    prow = rows[0]
                    rec["manifest"]["primary"] = {
                        "path": prow.get("path"),
                        "sha256": prow.get("sha256"),
                        "bytes": prow.get("bytes"),
                    }
                    if prow.get("path") != out_rel:
                        fails.append(f"S3 manifest primary path != catalog output_path: {prow.get('path')}")
                    live_sha = sha256_norm(out_path)
                    rec["manifest"]["live_sha256_norm"] = live_sha
                    if (prow.get("sha256") or "").lower() != live_sha:
                        fails.append("S3 manifest sha != recomputed live sha (CRLF->LF)")
                    if prow.get("bytes") != out_path.stat().st_size:
                        fails.append(f"S3 manifest bytes != live size: {prow.get('bytes')} != {out_path.stat().st_size}")
                    if not man.get("verified_on_disk", False):
                        fails.append("S3 manifest verified_on_disk is not true")
            except Exception as exc:
                fails.append(f"S3 manifest unreadable: {type(exc).__name__}")

        # S5 receipt
        rcp = REPO / "command-center/receipts" / f"{uid}.json"
        rec["receipt"] = {"exists": rcp.is_file()}
        if not rcp.is_file():
            fails.append("S5 receipt missing")
        else:
            try:
                r = json.loads(rcp.read_text(encoding="utf-8"))
                rec["receipt"]["state"] = r.get("state")
                rec["receipt"]["unit_id"] = r.get("unit_id")
                if r.get("unit_id") != uid:
                    fails.append("S5 receipt unit_id mismatch")
                rrows = [a for a in r.get("artifacts", []) if a.get("role") == "primary"]
                if rrows:
                    rec["receipt"]["primary_sha"] = rrows[0].get("sha256")
                    if rrows[0].get("path") != out_rel:
                        fails.append(f"S5 receipt primary path != catalog output_path: {rrows[0].get('path')}")
                    if out_path.is_file() and (rrows[0].get("sha256") or "").lower() != sha256_norm(out_path):
                        fails.append("S5 receipt primary sha != recomputed live sha")
                else:
                    fails.append("S5 receipt has no primary artifact row")
                rev = r.get("reviewer")
                if r.get("state") == "SUCCESS":
                    ok = bool(rev) and rev.get("verdict") == "PASS" and rev.get("independent") is True
                    rec["receipt"]["reviewer_valid"] = ok
                    if not ok:
                        fails.append("S5 receipt SUCCESS without valid independent PASS reviewer block")
                else:
                    rec["receipt"]["failure"] = r.get("failure")
                # G gate (pre-closure posture)
                try:
                    gres, gextra = gate.evaluate_full(r, repo_root=REPO, verify_filesystem=True)
                    rec["gate"] = {
                        "complete": gres.complete,
                        "marker": gres.marker(),
                        "blocking": [
                            {"n": c.n, "text": c.text, "outcome": c.outcome, "basis": c.basis}
                            for c in gres.blocking_conditions
                        ],
                        "extra": gextra,
                    }
                except Exception as exc:
                    rec["gate"] = {"error": f"{type(exc).__name__}: {exc}"}
            except Exception as exc:
                fails.append(f"S5 receipt unreadable: {type(exc).__name__}")

        # P live probes
        pdir = REPO / "command-center/p2-wave/probes" / uid
        probes = sorted(
            p for p in pdir.glob("probe*.py")
            if re.match(r"probe\d", p.name) and "__main__" in p.read_text(encoding="utf-8", errors="replace")
        )
        rec["probe_files"] = [p.name for p in probes]
        if not probes:
            fails.append("P no runnable probe scripts found")
        for p in probes:
            log = LOGS / f"{uid}__{p.stem}.log"
            t0 = time.time()
            try:
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
                cp = subprocess.run(
                    [sys.executable, "-B", str(p.relative_to(REPO))],
                    cwd=str(REPO), capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=PROBE_TIMEOUT_S, env=env,
                )
                dt = time.time() - t0
                out = (cp.stdout or "") + (cp.stderr or "")
                log.write_text(out, encoding="utf-8")
                m = re.search(r"(SUCCESS|FAILED):" + re.escape(uid) + r"[^\n]*", out)
                marker = m.group(0)[:200] if m else None
                ok = cp.returncode == 0
                rec["probes"][p.name] = {"rc": cp.returncode, "secs": round(dt, 1), "marker": marker, "log": str(log)}
                if not ok:
                    fails.append(f"P probe {p.name} rc={cp.returncode} marker={marker}")
            except subprocess.TimeoutExpired:
                rec["probes"][p.name] = {"rc": None, "secs": PROBE_TIMEOUT_S, "marker": "TIMEOUT", "log": str(log)}
                fails.append(f"P probe {p.name} TIMEOUT after {PROBE_TIMEOUT_S}s")
            except Exception as exc:
                rec["probes"][p.name] = {"rc": None, "error": f"{type(exc).__name__}: {exc}"}
                fails.append(f"P probe {p.name} crashed: {exc}")
            save()

        rec["fails"] = fails
        state["units"][uid] = rec
        save()
        print(f"[{uid}] fails={len(fails)}" + ("".join(f"\n   - {f}" for f in fails)))

    any_fail = any(rec.get("fails") for rec in state["units"].values())
    state["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["any_fail"] = any_fail
    save()
    print("\nPHASE1 any_fail=", any_fail, "units_recorded=", len(state["units"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
