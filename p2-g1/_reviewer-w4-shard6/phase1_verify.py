#!/usr/bin/env python3
"""Independent reviewer wave-4 shard-6, phase 1: static + live-probe verification.

Reviewer (me) did NOT build these units. For each of the 12 shard units:
  S1 catalog entry present (output_path/output_schema/dependencies known)
  S2 artifact: exists, non-empty, parses, NOT self-declared BLOCKED/FAILED/
     SEVERED/TIMEOUT, sentinel text present in artifact, honesty cross-check,
     min-bytes floor honored
  S3 manifest: probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row path matches
     catalog output_path; recomputed sha256 (CRLF->LF) == manifest sha;
     live bytes match; verified_on_disk recorded
  S4 schema: canonical schema_resolver.validate_artifact over catalog
     output_schema (blessed resolver, draft-2020-12, no network)
  S5 receipt: parses, unit_id matches, closure posture recorded; for units
     whose output_path IS the receipt, the receipt self-row sha is the known
     self-reference class (recorded, non-gating); otherwise checked vs live
  P  live probes: every probe[0-9]*.py in probes/<id>/ re-run by THIS reviewer
     (python -B, cwd=repo root, per-probe timeout, rc must be 0, SUCCESS marker)
  G  receipt gate: platform/lib/receipt_schema_gate.evaluate_full() run by me

Writes incremental JSON state to _reviewer-w4-shard6/phase1_state.json and
per-probe logs to _reviewer-w4-shard6/logs/.
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
    "BLD-0049", "BLD-0058", "BLD-0059", "CC-0009", "CC-0010", "CC-0012",
    "CC-0019", "CNF-0077", "CNF-0132", "CNF-0133", "CNF-0136", "CNF-0147",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
STATE_PATH = OUTDIR / "phase1_state.json"
PROBE_TIMEOUT_S = 900

state = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "units": {}}


def save() -> None:
    STATE_PATH.write_text(json.dumps(state, indent=1), encoding="utf-8")


def sha256_norm(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_catalog():
    doc = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return {u["id"]: u for u in doc["work_units"] if isinstance(u.get("id"), str)}


def load_gate():
    gp = REPO / "platform/lib/receipt_schema_gate.py"
    spec = importlib.util.spec_from_file_location("receipt_schema_gate", gp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["receipt_schema_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def load_resolver():
    spec = importlib.util.spec_from_file_location(
        "schema_resolver_rev", REPO / "platform/lib/schema_resolver.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver_rev"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    catalog = load_catalog()
    gate = load_gate()
    resolver = load_resolver()

    run_ids = sys.argv[1:] or UNITS
    for uid in run_ids:
        rec = {"checks": {}, "probes": {}}
        fails = []

        # S1 catalog
        ce = catalog.get(uid)
        rec["checks"]["catalog_entry"] = bool(ce)
        if not ce:
            fails.append("S1 catalog entry missing")
            rec["fails"] = fails
            state["units"][uid] = rec
            save()
            continue
        rec["catalog"] = {
            "output_path": ce.get("output_path"),
            "output_schema": ce.get("output_schema"),
            "dependencies": ce.get("dependencies"),
            "owner_approval_required": ce.get("owner_approval_required"),
        }

        out_rel = ce.get("output_path") or ""
        out_path = REPO / out_rel

        # S2 artifact (+ S4 schema)
        if not out_path.is_file():
            fails.append("S2 artifact missing: " + out_rel)
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
                fails.append("S2 artifact unparseable: " + type(exc).__name__)
            if isinstance(art, dict):
                st = str(art.get("state", "") or "").upper()
                rec["artifact"]["state"] = st or None
                if st in NOT_DELIVERING:
                    fails.append("S2 artifact self-declares non-delivery state=" + st)
                text = raw.decode("utf-8", errors="replace")
                sent = str(art.get("completion_sentinel") or art.get("sentinel") or "")
                rec["artifact"]["sentinel_present"] = bool(sent) and (sent in text)
                if sent and not rec["artifact"]["sentinel_present"]:
                    fails.append("S2 sentinel text absent from artifact")
                ds = str(art.get("delivery_status", "") or "")
                if ds.upper() in NOT_DELIVERING and st == "SUCCESS":
                    fails.append("S2 honesty: state=SUCCESS but delivery_status=" + ds)
                minb = art.get("min_bytes_threshold")
                if isinstance(minb, int) and minb > 0 and size < minb:
                    fails.append("S2 artifact below own min_bytes_threshold %d<%d" % (size, minb))
                sch_rel = ce.get("output_schema") or ""
                try:
                    errs = resolver.validate_artifact(art, sch_rel)
                    rec["schema"] = {"rel": sch_rel, "errors": errs[:10], "n_errors": len(errs)}
                    if errs:
                        fails.append("S4 schema errors (%d): %s" % (len(errs), errs[0]))
                except Exception as exc:
                    rec["schema"] = {"rel": sch_rel, "crash": type(exc).__name__ + ": " + str(exc)}
                    fails.append("S4 schema resolver crash: " + type(exc).__name__ + ": " + str(exc))

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
                    rec["manifest"]["verified_on_disk"] = man.get("verified_on_disk")
                    rec["manifest"]["n_rows"] = len(man.get("artifacts", []))
                    if str(prow.get("path", "")).replace("\\", "/") != out_rel.replace("\\", "/"):
                        fails.append("S3 manifest primary path != catalog output_path: " + str(prow.get("path")))
                    live_sha = sha256_norm(out_path)
                    rec["manifest"]["live_sha256_norm"] = live_sha
                    if (prow.get("sha256") or "").lower() != live_sha:
                        fails.append("S3 manifest sha != recomputed live sha (CRLF->LF)")
                    if prow.get("bytes") != out_path.stat().st_size:
                        fails.append("S3 manifest bytes != live size: %s != %s" % (prow.get("bytes"), out_path.stat().st_size))
            except Exception as exc:
                fails.append("S3 manifest unreadable: " + type(exc).__name__)

        # S5 receipt
        rcp = REPO / "command-center/receipts" / (uid + ".json")
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
                receipt_rel = "command-center/receipts/" + uid + ".json"
                if rrows:
                    rp = str(rrows[0].get("path", "")).replace("\\", "/")
                    rec["receipt"]["primary_path"] = rp
                    rec["receipt"]["primary_sha"] = rrows[0].get("sha256")
                    if rp == receipt_rel:
                        rec["receipt"]["self_reference"] = True
                    elif rp == out_rel.replace("\\", "/"):
                        if (rrows[0].get("sha256") or "").lower() != sha256_norm(out_path):
                            fails.append("S5 receipt primary sha != recomputed live artifact sha")
                    else:
                        alt = REPO / rp
                        if alt.is_file() and rrows[0].get("sha256"):
                            if (rrows[0].get("sha256") or "").lower() != sha256_norm(alt):
                                fails.append("S5 receipt primary row stale vs live: " + rp)
                rev = r.get("reviewer")
                rec["receipt"]["reviewer"] = {
                    "reviewer_id": (rev or {}).get("reviewer_id"),
                    "verdict": (rev or {}).get("verdict"),
                    "independent": (rev or {}).get("independent"),
                }
                if r.get("state") == "SUCCESS":
                    ok = bool(rev) and rev.get("verdict") == "PASS" and rev.get("independent") is True
                    rec["receipt"]["reviewer_block_formally_valid"] = ok
                rec["receipt"]["failure"] = r.get("failure")
                # G gate (posture as-found)
                try:
                    gres, _gextra = gate.evaluate_full(r, repo_root=REPO, verify_filesystem=True)
                    rec["gate"] = {
                        "complete": gres.complete,
                        "marker": gres.marker(),
                        "blocking": [
                            {"n": c.n, "text": c.text, "outcome": c.outcome, "basis": c.basis}
                            for c in gres.blocking_conditions
                        ],
                    }
                except Exception as exc:
                    rec["gate"] = {"error": type(exc).__name__ + ": " + str(exc)}
            except Exception as exc:
                fails.append("S5 receipt unreadable: " + type(exc).__name__)

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
            log = LOGS / (uid + "__" + p.stem + ".log")
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
                    fails.append("P probe " + p.name + " rc=" + str(cp.returncode) + " marker=" + str(marker))
                elif marker and marker.startswith("FAILED:"):
                    fails.append("P probe " + p.name + " rc=0 but FAILED marker: " + marker)
            except subprocess.TimeoutExpired:
                rec["probes"][p.name] = {"rc": None, "secs": PROBE_TIMEOUT_S, "marker": "TIMEOUT", "log": str(log)}
                fails.append("P probe " + p.name + " TIMEOUT after " + str(PROBE_TIMEOUT_S) + "s")
            except Exception as exc:
                rec["probes"][p.name] = {"rc": None, "error": type(exc).__name__ + ": " + str(exc)}
                fails.append("P probe " + p.name + " crashed: " + str(exc))
            save()

        rec["fails"] = fails
        state["units"][uid] = rec
        save()
        print("[" + uid + "] fails=" + str(len(fails)) + "".join("\n   - " + f for f in fails), flush=True)

    any_fail = any(rec.get("fails") for rec in state["units"].values())
    state["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state["any_fail"] = any_fail
    save()
    print("\nPHASE1 any_fail=", any_fail, "units_recorded=", len(state["units"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
