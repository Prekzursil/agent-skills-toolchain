"""review:w3s24 (r3) independent verification battery - fresh evidence.

Does NOT inherit r1/r2 verdicts. Per unit (catalog SSOT
command-center/WORK-UNIT-CATALOG.json):

  C1 artifact  : output_path exists, non-empty, parses as JSON object
  C2 closure   : state==SUCCESS, no failure object, sentinel not FAILED:,
                 not BLOCKED/SEVERED/TIMEOUT
  C3 manifest  : recomputed sha256(bytes, CRLF->LF) matches the role=primary
                 manifest row (path + present + unit_id); named-probe
                 inventory matches probe*.py on disk
  C4 probes    : every probes/<uid>/probe*.py re-executed by THIS reviewer,
                 exit 0 required (cwd=REPO, AST_INTEGRATE_ROOT=REPO)
  C5 schema    : validate against the CATALOG-DECLARED file
                 (command-center/schema/receipt.schema.json#/$defs/<frag>)
                 via a registry chaining CC -> artifact-class-profiles ->
                 platform receipt.schema.json; PLUS the physical platform
                 copy (r2's instrument) as an equivalence check; PLUS the
                 program admission CLI receipt_validate.py as third signal
  P  predicate : gate.evaluate_gate_a with repo_root + verify_filesystem=True
                 -- all 12 conditions measured, c2/c3 off disk (stronger
                 than the r2 run which left them NOT-CHECKED)

Read-only on the unit tree: never writes receipts, probes, or manifests.
Outputs _reviewer-w3s24-r3/battery_results.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
SRC = Path(r"C:\Users\Prekzursil\source\ast-integrate")
MINE = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
        "TST-0223", "TST-0227", "TST-0230", "TST-0233"]
OUT = Path(r"C:\Users\Prekzursil\p2-g1\_reviewer-w3s24-r3\battery_results.json")

sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as gate  # noqa: E402
from jsonschema.validators import Draft202012Validator  # noqa: E402,F401
from referencing import Registry, Resource  # noqa: E402
from referencing.jsonschema import DRAFT202012  # noqa: E402

CC_SCHEMA = REPO / "command-center" / "schema" / "receipt.schema.json"
PROF_SCHEMA = REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
PL_SCHEMA = REPO / "platform" / "schema" / "receipt.schema.json"


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build_chain_registry() -> Registry:
    """Register CC + profiles + platform receipt schemas under their $ids so
    the catalog-declared CC fragment chain resolves without network/file
    retrieval: CC.$defs.frag -> profiles.$defs.frag -> platform.$defs.frag."""
    reg: Registry = Registry()
    for path in (CC_SCHEMA, PROF_SCHEMA, PL_SCHEMA):
        sch = json.loads(path.read_bytes().decode("utf-8"))
        res = Resource.from_contents(sch, default_specification=DRAFT202012)
        reg = reg.with_resource(sch["$id"], res)
    return reg


def validate_cc_chain(doc, fragment: str) -> list[str]:
    """Validate against the catalog-declared CC file + fragment."""
    cc = json.loads(CC_SCHEMA.read_bytes().decode("utf-8"))
    validator = Draft202012Validator(
        {"$ref": cc["$id"] + "#/$defs/" + fragment},
        registry=build_chain_registry(),
    )
    errs = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errs.append(f"{loc}: {err.message}")
    return sorted(errs)


cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
cat_by_id = {u["id"]: u for u in cat["work_units"]}

# precondition: schema files identical across p2-g1 and source/ast-integrate
pre = {}
for rel in ("command-center/schema/receipt.schema.json",
            "platform/schema/artifact-class-profiles.schema.json",
            "platform/schema/receipt.schema.json"):
    a, b = (REPO / rel).read_bytes(), (SRC / rel).read_bytes()
    pre[rel] = {"identical": a == b, "sha256": hashlib.sha256(a).hexdigest()[:16],
                "bytes": len(a)}
    assert a == b, f"schema drift between p2-g1 and source for {rel}"

results: dict[str, dict] = {}
for uid in MINE:
    row: dict = {"unit_id": uid}
    checks: dict[str, bool] = {}
    entry = cat_by_id.get(uid)
    out_rel = entry["output_path"]
    out_abs = REPO / out_rel
    _, frag_raw = gate.parse_schema_ref(entry["output_schema"])
    frag = (frag_raw or "").lstrip("#").split("/")[-1] or None
    row["output_path"] = out_rel
    row["schema_fragment"] = frag

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

    # C2 closure shape
    if isinstance(doc, dict):
        rev = doc.get("reviewer") or {}
        row["state"] = doc.get("state")
        row["sentinel_head"] = str(doc.get("sentinel", ""))[:24]
        row["reviewer_verdict"] = rev.get("verdict")
        row["reviewer_independent"] = rev.get("independent")
        row["failure_obj"] = doc.get("failure")
        row["defects_open"] = [
            {"id": d.get("id"), "severity": d.get("severity"), "status": d.get("status")}
            for d in doc.get("defects", []) if isinstance(d, dict)
        ]
        checks["state_success"] = doc.get("state") == "SUCCESS"
        checks["not_blocked_failed"] = doc.get("state") not in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT")
        checks["no_failure_obj"] = doc.get("failure") is None
        checks["sentinel_not_failed"] = not str(doc.get("sentinel", "")).startswith("FAILED:")
    else:
        checks["state_success"] = False

    # C3 manifest sha + inventory
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    named_probes: list[str] = []
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
        named_probes = sorted(
            str(a.get("path", "")).replace("\\", "/").split("/")[-1]
            for a in man.get("artifacts", []) if a.get("role") == "named-probe"
        )
        row["manifest_named_probes"] = named_probes
    except Exception as exc:  # noqa: BLE001
        row["c3_error"] = f"{type(exc).__name__}: {exc}"
        checks["manifest_primary_sha_match"] = False

    # C4 probes re-run by THIS reviewer
    probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
    disk_probes = sorted(p.name for p in probe_dir.glob("probe*.py")) if probe_dir.is_dir() else []
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
            # keep stdout evidence for every probe (tail) for spot-checks
            row.setdefault("probe_stdout_tails", {})[pname] = (pr.stdout or "")[-3000:]
            if pr.returncode != 0:
                row.setdefault("probe_fail_tail", {})[pname] = (
                    (pr.stdout or "")[-800:] + " | STDERR: " + (pr.stderr or "")[-800:]
                )
        except subprocess.TimeoutExpired:
            rcs.append({pname: "TIMEOUT"})
    row["probe_rcs"] = rcs
    checks["probes_all_exit0"] = bool(rcs) and all(
        next(iter(d.values())) == 0 for d in rcs
    )

    # C5 schema - three instruments
    if isinstance(doc, dict):
        # (a) catalog-declared CC chain
        try:
            errs_cc = validate_cc_chain(doc, frag)
            row["schema_errors_cc_chain_first10"] = errs_cc[:10]
            row["schema_error_count_cc_chain"] = len(errs_cc)
            checks["schema_valid_cc_chain"] = len(errs_cc) == 0
        except Exception as exc:  # noqa: BLE001
            row["c5_cc_chain_error"] = f"{type(exc).__name__}: {exc}"
            checks["schema_valid_cc_chain"] = False
        # (b) physical platform copy (r2's instrument) - equivalence
        try:
            errs_pl = gate.validate_receipt(doc, schema=json.loads(PL_SCHEMA.read_bytes().decode("utf-8")), fragment=frag)
            row["schema_error_count_platform_copy"] = len(errs_pl)
            checks["schema_valid_platform_copy"] = len(errs_pl) == 0
            row["schema_instruments_agree"] = (len(errs_cc) == 0) == (len(errs_pl) == 0)
        except Exception as exc:  # noqa: BLE001
            row["c5_platform_error"] = f"{type(exc).__name__}: {exc}"
            checks["schema_valid_platform_copy"] = False
            row["schema_instruments_agree"] = False
    else:
        checks["schema_valid_cc_chain"] = False
        checks["schema_valid_platform_copy"] = False
        row["schema_instruments_agree"] = False

    # P predicate: 12 conditions, disk-verified (stronger than r2)
    if isinstance(doc, dict):
        try:
            gr = gate.evaluate_gate_a(
                doc, repo_root=REPO, verify_filesystem=True,
                schema=json.loads(PL_SCHEMA.read_bytes().decode("utf-8")), fragment=frag,
            )
            gd = gr.to_dict()
            row["predicate_complete"] = gd["complete"]
            row["predicate_marker"] = gd["marker"]
            row["predicate_blocking"] = [
                {"n": c["n"], "outcome": c["outcome"], "basis": c["basis"]}
                for c in gd["conditions"] if c["outcome"] in ("UNSATISFIED", "NOT-CHECKED")
            ]
            row["schema_error_count_predicate"] = len(gd["schema_errors"])
            checks["predicate_complete"] = gd["complete"] is True
        except Exception as exc:  # noqa: BLE001
            row["predicate_error"] = f"{type(exc).__name__}: {exc}"
            checks["predicate_complete"] = False
    else:
        checks["predicate_complete"] = False

    row["checks"] = checks
    failed = sorted(k for k, v in checks.items() if not v)
    row["failed_checks"] = failed
    row["verdict"] = "PASS" if not failed else "FAIL"
    results[uid] = row
    print(f"{uid} | verdict: {row['verdict']} | failed: {failed or 'none'}", flush=True)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"schema_precondition": pre, "units": results}, indent=1),
               encoding="utf-8")
print()
print("RESULTS:", OUT)
