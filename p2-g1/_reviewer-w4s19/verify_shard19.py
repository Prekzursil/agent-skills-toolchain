#!/usr/bin/env python3
"""Independent reviewer battery -- wave 4 shard 19 (12 TST units).

For each unit:
  A. static receipt checks (exists / non-empty / parses / not self-blocked /
     state SUCCESS / receipt_core rule reviewer.verdict=PASS + independent=true)
  B. manifest: probes/<uid>/UNIT-ARTIFACT-MANIFEST.json has a row for the
     catalog output_path; sha256 recomputed with CRLF->LF normalization matches;
     byte size matches; supporting probe-file rows also match (pins the exact
     bytes before we execute them)
  C. live probe re-run: every registered probe*.py re-executed from the repo
     root; exit 0 required
  D. output_schema validation via the program's own resolver
     (platform/lib/schema_resolver.validate_artifact)
  E. informational: dependency receipt states

Receipts are NOT modified (an existing valid PASS closure stays SUCCESS;
editing a receipt would invalidate its manifest-registered sha256).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUTDIR = REPO / "_reviewer-w4s19"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

UNITS = [
    "TST-0109", "TST-0113", "TST-0116", "TST-0124",
    "TST-0136", "TST-0137", "TST-0138", "TST-0139",
    "TST-0141", "TST-0142", "TST-0143", "TST-0144",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 600


def norm_sha(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    from schema_resolver import validate_artifact  # noqa: E402

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    wu = {u["id"]: u for u in cat["work_units"]}

    results: dict[str, dict] = {}
    n_pass = 0
    for uid in UNITS:
        r: dict = {"checks": {}, "info": {}}
        fails: list[str] = []
        entry = wu.get(uid)
        if entry is None:
            results[uid] = {"verdict": "FAIL", "fails": ["catalog-entry-missing"]}
            print(f"{uid} FAIL catalog-entry-missing")
            continue
        out_rel = str(entry["output_path"]).replace("\\", "/")
        out_abs = REPO / out_rel
        schema_ref = entry.get("output_schema")
        sentinel_cat = entry.get("completion_sentinel")

        # A. static receipt checks
        if not out_abs.exists():
            fails.append(f"receipt-missing:{out_rel}")
        else:
            raw = out_abs.read_bytes()
            r["checks"]["receipt_bytes"] = len(raw)
            if len(raw) == 0:
                fails.append("receipt-empty")
            try:
                doc = json.loads(raw)
                r["checks"]["parses"] = True
            except Exception as exc:
                fails.append(f"receipt-parse:{type(exc).__name__}")
                doc = None
            if doc is not None:
                st = str(doc.get("state") or "").upper()
                r["checks"]["state"] = st
                if st in NOT_DELIVERING:
                    fails.append(f"self-declared:{st}")
                if st != "SUCCESS":
                    fails.append(f"state-not-success:{st}")
                rev = doc.get("reviewer") or {}
                verd = str(rev.get("verdict") or "").upper()
                indep = bool(rev.get("independent"))
                r["checks"]["reviewer_verdict"] = verd
                r["checks"]["reviewer_independent"] = indep
                if st == "SUCCESS" and (verd != "PASS" or not indep):
                    fails.append(
                        f"receipt_core-success-without-independent-pass:"
                        f"verdict={verd},independent={indep}"
                    )
                uid_field = str(doc.get("unit_id") or doc.get("id") or "")
                if uid_field != uid:
                    fails.append(f"unit-id-mismatch:{uid_field}")
                sent_field = str(
                    doc.get("sentinel") or doc.get("completion_sentinel") or ""
                )
                if sentinel_cat and sent_field and sent_field != sentinel_cat:
                    r["info"]["sentinel_drift"] = f"{sent_field} vs catalog {sentinel_cat}"
                if sentinel_cat and sentinel_cat not in raw.decode("utf-8", "replace"):
                    fails.append(f"sentinel-absent:{sentinel_cat}")
                # self-block residue: explicit failure block declaring BLOCKED
                fr = doc.get("failure") or doc.get("failure_report")
                if isinstance(fr, dict) and str(fr.get("state", "")).upper() in NOT_DELIVERING:
                    fails.append("embedded-failure-block")

        # B. manifest + sha256 (CRLF->LF)
        man_rel = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        man_abs = REPO / man_rel
        probe_files: list[Path] = []
        if not man_abs.exists():
            fails.append(f"manifest-missing:{man_rel}")
        else:
            try:
                man = json.loads(man_abs.read_bytes())
            except Exception as exc:
                man = None
                fails.append(f"manifest-parse:{type(exc).__name__}")
            if man is not None:
                rows = man.get("artifacts") or []
                prim = [a for a in rows if str(a.get("path", "")).replace("\\", "/") == out_rel]
                if not prim:
                    fails.append(f"manifest-no-primary-row:{out_rel}")
                else:
                    p = prim[0]
                    if not out_abs.exists():
                        fails.append("artifact-missing-for-hash")
                    else:
                        live_raw = out_abs.read_bytes()
                        live_norm = live_raw.replace(b"\r\n", b"\n")
                        live = hashlib.sha256(live_norm).hexdigest()
                        r["checks"]["sha_primary_match"] = live == p.get("sha256")
                        if live != p.get("sha256"):
                            fails.append(
                                f"sha-mismatch:live={live[:12]},manifest={str(p.get('sha256'))[:12]}"
                            )
                        # manifest bytes are LF-normalized lengths (builder
                        # convention per _measure_one_delivered.py), so compare
                        # against the normalized length, not raw st_size
                        if p.get("bytes") != len(live_norm):
                            fails.append(
                                f"byte-mismatch:live_norm={len(live_norm)},manifest={p.get('bytes')}"
                            )
                for a in rows:
                    a_rel = str(a.get("path", "")).replace("\\", "/")
                    a_abs = REPO / a_rel
                    if a_rel.endswith(".py"):
                        probe_files.append(a_abs)
                    if not a_abs.exists():
                        fails.append(f"manifest-row-missing-on-disk:{a_rel}")
                        continue
                    live_a = norm_sha(a_abs.read_bytes())
                    if live_a != a.get("sha256"):
                        fails.append(f"sha-mismatch-supporting:{a_rel}")
        r["checks"]["probes_registered"] = [str(p.name) for p in probe_files]

        # C. live probe re-run (exit 0 required)
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        probe_results = {}
        for pf in probe_files:
            try:
                proc = subprocess.run(
                    [sys.executable, "-B", str(pf)],
                    cwd=str(REPO), env=env, capture_output=True,
                    text=True, timeout=PROBE_TIMEOUT_S,
                )
                tail = (proc.stdout or "").strip().splitlines()
                marker = tail[-1] if tail else ""
                probe_results[pf.name] = {
                    "rc": proc.returncode, "marker": marker[:160],
                    "stderr_tail": (proc.stderr or "").strip().splitlines()[-1:],
                }
                if proc.returncode != 0:
                    fails.append(f"probe-nonzero:{pf.name}:rc={proc.returncode}:{marker[:80]}")
            except subprocess.TimeoutExpired:
                probe_results[pf.name] = {"rc": "TIMEOUT"}
                fails.append(f"probe-timeout:{pf.name}")
        r["checks"]["probe_results"] = probe_results

        # D. schema validation via program resolver
        if doc is not None:
            try:
                errs = validate_artifact(doc, schema_ref)
            except Exception as exc:
                errs = [f"resolver-exception:{type(exc).__name__}:{exc}"]
            r["checks"]["schema_errors"] = errs[:10]
            r["checks"]["schema_error_count"] = len(errs)
            if errs:
                fails.append(f"schema-errors:{len(errs)}:{errs[0][:120]}")

        # E. informational dependency states
        deps = entry.get("dependencies") or []
        dep_states = {}
        for d in deps:
            d_path = REPO / "command-center" / "receipts" / f"{d}.json"
            if d_path.exists():
                try:
                    dep_states[d] = json.loads(d_path.read_bytes()).get("state")
                except Exception:
                    dep_states[d] = "UNPARSEABLE"
            else:
                dep_states[d] = "NO-RECEIPT"
        r["info"]["dependencies"] = dep_states

        verdict = "PASS" if not fails else "FAIL"
        r["verdict"] = verdict
        r["fails"] = fails
        results[uid] = r
        if verdict == "PASS":
            n_pass += 1
        print(f"{uid} {verdict} bytes={r['checks'].get('receipt_bytes')} "
              f"state={r['checks'].get('state')} probes={len(probe_files)} "
              f"schema_err={r['checks'].get('schema_error_count')} fails={fails}")

    (OUTDIR / "verify_results.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8"
    )
    print(f"\nSUMMARY {n_pass}/{len(UNITS)} PASS")
    print("SUCCESS:w4s19-review-battery" if n_pass == len(UNITS)
          else "FAILED:w4s19-review-battery")
    return 0 if n_pass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
