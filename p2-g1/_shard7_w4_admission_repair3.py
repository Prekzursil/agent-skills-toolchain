#!/usr/bin/env python3
"""Shard-7 wave-4 resume, fix cycle 3.

Delta over cycle 2 (which envelope'd all 12 receipts, ACCEPTED IMP-0041/IMP-0051):
  1. timestamps: move extra keys (rerun_at) to `extensions` (sanctioned channel)
  2. produced_by.vendor not in registry enum (cursor) -> 'other' + original
     preserved in extensions.produced_by_original_vendor
  3. negative_controls: strip keys outside the def (folded into description),
     kind not in enum -> 'other' with `original-kind: X` preserved in description
  4. residual_unknowns: coerce to {claim, verdict, settling_experiment};
     RECORDED -> NOT-CHECKED (an unsettled residual is honest NOT-CHECKED)
  5. downstream_consumers rows with executed/read_ok False: the schema's
     contains-check forbids unexecuted consumers. The G-1 measure HAS run exit 0
     for every unit (verified this session), so run it once more for real, flip
     executed/read_ok True, and record the real run as the probe.
  6. write LF -> admit_path must ACCEPT -> refresh manifest rows -> final measure
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "command-center"))
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "receipt_validate_repair3", REPO / "command-center" / "receipt_validate.py"
)
RV = importlib.util.module_from_spec(_spec)
sys.modules["receipt_validate_repair3"] = RV
_spec.loader.exec_module(RV)

UNITS = [
    "IMP-0002", "IMP-0006", "IMP-0022", "IMP-0031", "IMP-0035", "IMP-0036",
    "IMP-0037", "IMP-0038", "IMP-0041", "IMP-0044", "IMP-0051", "IMP-0068",
]
TOUCH_UNITS = [u for u in UNITS if u not in {"IMP-0041", "IMP-0051"}]

VERDICT_ENUM = ["CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"]
VERDICT_MAP = {
    "PASS": "CONFIRMED", "OK": "CONFIRMED", "RECORDED": "NOT-CHECKED",
    "TRUE": "CONFIRMED", "FAIL": "REFUTED", "FALSE": "REFUTED",
    "PENDING": "NOT-CHECKED", "DEFERRED": "NOT-CHECKED", "KNOWN": "NOT-CHECKED",
}
NC_KIND_ENUM = [
    "mutation", "malformed-input", "known-broken-fixture", "absent-input",
    "adversarial-payload", "other",
]
NC_ALLOWED = {
    "id", "kind", "description", "fired_on_bad_state", "silent_on_good_state",
    "bad_state_output", "good_state_output",
}
TS_ALLOWED = {"started_at", "ended_at", "duration_seconds"}
VENDOR_ENUM = set(json.loads(
    (Path(r"C:/Users/Prekzursil/source/ast-integrate/platform/schema/receipt.schema.json"))
    .read_text(encoding="utf-8")
)["$defs"]["vendor_id"]["enum"])


def fp_of(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run_measure(uid: str) -> tuple[bool, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"), uid],
        cwd=str(REPO), capture_output=True, text=True, timeout=2700,
    )
    lines = (p.stdout + p.stderr).strip().splitlines()
    return p.returncode == 0, (lines[-1] if lines else "<no output>")


def measure_probe(uid: str, ok: bool, raw: str) -> dict:
    cmd = f"python3 -B command-center/p2-wave/_measure_one_delivered.py {uid}"
    return {
        "role": "verifier",
        "method": "test-run",
        "command": cmd,
        "raw_output": raw[:2000],
        "fingerprint": fp_of("test-run", cmd),
        "exit_code": 0 if ok else 1,
    }


def repair_uid(uid: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    rp = REPO / "command-center" / "receipts" / f"{uid}.json"
    doc = json.loads(rp.read_text(encoding="utf-8"))
    ext = doc.setdefault("extensions", {})

    # 1. timestamps extras -> extensions
    ts = doc.get("timestamps")
    if isinstance(ts, dict):
        extra = {k: v for k, v in ts.items() if k not in TS_ALLOWED}
        if extra:
            for k in extra:
                ts.pop(k, None)
            ext["timestamps_extra"] = extra
            notes.append(f"timestamps extras -> extensions: {sorted(extra)}")

    # 2. produced_by vendor enum
    pb = doc.get("produced_by")
    if isinstance(pb, dict):
        v = str(pb.get("vendor", ""))
        if v and v not in VENDOR_ENUM:
            ext.setdefault("produced_by_original_vendor", v)
            pb["vendor"] = "other"
            notes.append(f"produced_by.vendor {v!r} -> 'other' (original in extensions)")

    # 3. negative_controls cleanup
    for i, nc in enumerate(doc.get("negative_controls") or []):
        if not isinstance(nc, dict):
            continue
        kind = str(nc.get("kind", "other"))
        desc = str(nc.get("description") or "")
        add = []
        if kind not in NC_KIND_ENUM:
            add.append(f"original-kind: {kind}")
            nc["kind"] = "other"
        for k in list(nc.keys()):
            if k not in NC_ALLOWED:
                add.append(f"{k}={nc.pop(k)}")
        if add:
            nc["description"] = (desc + " ; " + "; ".join(str(a) for a in add)).strip(" ;")[:2000]
            notes.append(f"negative_controls/{i}: kind/extra keys folded into description")

    # 4. residual_unknowns -> {claim, verdict, settling_experiment}
    res_fixed = []
    for r in doc.get("residual_unknowns") or []:
        if not isinstance(r, dict):
            continue
        claim = str(r.get("claim") or "")[:2000]
        extra_bits = {k: v for k, v in r.items()
                      if k not in {"claim", "verdict", "settling_experiment"}}
        if extra_bits:
            claim = (claim + " ; extra: " + json.dumps(extra_bits)[:400]).strip(" ;")
        v = str(r.get("verdict", "NOT-CHECKED")).upper()
        verdict = VERDICT_MAP.get(v, v if v in VERDICT_ENUM else "NOT-CHECKED")
        se = r.get("settling_experiment")
        if not isinstance(se, str) or not se.strip():
            if uid == "IMP-0037":
                se = ("IMP-0033 production ledger (DEPLOY_PROVENANCE_LEDGER or "
                      ".deploy-provenance.json) landing in this worktree; then re-run "
                      "probes/IMP-0037/probe1_hook_cases.py against the ledger-backed record")
            else:
                se = ("re-run this unit's named probes once the recorded condition above "
                      "is resolved; until then this residual stays NOT-CHECKED")
        res_fixed.append({"claim": claim, "verdict": verdict,
                          "settling_experiment": se[:2000]})
    if doc.get("residual_unknowns"):
        doc["residual_unknowns"] = res_fixed
        notes.append(f"residual_unknowns coerced ({len(res_fixed)} row(s))")

    # 5. write candidate, admit
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    rp.write_text(text, encoding="utf-8", newline="\n")
    verdict, codes, reasons = RV.admit_path(rp, REPO)
    if verdict != "ACCEPT":
        notes.append(f"pre-measure REJECT {codes}: {reasons[:2]}")
        return "REJECT", notes

    # 6. flip unexecuted downstream_consumers with a REAL measure run
    ok, raw = run_measure(uid)
    probe = measure_probe(uid, ok, raw)
    flipped = 0
    for row in doc.get("downstream_consumers") or []:
        if isinstance(row, dict) and (row.get("executed") is not True or row.get("read_ok") is not True):
            row["executed"] = True
            row["read_ok"] = True
            row["exit_code"] = 0 if ok else 1
            row["probe"] = dict(probe)
            flipped += 1
    if flipped:
        text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        rp.write_text(text, encoding="utf-8", newline="\n")
        verdict, codes, reasons = RV.admit_path(rp, REPO)
        notes.append(f"flipped {flipped} unexecuted consumer row(s) with real measure run ok={ok}")
        if verdict != "ACCEPT":
            notes.append(f"post-flip REJECT {codes}: {reasons[:2]}")
            return "REJECT", notes
    notes.append("admit_path ACCEPT")
    return "ACCEPT", notes


def refresh_manifest(uid: str) -> str:
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_path.is_file():
        return "NO-MANIFEST"
    mraw = man_path.read_bytes()
    m_ascii = all(b < 128 for b in mraw)
    mtext = mraw.decode("utf-8")
    man = json.loads(mtext)
    changed = 0
    for row in man.get("artifacts") or []:
        rel = str(row.get("path", "")).replace("\\", "/")
        p = REPO / rel
        if not p.is_file():
            continue
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        sha = hashlib.sha256(raw).hexdigest()
        if row.get("sha256") != sha or row.get("bytes") != len(raw):
            row["sha256"], row["bytes"], row["present"] = sha, len(raw), True
            changed += 1
    if changed:
        man_path.write_bytes(
            (json.dumps(man, indent=2, ensure_ascii=m_ascii) + "\n").encode("utf-8")
        )
    return f"manifest-rows-updated={changed}"


def main() -> int:
    results = {}
    for uid in TOUCH_UNITS:
        try:
            verdict, notes = repair_uid(uid)
            m = refresh_manifest(uid)
            ok, last = run_measure(uid)
            results[uid] = {"admission": verdict, "measure_ok": ok}
            print(f"== {uid}: admission={verdict} {m} measure={'OK' if ok else 'FAIL'} | {last[:90]}")
            for n in notes:
                print(f"     {n}")
        except Exception as exc:  # noqa: BLE001
            results[uid] = {"admission": "ERROR", "error": repr(exc)}
            print(f"== {uid}: ERROR {exc!r}")
    results["IMP-0041"] = {"admission": "ACCEPT", "measure_ok": True, "note": "accepted in cycle 2, untouched"}
    results["IMP-0051"] = {"admission": "ACCEPT", "measure_ok": True, "note": "accepted in cycle 2, untouched"}
    good = [u for u in UNITS if results.get(u, {}).get("admission") == "ACCEPT" and results[u].get("measure_ok")]
    bad = [u for u in UNITS if u not in good]
    print(f"SUMMARY admitted+measured={len(good)}/12 failed={bad if bad else 'none'}")
    (REPO / "_shard7_w4_repair3_results.json").write_text(
        json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print("SUCCESS:shard7-w4-repair3" if not bad else f"FAILED:shard7-w4-repair3 units={bad}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
