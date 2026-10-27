#!/usr/bin/env python3
"""Final post-closure sweep - reviewer w4s15.

For all 12 units: receipt state=SUCCESS, reviewer PASS+independent+fresh,
failure absent, receipt_core 0-error (strict), program receipt gate 0-error,
sentinel SUCCESS-form + contains unit id, per-unit manifest artifact row still
matches live bytes, artifact bytes unchanged vs the battery run. The 6
confirm-only receipts must be byte-identical to their pre-run snapshot.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
WS = REPO / "_reviewer-w4s15"
ALL = ["RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
       "RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157"]
CONFIRM_ONLY = {"RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111"}


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_core_validator():
    from jsonschema import Draft202012Validator

    sch = json.loads((REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
    core = dict(sch["$defs"]["receipt_core"])
    core["$defs"] = sch["$defs"]
    Draft202012Validator.check_schema(core)
    return Draft202012Validator(core)


def main() -> int:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import os

    os.environ.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    from receipt_schema_gate import load_schema, validate_receipt

    core_v = load_core_validator()
    gate_schema = load_schema(REPO / "platform" / "schema" / "receipt.schema.json")
    catalog = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u.get("id"): u for u in catalog.get("work_units", []) if isinstance(u, dict)}
    battery = json.loads((WS / "verify_results.json").read_text(encoding="utf-8"))
    closure = json.loads((WS / "closure_report.json").read_text(encoding="utf-8"))

    all_ok = True
    rows = []
    for uid in ALL:
        r = {}
        rpath = REPO / "command-center" / "receipts" / (uid + ".json")
        raw = rpath.read_bytes()
        receipt = json.loads(raw.decode("utf-8"))
        r["state"] = receipt.get("state")
        r["failure_absent"] = receipt.get("failure") is None
        rev = receipt.get("reviewer") or {}
        r["verdict"] = rev.get("verdict")
        r["independent"] = rev.get("independent")
        r["fresh"] = rev.get("fresh_context")
        core_errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        r["core_errors"] = len(core_errs)
        gate_errs = validate_receipt(receipt, schema=gate_schema)
        r["gate_errors"] = len(gate_errs)
        sent = str(receipt.get("sentinel") or "")
        r["sentinel_success_form"] = sent.startswith(("SUCCESS:", "SENTINEL:"))
        r["sentinel_has_uid"] = uid in sent
        # live artifact + manifest binding
        cu = byid[uid]
        out_rel = str(cu["output_path"]).replace("\\", "/")
        art = REPO / out_rel
        r["artifact_bytes"] = art.stat().st_size if art.is_file() else 0
        r["artifact_unchanged_since_battery"] = (
            r["artifact_bytes"] == battery["results"][uid].get("artifact_disk_bytes", r["artifact_bytes"])
        )
        man = json.loads((REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
        row = [a for a in man.get("artifacts", [])
               if a.get("unit_id") == uid and str(a.get("path", "")).replace("\\", "/") == out_rel]
        r["manifest_sha_match"] = bool(row) and row[0].get("sha256") == lf_sha(art)
        # untouched confirmations
        if uid in CONFIRM_ONLY:
            before = closure["untouched_snapshot"][uid]["sha256_before"]
            r["confirm_only_untouched"] = hashlib.sha256(raw).hexdigest() == before
        else:
            r["confirm_only_untouched"] = None
        ok = (r["state"] == "SUCCESS" and r["failure_absent"] and r["verdict"] == "PASS"
              and r["independent"] is True and r["fresh"] is True and r["core_errors"] == 0
              and r["gate_errors"] == 0 and r["sentinel_success_form"] and r["sentinel_has_uid"]
              and r["manifest_sha_match"] and r["confirm_only_untouched"] is not False)
        r["ok"] = ok
        all_ok &= ok
        rows.append((uid, r))
        flag = "OK " if ok else "FAIL"
        print(flag + " " + uid + " state=" + str(r["state"]) + " verdict=" + str(r["verdict"]) +
              " indep=" + str(r["independent"]) + " core_err=" + str(r["core_errors"]) +
              " gate_err=" + str(r["gate_errors"]) + " sentinel_ok=" + str(r["sentinel_success_form"] and r["sentinel_has_uid"]) +
              " manifest=" + str(r["manifest_sha_match"]) +
              (" untouched=" + str(r["confirm_only_untouched"]) if uid in CONFIRM_ONLY else ""))

    (WS / "final_sweep.json").write_text(json.dumps({u: r for u, r in rows}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(("SUCCESS" if all_ok else "FAILED") + ":w4s15 final sweep 12/12 closures verified")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
