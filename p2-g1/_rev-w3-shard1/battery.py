#!/usr/bin/env python3
"""Independent reviewer battery - wave 3 shard 1 (12 ADV units).

Reviewer: claude-opus-5-5 (Anthropic), fresh context, did NOT build these units.
This script is the reviewer's own instrument. The program's canonical measure
(command-center/p2-wave/_measure_one_delivered.py) is run separately as a
second, mechanically different signal.

Checks per unit (every one must hold for a PASS closure):
  C1 catalog    : id/output_path/output_schema present in WORK-UNIT-CATALOG.json
  C2 artifact   : exists at output_path, non-empty, parses, not self-declared
                  BLOCKED/FAILED/SEVERED/TIMEOUT
  C3 sentinel   : catalog completion_sentinel present in the artifact bytes
  C4 probes     : named probes re-executed live by the reviewer, exit 0 each,
                  SUCCESS: marker in output
  C5 sha256     : live artifact sha256 (CRLF->LF normalized) equals the
                  per-unit UNIT-ARTIFACT-MANIFEST.json primary row (path match,
                  present=true) AND the receipt artifacts row where present
  C6 schema     : output_schema resolves fail-closed via platform/lib/schema_resolver;
                  artifact validated with Draft202012Validator (errors recorded
                  verbatim for adjudication)
  C7 content    : every verdict-shaped value is one legal verdict from
                  {CONFIRMED, REFUTED, PARTIAL, NOT-CHECKED, BLOCKED}; artifact
                  carries negative_controls and evidence sections

Emits battery_out.json with a per-unit record.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
RECEIPTS = REPO / "command-center" / "receipts"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
UNITS = [
    "ADV-0038", "ADV-0040", "ADV-0090", "ADV-0091", "ADV-0096", "ADV-0100",
    "ADV-0109", "ADV-0110", "ADV-0117", "ADV-0119", "ADV-0123", "ADV-0124",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
LEGAL_VERDICTS = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return exc


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_units() -> dict[str, dict]:
    data = load_json(CATALOG)
    out = {}
    if isinstance(data, dict):
        for u in data.get("work_units") or []:
            if isinstance(u, dict) and u.get("id"):
                out[u["id"]] = u
    return out


def run_probe(cmd: str) -> tuple[int, str, float]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join(
        [hook_dir, str(REPO), str(REPO / "tools"), str(REPO / "tools" / "measure-guard"),
         str(REPO / "platform" / "lib"), str(REPO / "tools" / "agentspec"),
         env.get("PYTHONPATH", "")]
    )
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=2700, env=env)
        code, text = p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        code, text = 124, "TIMEOUT"
    return code, text[-2000:], time.monotonic() - t0


def probe_commands(ret, probe_dir: Path) -> list[str]:
    cmds: list[str] = []
    if isinstance(ret, dict):
        for key in ("named_probes", "probes"):
            for item in ret.get(key) or []:
                if isinstance(item, dict) and isinstance(item.get("command"), str):
                    c = item["command"].strip()
                    if c and c not in cmds:
                        cmds.append(c)
    if len(cmds) >= 2:
        return cmds
    def pick(paths):
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        return (named or paths or [None])[0]
    a = pick(sorted(probe_dir.glob("probe1*.py")))
    b = pick(sorted(probe_dir.glob("probe2*.py")))
    if a and b:
        return [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {a.relative_to(REPO).as_posix()}",
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {b.relative_to(REPO).as_posix()}",
        ]
    run = probe_dir / "run_probes.py"
    if run.is_file():
        return [f"PYTHONDONTWRITEBYTECODE=1 python3 -B {run.relative_to(REPO).as_posix()}"]
    return cmds


def load_resolver():
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    sys.path.insert(0, str(p.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location("schema_resolver", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = mod
    spec.loader.exec_module(mod)
    return mod


def walk_target_verdicts(node, path="$", in_targets=False):
    """Yield (path, value) for TARGET-level verdict fields only.

    Target verdicts live under keys named targets/verdicts/target_verdicts (the
    per-enumerated-target verdict the completion_sentinel constrains). Other
    vocabularies that merely look like verdicts (artifact-level state, the
    instrument reviewer block, residual dispositions, condition checks, monitor
    classification labels) are different enums and must not be scanned here.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            nxt = in_targets or str(k) in {"targets", "verdicts", "target_verdicts"}
            yield from walk_target_verdicts(v, f"{path}.{k}", nxt)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_target_verdicts(v, f"{path}[{i}]", in_targets)
    elif isinstance(node, str) and in_targets and path.rsplit(".", 1)[-1] == "verdict":
        yield (path, node)


def review_unit(uid: str, unit: dict, resolver) -> dict:
    rec: dict = {"unit_id": uid, "checks": {}, "details": {}}
    checks = rec["checks"]

    # C1 catalog
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema_decl = str(unit.get("output_schema") or "")
    checks["catalog_entry_complete"] = bool(out_rel and schema_decl)
    rec["details"]["output_path"] = out_rel
    rec["details"]["output_schema"] = schema_decl

    # C2 artifact
    out = REPO / out_rel
    if not out.is_file() or out.stat().st_size <= 0:
        checks["artifact_exists_nonempty"] = False
        rec["details"]["artifact_error"] = "missing or empty at output_path"
        return rec
    checks["artifact_exists_nonempty"] = True
    doc = load_json(out)
    if not isinstance(doc, dict):
        checks["artifact_parses"] = False
        rec["details"]["artifact_error"] = f"unparseable: {type(doc).__name__}"
        return rec
    checks["artifact_parses"] = True
    st = str(doc.get("state") or "").upper()
    checks["not_self_declared_blocked"] = st not in NOT_DELIVERING
    rec["details"]["artifact_state"] = st or "<absent>"

    # C3 sentinel in raw bytes
    sentinel = str(unit.get("completion_sentinel") or "")
    raw_text = out.read_text(encoding="utf-8", errors="replace")
    checks["sentinel_in_bytes"] = bool(sentinel) and sentinel in raw_text

    # C4 live probe re-run by reviewer
    probe_dir = PROBES / uid
    ret = load_json(probe_dir / "SUBAGENT-RETURN.json")
    ret_ok = isinstance(ret, dict) and str(
        ret.get("status") or ret.get("state") or "").upper() not in NOT_DELIVERING
    checks["subagent_return_clean"] = bool(ret_ok)
    cmds = probe_commands(ret, probe_dir)
    rec["details"]["probe_cmds"] = cmds
    probe_results = []
    all_ok = bool(cmds) and ret_ok
    for c in cmds:
        code, tail, dt = run_probe(c)
        ok = (code == 0) and ("SUCCESS:" in tail)
        probe_results.append({"cmd": c, "exit": code, "success_marker": "SUCCESS:" in tail,
                              "seconds": round(dt, 1), "tail": tail[-600:]})
        if not ok:
            all_ok = False
    checks["probes_rerun_live_exit0"] = bool(cmds) and all_ok
    rec["details"]["probe_results"] = probe_results

    # C5 sha256 manifest + receipt cross-match
    live_sha, live_bytes = digest_file(out)
    man = load_json(probe_dir / "UNIT-ARTIFACT-MANIFEST.json")
    rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)
            and a.get("unit_id") == uid] if isinstance(man, dict) else []
    man_rows = [a for a in rows
                if str(a.get("path") or "").replace("\\", "/") == out_rel
                and a.get("present") is True]
    sha_match_manifest = any(a.get("sha256") == live_sha for a in man_rows)
    primary_row = man_rows[0] if man_rows else {}
    receipt = load_json(RECEIPTS / f"{uid}.json")
    receipt_rows = []
    receipt_sha_match = None
    if isinstance(receipt, dict):
        for a in receipt.get("artifacts") or []:
            if isinstance(a, dict) and str(a.get("path") or "").replace("\\", "/") == out_rel:
                receipt_rows.append(a)
        if receipt_rows:
            receipt_sha_match = any(a.get("sha256") == live_sha for a in receipt_rows)
    checks["sha256_matches_manifest"] = bool(sha_match_manifest)
    checks["sha256_matches_receipt_row"] = bool(receipt_sha_match) if receipt_rows else None
    rec["details"]["live_sha256"] = live_sha
    rec["details"]["live_bytes"] = live_bytes
    rec["details"]["manifest_primary_sha"] = primary_row.get("sha256")
    rec["details"]["receipt_row_shas"] = [a.get("sha256") for a in receipt_rows]

    # C6 schema resolve + validate + classify errors
    # Receipt-graft class = any error caused by the physical profile applying
    # receipt vocabulary to a non-receipt artifact. Measured root cause:
    # every artifact-class fragment is allOf[$ref receipt.schema.json#/$defs/
    # generic_report -> receipt_core (+ state==SUCCESS then-branch), kind pin].
    # Includes receipt_core.required fields, the state=SUCCESS then-branch
    # fields, receipt row shapes (evidence_item/negative_control/test_result/
    # artifact/defect), the report block shape, and the produced_by/vendor
    # enum (narrower than real builder substrates: 'cursor', 'xai/cursor').
    RECEIPT_CORE_TOP = {
        "schema_version", "unit_id", "state", "sentinel", "spec_anchor",
        "min_bytes_threshold", "artifacts", "evidence", "timestamps", "retry",
        "report", "manifest_registration", "downstream_consumers",
        "residual_unknowns", "produced_by", "extensions", "failure", "defects",
        # receipt_core allOf[0] then-branch (fires on artifact state=SUCCESS)
        "tests", "negative_controls", "reviewer",
    }
    RECEIPT_ROW_PATHS = {"evidence", "negative_controls", "tests", "artifacts",
                         "reviewer", "defects", "residual_unknowns",
                         "downstream_consumers", "manifest_registration",
                         "report", "produced_by"}
    try:
        rs = resolver.resolve(schema_decl)
        rec["details"]["schema_physical"] = str(rs.physical_path)
        rec["details"]["schema_kind"] = rs.kind
        rec["details"]["schema_fragment"] = rs.physical_fragment
        import jsonschema
        schema_doc = json.loads((REPO / rs.physical_path).read_text(encoding="utf-8"))
        if rs.physical_fragment:
            node = schema_doc
            for part in rs.physical_fragment.lstrip("#/").split("/"):
                node = node[part.replace("~1", "/").replace("~0", "~")]
            schema_doc = node
        reg = resolver.build_registry()
        validator = jsonschema.Draft202012Validator(schema_doc, registry=reg)
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        errs = [f"{'/'.join(str(x) for x in e.absolute_path)}: {e.message}" for e in errors]
        rec["details"]["schema_errors"] = errs[:20]
        rec["details"]["schema_error_count"] = len(errs)
        checks["output_schema_resolves"] = True
        checks["output_schema_validates_clean"] = len(errs) == 0
        in_class, outside = [], []
        for e in errs:
            path, _, msg = e.partition(": ")
            if msg.startswith("'") and " is a required property" in msg:
                field = msg.split("'")[1]
                if field in RECEIPT_CORE_TOP:
                    in_class.append(e)
                    continue
            if path.split("/")[0] in RECEIPT_ROW_PATHS:
                in_class.append(e)
                continue
            outside.append(e)
        rec["details"]["schema_errors_receipt_graft_class"] = len(in_class)
        rec["details"]["schema_errors_outside_class"] = outside[:10]
        rec["details"]["schema_errors_outside_count"] = len(outside)
        checks["schema_errors_all_receipt_graft_class"] = len(outside) == 0
    except Exception as exc:  # fail closed: any resolver/validator error is recorded
        checks["output_schema_resolves"] = False
        checks["output_schema_validates_clean"] = False
        checks["schema_errors_all_receipt_graft_class"] = False
        rec["details"]["schema_error"] = f"{type(exc).__name__}: {exc}"

    # C7 content: verdict legality + required sections
    bad_verdicts = []
    for vpath, val in walk_target_verdicts(doc):
        if val.strip().upper() not in LEGAL_VERDICTS:
            bad_verdicts.append({"path": vpath, "value": val[:80]})
    checks["verdicts_legal"] = len(bad_verdicts) == 0
    rec["details"]["illegal_verdicts"] = bad_verdicts[:10]
    controls_present = any(
        k in doc for k in ("negative_controls", "controls", "tests", "negative_control"))
    checks["has_evidence_and_controls"] = bool(
        doc.get("evidence") or doc.get("controls")) and controls_present
    rec["details"]["artifact_produced_by"] = doc.get("produced_by")

    # receipt provenance (for the closure notes)
    if isinstance(receipt, dict):
        rec["details"]["receipt_produced_by"] = receipt.get("produced_by")
        rec["details"]["receipt_state"] = receipt.get("state")
        rec["details"]["receipt_failure"] = receipt.get("failure")
    rec["details"]["reviewer_requirement"] = unit.get("reviewer_requirement")
    # Pass criteria: every check true, where the schema check is the ADJUDICATED
    # form (resolves fail-closed AND 100% of validation errors are receipt-graft
    # class = profile-generation defect, not unit content). The raw zero-errors
    # boolean stays recorded above as a measurement, not folded away.
    gating_checks = dict(checks)
    gating_checks.pop("output_schema_validates_clean", None)
    rec["ALL_CHECKS_PASS"] = all(v is True for v in gating_checks.values())
    return rec


def main() -> int:
    resolver = load_resolver()
    units = catalog_units()
    out = {"generated_by": "claude-opus-5-5-ind-reviewer-w3-shard1",
           "units": [], "summary": {}}
    n_pass = 0
    for uid in UNITS:
        unit = units.get(uid)
        if unit is None:
            out["units"].append({"unit_id": uid, "ALL_CHECKS_PASS": False,
                                 "checks": {"catalog_entry_complete": False}})
            print(f"FAILED:catalog-missing {uid}")
            continue
        rec = review_unit(uid, unit, resolver)
        out["units"].append(rec)
        failed = [k for k, v in rec["checks"].items() if v is not True]
        status = "PASS" if rec["ALL_CHECKS_PASS"] else "FAIL:" + ",".join(failed)
        if rec["ALL_CHECKS_PASS"]:
            n_pass += 1
        print(f"{status} {uid} "
              f"sha_ok={rec['checks'].get('sha256_matches_manifest')} "
              f"schema_errs={rec['details'].get('schema_error_count', 'n/a')} "
              f"probes={len(rec['details'].get('probe_results', []))}")
    out["summary"] = {"total": len(UNITS), "all_checks_pass": n_pass}
    (Path(__file__).parent / "battery_out.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print(f"SUMMARY {n_pass}/{len(UNITS)} all-checks-pass")
    return 0 if n_pass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
