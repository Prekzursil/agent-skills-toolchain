"""review:w3s24 (re-run r2) independent verification battery.

Adversarially verifies 8 units in ~/p2-g1 WITHOUT reusing the prior run's
verdicts. Per unit:
  C1 artifact   : output_path exists, non-empty, parses as JSON object
  C2 state      : state==SUCCESS, no failure object, sentinel not FAILED,
                  reviewer.verdict==PASS, reviewer.independent==True
  C3 manifest   : recomputed sha256(raw bytes, CRLF->LF) matches the
                  role=primary manifest row (path + present + unit_id)
  C4 probes     : every manifest named-probe re-executed by THIS reviewer,
                  exit 0 required; cross-checked against probe*.py on disk
  C5 schema     : receipt validates against the catalog output_schema
                  fragment via the program resolver (receipt_schema_gate)
Outputs one JSON + printed single-bit verdicts. NEVER writes to receipts,
probes, or manifests (read-only on the unit tree).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MINE = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
        "TST-0223", "TST-0227", "TST-0230", "TST-0233"]
OUT = Path(r"C:\Users\Prekzursil\p2-g1\_reviewer-w3s24-r2\battery_results.json")

# import the program's own schema resolver (SSOT validator)
sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as gate  # noqa: E402

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
cat_by_id = {u["id"]: u for u in cat["work_units"]}


def lf_sha(p: Path) -> str:
    raw = p.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


results: dict[str, dict] = {}
for uid in MINE:
    row: dict = {"unit_id": uid}
    checks: dict[str, bool] = {}
    entry = cat_by_id.get(uid)

    # --- resolve declared output_path / output_schema from catalog
    out_rel = entry["output_path"]
    out_abs = REPO / out_rel
    frag = gate.parse_schema_ref(entry["output_schema"])[1]
    frag_name = frag.lstrip("#").split("/")[-1] if frag else None
    row["output_path"] = out_rel
    row["schema_fragment"] = frag_name

    # C1 artifact
    try:
        raw_bytes = out_abs.read_bytes()
        row["bytes"] = len(raw_bytes)
        checks["artifact_exists_nonempty"] = len(raw_bytes) > 0
        doc = json.loads(raw_bytes.decode("utf-8"))
        checks["artifact_parses"] = isinstance(doc, dict)
    except Exception as exc:  # noqa: BLE001
        row["c1_error"] = f"{type(exc).__name__}: {exc}"
        checks["artifact_exists_nonempty"] = False
        checks["artifact_parses"] = False
        doc = None

    # C2 state / closure
    if isinstance(doc, dict):
        rev = doc.get("reviewer") or {}
        row["state"] = doc.get("state")
        row["sentinel_head"] = str(doc.get("sentinel", ""))[:20]
        row["reviewer_verdict"] = rev.get("verdict")
        row["reviewer_independent"] = rev.get("independent")
        row["has_failure_obj"] = doc.get("failure") is not None
        row["defects_open_p01"] = [
            d.get("id") for d in doc.get("defects", [])
            if d.get("status") == "open" and d.get("severity") in ("P0", "P1")
        ]
        checks["state_success"] = doc.get("state") == "SUCCESS"
        checks["not_blocked_failed"] = doc.get("state") not in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT")
        checks["no_failure_obj"] = doc.get("failure") is None
        checks["sentinel_not_failed"] = not str(doc.get("sentinel", "")).startswith("FAILED:")
        checks["reviewer_pass"] = rev.get("verdict") == "PASS"
        checks["reviewer_independent"] = rev.get("independent") is True
    else:
        checks["state_success"] = False

    # C3 manifest sha match
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    try:
        man = json.loads(man_path.read_bytes().decode("utf-8"))
        live_sha = lf_sha(out_abs)
        row["receipt_sha256_LF"] = live_sha
        want_rel = out_rel.replace("\\", "/")
        rows_match = [
            a for a in man.get("artifacts", [])
            if a.get("role") == "primary"
            and str(a.get("path", "")).replace("\\", "/") == want_rel
            and a.get("present") is True
            and a.get("unit_id") == uid
            and a.get("sha256") == live_sha
        ]
        checks["manifest_primary_sha_match"] = bool(rows_match)
        row["manifest_expected_present"] = (man.get("expected"), man.get("present"))
        named_probes = sorted(
            str(a.get("path", "")).replace("\\", "/").split("/")[-1]
            for a in man.get("artifacts", []) if a.get("role") == "named-probe"
        )
        row["manifest_named_probes"] = named_probes
    except Exception as exc:  # noqa: BLE001
        row["c3_error"] = f"{type(exc).__name__}: {exc}"
        checks["manifest_primary_sha_match"] = False
        named_probes = []

    # C4 probes: re-run every named-probe myself (exit 0 required)
    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    disk_probes = sorted(
        p.name for p in probe_dir.glob("probe*.py")
    ) if probe_dir.is_dir() else []
    row["disk_probe_files"] = disk_probes
    checks["probe_inventory_matches_manifest"] = disk_probes == named_probes
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    rcs = []
    for pname in disk_probes:
        try:
            pr = subprocess.run(
                [sys.executable, "-B", str(probe_dir / pname)],
                cwd=str(REPO), capture_output=True, text=True,
                timeout=900, env=env,
            )
            rcs.append({pname: pr.returncode})
            if pr.returncode != 0:
                row.setdefault("probe_fail_tail", {})[pname] = (pr.stdout or "")[-800:] + " | STDERR: " + (pr.stderr or "")[-800:]
        except subprocess.TimeoutExpired:
            rcs.append({pname: "TIMEOUT"})
    row["probe_rcs"] = rcs
    checks["probes_all_exit0"] = bool(rcs) and all(
        next(iter(d.values())) == 0 for d in rcs
    )

    # C5 schema via program resolver
    try:
        errs = gate.validate_receipt(doc, fragment=frag_name)
        row["schema_errors"] = errs[:20]
        row["schema_error_count"] = len(errs)
        checks["schema_valid"] = len(errs) == 0
    except Exception as exc:  # noqa: BLE001
        row["c5_error"] = f"{type(exc).__name__}: {exc}"
        checks["schema_valid"] = False

    row["checks"] = checks
    failed = sorted(k for k, v in checks.items() if not v)
    row["failed_checks"] = failed
    row["verdict"] = "PASS" if not failed else "FAIL"
    results[uid] = row
    print(f"{uid} | verdict: {row['verdict']} | failed: {failed or 'none'}")

OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
print()
print("RESULTS:", OUT)
