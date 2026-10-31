#!/usr/bin/env python3
"""w3 shard-23 INDEPENDENT REVIEWER verification battery (12 units).

Checks per unit (fail-closed, each terminal marker printed):
  C1 catalog entry exists (output_path/output_schema/dependencies)
  C2 receipt artifact at catalog output_path: exists, non-empty, parses, >= min_bytes_threshold
  C3 not self-declared BLOCKED/FAILED (receipt state, sentinel, SUBAGENT-RETURN status/state)
  C4 UNIT-ARTIFACT-MANIFEST.json: parses, expected==present, every row on disk
  C5 sha256 recompute per row (CRLF->LF normalized) matches manifest + bytes match
  C6 primary manifest row == catalog output_path
  C7 receipt validates against catalog output_schema fragment (jsonschema, file:// registry)
  C8 live probes re-run: every named_probes command exits 0
  C9 receipt.tests commands == SUBAGENT-RETURN named_probes commands
  C10 SUCCESS predicate fields (receipt_core conditional): required keys, evidence>=2,
      tests>=1 non-FAIL, negative_controls>=1 both-states fired, downstream_consumers ok,
      manifest registered
  C11 reviewer closure state: verdict/independent present?
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
CC = REPO / "command-center"
UNITS = [
    "TST-0195", "TST-0197", "TST-0202", "TST-0204", "TST-0206", "TST-0215",
    "TST-0219", "TST-0221", "TST-0223", "TST-0227", "TST-0230", "TST-0233",
]
OUT = REPO / "_p2shard23-w3-review" / "_w3s23_battery_out.json"
PROBE_TIMEOUT_S = 420

# ---------------------------------------------------------------- schema setup
from jsonschema.validators import Draft202012Validator  # noqa: E402
from referencing import Registry, Resource  # noqa: E402
from referencing.jsonschema import DRAFT202012  # noqa: E402


def _uri_to_path(uri: str) -> Path:
    p = uri
    for pref in ("file:///", "file://"):
        if p.startswith(pref):
            p = p[len(pref):]
            break
    return Path(p)


def _retrieve(uri: str) -> Resource:
    path = _uri_to_path(uri)
    if not path.is_file():
        raise FileNotFoundError(f"schema uri not on disk: {uri}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return Resource.from_contents(doc, default_specification=DRAFT202012)


REGISTRY = Registry(retrieve=_retrieve)
CC_SCHEMA_DOC = json.loads((CC / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
CC_SCHEMA_URI = "file:///C:/Users/Prekzursil/p2-g1/command-center/schema/receipt.schema.json"


def fragment_validator(output_schema: str) -> Draft202012Validator:
    """output_schema like 'command-center/schema/receipt.schema.json#/$defs/portability_report'."""
    frag = output_schema.split("#", 1)[1]  # /$defs/<name>
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "allOf": [{"$ref": CC_SCHEMA_URI + "#" + frag}],
    }
    return Draft202012Validator(wrapper, registry=REGISTRY)


# ---------------------------------------------------------------- helpers
def sha_lf(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


BASH = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"


def run_probe(cmd: str) -> dict:
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["bash", "-c", cmd], cwd=str(REPO), capture_output=True,
            text=True, timeout=PROBE_TIMEOUT_S,
        )
        return {
            "cmd": cmd, "exit": proc.returncode,
            "tail": ((proc.stdout or "") + (proc.stderr or ""))[-400:],
            "secs": round(time.time() - t0, 1),
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": "TIMEOUT", "tail": "", "secs": round(time.time() - t0, 1)}


# ---------------------------------------------------------------- battery
def check_unit(uid: str, catalog: dict) -> dict:
    res = {"unit": uid, "checks": {}, "probe_runs": []}

    def C(name, ok, detail=""):
        res["checks"][name] = {"ok": bool(ok), "detail": detail}
        return ok

    # C1 catalog
    ent = catalog.get(uid)
    if not C("C1_catalog_entry", ent is not None,
             "" if ent else "unit missing from WORK-UNIT-CATALOG work_units"):
        res["verdict"] = "FAIL"
        return res
    out_rel = ent.get("output_path")
    out_path = REPO / out_rel
    frag_name = ent.get("output_schema", "").split("#")[-1].split("/")[-1]

    # C2 receipt artifact
    ok = out_path.is_file() and out_path.stat().st_size > 0
    if not C("C2_artifact_exists_nonempty", ok, f"{out_rel} size={out_path.stat().st_size if out_path.exists() else 0}"):
        res["verdict"] = "FAIL"
        return res
    try:
        receipt = load(out_path)
        C("C2b_receipt_parses", True)
    except Exception as exc:
        C("C2b_receipt_parses", False, str(exc)[:200])
        res["verdict"] = "FAIL"
        return res
    mbt = receipt.get("min_bytes_threshold")
    C("C2c_receipt_ge_min_bytes",
      isinstance(mbt, int) and out_path.stat().st_size >= mbt,
      f"file={out_path.stat().st_size} min_bytes_threshold={mbt}")

    # C3 not self-blocked
    state = receipt.get("state")
    sentinel = receipt.get("sentinel", "")
    probe_dir = CC / "p2-wave" / "probes" / uid
    sar_path = probe_dir / "SUBAGENT-RETURN.json"
    sar = load(sar_path) if sar_path.is_file() else {}
    blocked = (
        state in ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT")
        or sentinel.startswith("FAILED:")
        or str(sar.get("status", "")).upper() in ("BLOCKED", "FAILED")
        or str(sar.get("state", "")).upper() in ("BLOCKED", "FAILED")
        or "reviewer-absent" in json.dumps(receipt.get("failure") or {})
    )
    C("C3_not_self_blocked", not blocked,
      f"state={state} sentinel={sentinel} sar.status={sar.get('status')} sar.state={sar.get('state')}")

    # C4/C5/C6 manifest
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    if not C("C4_manifest_exists", man_path.is_file(), str(man_path)):
        res["verdict"] = "FAIL"
        return res
    try:
        man = load(man_path)
        C("C4b_manifest_parses", True)
    except Exception as exc:
        C("C4b_manifest_parses", False, str(exc)[:200])
        res["verdict"] = "FAIL"
        return res
    rows = man.get("artifacts") or []
    missing = [r["path"] for r in rows if not (REPO / r["path"]).is_file()]
    C("C4c_manifest_rows_on_disk",
      man.get("verified_on_disk") is True and man.get("expected") == man.get("present")
      and len(rows) == man.get("expected") and not missing,
      f"expected={man.get('expected')} present={man.get('present')} rows={len(rows)} missing={missing}")

    bad_sha, bad_bytes = [], []
    for r in rows:
        p = REPO / r["path"]
        try:
            sha, nb = sha_lf(p)
        except Exception as exc:
            bad_sha.append(f"{r['path']}:{exc}")
            continue
        if sha != r.get("sha256"):
            bad_sha.append(f"{r['path']} live={sha[:16]} man={str(r.get('sha256'))[:16]}")
        if r.get("bytes") is not None and nb != r.get("bytes"):
            bad_bytes.append(f"{r['path']} live={nb} man={r.get('bytes')}")
    C("C5_sha256_crlf_normalized_match", not bad_sha, "; ".join(bad_sha) or f"all {len(rows)} rows match")
    C("C5b_bytes_match", not bad_bytes, "; ".join(bad_bytes) or "all rows match")

    primaries = [r for r in rows if r.get("role") == "primary"]
    C("C6_primary_row_is_catalog_output",
      len(primaries) == 1 and primaries[0]["path"] == out_rel and primaries[0].get("unit_id") == uid,
      f"primary={[r['path'] for r in primaries]} catalog={out_rel}")

    # C7 schema validation
    try:
        v = fragment_validator(ent["output_schema"])
        errs = sorted(v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        msgs = [f"{list(e.absolute_path)}: {e.message[:200]}" for e in errs][:8]
        C("C7_schema_valid", not errs, "; ".join(msgs) or f"validates against $defs/{frag_name}")
    except Exception as exc:
        C("C7_schema_valid", False, f"validator failure: {exc}")
        res["verdict"] = "FAIL"
        return res

    # C8 live probes
    named = sar.get("named_probes") or []
    cmds = [n.get("command") for n in named if n.get("command")]
    C("C8_probe_commands_present", len(cmds) >= 1, f"{len(cmds)} named probes")
    for cmd in cmds:
        rr = run_probe(cmd)
        res["probe_runs"].append(rr)
    C("C8b_all_probes_exit0",
      all(r["exit"] == 0 for r in res["probe_runs"]) and len(res["probe_runs"]) == len(cmds),
      "; ".join(f"exit={r['exit']} {Path(r['cmd'].split()[-1]).name}" for r in res["probe_runs"]))

    # C9 receipt.tests commands match named probes
    test_cmds = sorted({t.get("command") for t in (receipt.get("tests") or []) if t.get("command")})
    C("C9_tests_match_named_probes", set(test_cmds) == set(cmds),
      f"tests={len(test_cmds)} named={len(cmds)} "
      f"only_tests={sorted(set(test_cmds) - set(cmds))[:2]} only_named={sorted(set(cmds) - set(test_cmds))[:2]}")

    # C10 SUCCESS predicate fields
    if state == "SUCCESS":
        req = ["tests", "negative_controls", "reviewer", "manifest_registration",
               "downstream_consumers", "residual_unknowns"]
        missing_keys = [k for k in req if k not in receipt]
        C("C10_success_required_keys", not missing_keys, f"missing={missing_keys}")
        ev = receipt.get("evidence") or []
        C("C10b_evidence_ge2", len(ev) >= 2, f"evidence={len(ev)}")
        tests = receipt.get("tests") or []
        badres = [t.get("result") for t in tests if t.get("result") in ("FAIL", "ERROR", "SKIP", "NOT-RUN")]
        C("C10c_tests_no_fail", len(tests) >= 1 and not badres, f"tests={len(tests)} bad={badres}")
        nc = receipt.get("negative_controls") or []
        nc_bad = [i for i, n in enumerate(nc)
                  if n.get("fired_on_bad_state") is False or n.get("silent_on_good_state") is False]
        C("C10d_negative_controls_bothstates", len(nc) >= 1 and not nc_bad,
          f"nc={len(nc)} bad_idx={nc_bad}")
        dc = receipt.get("downstream_consumers") or []
        dc_bad = [i for i, d in enumerate(dc)
                  if d.get("executed") is False or d.get("read_ok") is False]
        C("C10e_downstream_consumers", len(dc) >= 1 and not dc_bad,
          f"dc={len(dc)} bad_idx={dc_bad}")
        mr = receipt.get("manifest_registration") or {}
        C("C10f_manifest_registered",
          mr.get("registered") is True and str(mr.get("manifest_path", "")).endswith(f"probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"),
          f"mr={json.dumps(mr)[:160]}")
    else:
        C("C10_success_required_keys", False, f"state={state} is not SUCCESS; reviewer cannot close as delivered-SUCCESS")

    # C11 reviewer closure state
    rev = receipt.get("reviewer") or {}
    allowed = {"reviewer_id", "verdict", "independent", "fresh_context", "vendor", "notes", "reviewed_at"}
    extra = sorted(set(rev.keys()) - allowed)
    has_v = rev.get("verdict") == "PASS"
    has_i = rev.get("independent") is True
    C("C11_reviewer_closed", has_v and has_i,
      f"verdict={rev.get('verdict')} independent={rev.get('independent')} extra_keys={extra} "
      f"notes_len={len(rev.get('notes') or '')}")
    res["reviewer_extra_keys"] = extra
    res["reviewer_current"] = {k: rev.get(k) for k in ("reviewer_id", "verdict", "independent", "vendor")}

    res["verdict"] = "PASS" if all(c["ok"] for c in res["checks"].values()) else "FAIL"
    return res


def main() -> int:
    cat = load(CC / "WORK-UNIT-CATALOG.json")
    byid = {it.get("id"): it for it in cat.get("work_units", [])}
    catalog = {u: byid.get(u) for u in UNITS}
    results = [check_unit(u, catalog) for u in UNITS]
    OUT.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    fails = [r["unit"] for r in results if r["verdict"] != "PASS"]
    for r in results:
        bad = [k for k, c in r["checks"].items() if not c["ok"]]
        print(f"{r['verdict']}:W3S23:{r['unit']} bad_checks={bad or 'none'}")
    print(f"SUCCESS:w3s23_battery clean={len(results) - len(fails)}/{len(results)} out={OUT.name}" if not fails
          else f"FAILED:w3s23_battery fails={fails} out={OUT.name}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
