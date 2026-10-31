#!/usr/bin/env python3
"""Wave-2 shard-11 INDEPENDENT REVIEWER battery (12 units).

Re-verifies, per unit, with fresh instrumentation:
  1. receipt artifact at the catalog output_path: exists, non-empty, parses,
     not self-declared BLOCKED/FAILED (state==SUCCESS)
  2. reviewer verdict PASS + independent=true present (receipt_core rule)
  3. probes/<id>/UNIT-ARTIFACT-MANIFEST.json: every row re-hashed against the
     live file with CRLF->LF normalization (contract hash), bytes compared,
     eol observation recorded; a primary row must exist
  4. the receipt's own `artifacts` rows re-hashed the same way (extra check)
  5. live probes re-run in this process tree: exit 0 AND a SUCCESS:<unit-id>
     sentinel on stdout (vacuity guard: a green run must name the unit)
  6. the program's own gate (platform/lib/receipt_schema_gate.py):
     layer-1 receipt.schema.json validation (external receipt_core $ref
     resolved) + the 12-condition completion predicate + coherence checks
  7. admission cross-instrument: command-center/receipt_validate.py ACCEPT
  8. IMP-0096 only: benchmark_record validated against
     tools/marketplace/schema/benchmark-evidence.schema.json

CONFIRM-ONLY: this battery never writes to receipts, manifests or artifacts.
Exit 0 only if ALL 12 units hold; exit 1 lists every failing check.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
IDS = [
    "IMP-0095", "IMP-0096", "IMP-0102", "IMP-0107", "IMP-0122", "IMP-0133",
    "IMP-0138", "IMP-0146", "IMP-0151", "IMP-0153", "IMP-0160", "IMP-0161",
]
PROBE_TIMEOUT = 300

GATE_PATH = REPO / "platform/lib/receipt_schema_gate.py"
spec = importlib.util.spec_from_file_location("rsg", GATE_PATH)
rsg = importlib.util.module_from_spec(spec)
sys.modules["rsg"] = rsg
spec.loader.exec_module(rsg)


def hashes(path: Path) -> tuple[str, str, int, int, str]:
    """Return (raw_sha, norm_sha, raw_len, norm_len, eol_observed)."""
    data = path.read_bytes()
    raw = hashlib.sha256(data).hexdigest()
    norm_data = data.replace(b"\r\n", b"\n")
    norm = hashlib.sha256(norm_data).hexdigest()
    eol = "LF" if b"\r\n" not in data else ("CRLF" if b"\n" in data else "none")
    return raw, norm, len(data), len(norm_data), eol


def check_row(row: dict) -> tuple[bool, str]:
    """One manifest/receipt artifact row vs the live file (contract hash)."""
    rel = row.get("path", "")
    p = REPO / rel
    if not p.exists():
        return False, f"{rel}: MISSING on disk"
    raw, norm, raw_len, norm_len, eol = hashes(p)
    if norm_len == 0:
        return False, f"{rel}: EMPTY"
    want = row.get("sha256")
    if norm != want:
        return False, f"{rel}: sha256(LF) {norm} != recorded {want}"
    want_bytes = row.get("bytes")
    if isinstance(want_bytes, int) and want_bytes != norm_len:
        return False, f"{rel}: bytes(LF) {norm_len} != recorded {want_bytes}"
    row_eol = row.get("eol")
    if row_eol and row_eol != eol:
        return False, f"{rel}: observed eol {eol} != recorded {row_eol}"
    return True, f"{rel}: OK ({norm_len}B LF sha256 match, observed {eol})"


def run_probe(uid: str, probe: Path) -> tuple[bool, str]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    t0 = time.monotonic()
    try:
        cp = subprocess.run(
            [sys.executable, "-B", str(probe)],
            cwd=str(REPO), capture_output=True, text=True,
            timeout=PROBE_TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"{probe.name}: TIMEOUT after {PROBE_TIMEOUT}s"
    dt = time.monotonic() - t0
    if cp.returncode != 0:
        return False, (f"{probe.name}: rc={cp.returncode} "
                       f"stderr={cp.stderr.strip()[:300]!r}")
    if f"SUCCESS:{uid}" not in cp.stdout:
        return False, (f"{probe.name}: rc=0 but no SUCCESS:{uid} sentinel "
                       f"(stdout tail {cp.stdout.strip()[-160:]!r})")
    if not cp.stdout.strip():
        return False, f"{probe.name}: rc=0 but EMPTY stdout"
    return True, f"{probe.name}: rc=0 sentinel OK ({dt:.2f}s, {len(cp.stdout)}B out)"


def main() -> int:
    all_ok = True
    summary: list[str] = []
    for uid in IDS:
        checks: list[tuple[bool, str, str]] = []  # (ok, check, detail)

        # --- 1+2. receipt artifact ---------------------------------------- #
        rpath = REPO / "command-center/receipts" / f"{uid}.json"
        receipt = None
        if not rpath.exists():
            checks.append((False, "receipt-exists", str(rpath)))
        else:
            raw = rpath.read_bytes()
            checks.append((len(raw) > 0, "receipt-nonempty", f"{len(raw)}B"))
            try:
                receipt = json.loads(raw.decode("utf-8"))
                checks.append((True, "receipt-parses", "json ok"))
            except Exception as exc:
                checks.append((False, "receipt-parses", str(exc)))
            if receipt is not None:
                state = receipt.get("state")
                checks.append((state == "SUCCESS", "receipt-state",
                               f"state={state}"))
                rev = receipt.get("reviewer") or {}
                ok_rev = (rev.get("verdict") == "PASS"
                          and rev.get("independent") is True)
                checks.append((ok_rev, "reviewer-pass-independent",
                               f"verdict={rev.get('verdict')} "
                               f"independent={rev.get('independent')} "
                               f"reviewer_id={rev.get('reviewer_id')}"))
                sentinel = (receipt.get("sentinel")
                            or receipt.get("completion_sentinel") or "")
                checks.append((uid in sentinel, "sentinel-embeds-id",
                               repr(sentinel)))

        # --- 3. per-unit manifest rows ------------------------------------ #
        mpath = (REPO / "command-center/p2-wave/probes" / uid /
                 "UNIT-ARTIFACT-MANIFEST.json")
        if not mpath.exists():
            checks.append((False, "manifest-exists", str(mpath)))
        else:
            try:
                man = json.loads(mpath.read_bytes().decode("utf-8"))
                checks.append((True, "manifest-parses", "json ok"))
            except Exception as exc:
                man = None
                checks.append((False, "manifest-parses", str(exc)))
            if man is not None:
                rows = man.get("artifacts") or []
                checks.append((bool(rows), "manifest-has-rows",
                               f"{len(rows)} rows"))
                primaries = [r for r in rows
                             if r.get("role") == "primary"]
                checks.append((bool(primaries), "manifest-primary-row",
                               f"{len(primaries)} primary"))
                for row in rows:
                    ok, detail = check_row(row)
                    checks.append((ok, "manifest-row-hash", detail))

        # --- 4. receipt's own artifact rows ------------------------------- #
        if receipt is not None:
            for row in receipt.get("artifacts") or []:
                ok, detail = check_row(row)
                checks.append((ok, "receipt-artifact-row", detail))

        # --- 5. live probes ----------------------------------------------- #
        pdir = REPO / "command-center/p2-wave/probes" / uid
        probes = sorted(pdir.glob("probe*.py"))
        checks.append((len(probes) >= 2, "probe-count>=2", f"{len(probes)}"))
        for probe in probes:
            ok, detail = run_probe(uid, probe)
            checks.append((ok, "live-probe", detail))

        # --- 6. program gate: layer1 + 12-condition predicate ------------- #
        if receipt is not None:
            try:
                result, extra = rsg.evaluate_full(
                    receipt, repo_root=REPO, verify_filesystem=True)
                checks.append((not result.schema_errors, "gate-layer1-schema",
                               "; ".join(result.schema_errors[:3])
                               or "no schema errors"))
                for c in result.conditions:
                    checks.append(
                        (not c.blocking, f"gate-cond-{c.n}",
                         f"{c.outcome}: {c.text} [{c.basis}]"))
                for e in extra:
                    checks.append((False, "gate-coherence", e))
                if not extra:
                    checks.append((True, "gate-coherence", "no coherence errors"))
            except Exception as exc:
                checks.append((False, "gate-run", f"gate raised: {exc}"))

        # --- 7. admission cross-instrument -------------------------------- #
        try:
            cp = subprocess.run(
                [sys.executable, "-B", "command-center/receipt_validate.py",
                 f"command-center/receipts/{uid}.json"],
                cwd=str(REPO), capture_output=True, text=True, timeout=120,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            accepted = cp.returncode == 0 and "ACCEPT" in cp.stdout
            checks.append((accepted, "admission-receipt-validate",
                           cp.stdout.strip().splitlines()[-1][:160]
                           if cp.stdout.strip() else f"rc={cp.returncode}"))
        except Exception as exc:
            checks.append((False, "admission-receipt-validate", str(exc)))

        # --- 8. IMP-0096 benchmark evidence schema ------------------------ #
        if uid == "IMP-0096" and receipt is not None:
            try:
                from jsonschema import Draft202012Validator
                bench_schema = json.loads(
                    (REPO / "tools/marketplace/schema/"
                     "benchmark-evidence.schema.json").read_bytes()
                    .decode("utf-8"))
                record = receipt.get("benchmark_record")
                if not isinstance(record, dict):
                    checks.append((False, "benchmark-evidence-schema",
                                   "receipt has no benchmark_record object"))
                else:
                    errs = sorted(Draft202012Validator(bench_schema)
                                  .iter_errors(record),
                                  key=lambda e: list(e.path))
                    checks.append((not errs, "benchmark-evidence-schema",
                                   "; ".join(e.message for e in errs[:3])
                                   or "record valid"))
            except Exception as exc:
                checks.append((False, "benchmark-evidence-schema",
                               f"validator raised: {exc}"))

        bad = [(c, d) for ok, c, d in checks if not ok]
        verdict = "PASS" if not bad else "FAIL"
        if bad:
            all_ok = False
        summary.append(f"{uid}: {verdict} ({len(checks) - len(bad)}/"
                       f"{len(checks)} checks hold)")
        print(f"=== {uid}: {verdict} ===")
        for ok, c, d in checks:
            mark = "ok " if ok else "FAIL"
            print(f"  [{mark}] {c}: {d}")

    print()
    for line in summary:
        print(line)
    print("BATTERY:" + ("ALL-PASS" if all_ok else "HAS-FAILURES"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
