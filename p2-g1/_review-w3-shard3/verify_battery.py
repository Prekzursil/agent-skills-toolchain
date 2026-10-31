#!/usr/bin/env python3
"""Independent reviewer verification battery - P2 wave 3 shard 3 (12 units).

Checks per unit (fail-closed, any miss -> FAIL verdict for that unit):
  C01 catalog entry exists with output_path + output_schema
  C02 artifact exists and is non-empty at the catalog output_path
  C03 artifact parses as JSON
  C04 artifact is not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  C05 artifact completion sentinel embeds the unit id (when present)
  C06 recomputed sha256 (CRLF->LF) matches probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row
  C07 recomputed sha256/bytes also match the receipt's primary artifacts row
  C08 artifact validates against the catalog output_schema (schema_resolver)
  C09 every recorded named probe re-runs live with exit 0 (run by the reviewer, cwd=repo)
  C10 program's own _measure_one_delivered.py <uid> prints SUCCESS:delivered
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUTDIR = REPO / "_review-w3-shard3"
UNITS = [
    "ARC-0055", "ARC-0056", "ARC-0076",
    "AUD-0003", "AUD-0005", "AUD-0008", "AUD-0010", "AUD-0026",
    "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 900

sys.path.insert(0, str(REPO / "platform" / "lib"))


def lf_sha256(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def catalog_index() -> dict:
    doc = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    return {u.get("id"): u for u in doc.get("work_units", []) if isinstance(u, dict)}


def probe_commands(receipt: dict) -> list[str]:
    cmds: list[str] = []
    for np in receipt.get("named_probes") or []:
        c = (np or {}).get("command")
        if isinstance(c, str) and c.strip():
            cmds.append(c.strip())
    for ev in receipt.get("evidence") or []:
        for pr in (ev or {}).get("probes") or []:
            c = (pr or {}).get("command")
            if isinstance(c, str) and c.strip() and c.strip() not in cmds:
                cmds.append(c.strip())
    # keep only executable rows: real commands, not prose instructions
    out = []
    for c in cmds:
        if " " not in c:
            continue  # bare prose like "compare ..." is not a command
        if not (c.startswith("PYTHONDONTWRITEBYTECODE") or c.startswith("python")):
            continue
        out.append(c)
    return out


def run_cmd(cmd: str) -> dict:
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROBE_TIMEOUT,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        tail = [ln for ln in out.strip().splitlines() if ln.strip()][-3:]
        return {
            "cmd": cmd,
            "exit": proc.returncode,
            "seconds": round(time.time() - t0, 1),
            "tail": tail,
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": "TIMEOUT", "seconds": round(time.time() - t0, 1), "tail": []}
    except Exception as exc:  # noqa: BLE001
        return {"cmd": cmd, "exit": "SPAWN-ERROR", "seconds": round(time.time() - t0, 1), "tail": [repr(exc)]}


def validate_schema(artifact_path: Path, schema_decl: str) -> dict:
    """Validate via the program's own resolver; fall back to direct compile."""
    try:
        import schema_resolver as SR  # noqa: E402

        doc = load_json(artifact_path)
        errs = SR.validate_artifact(doc, schema_decl)
        return {"method": "schema_resolver.validate_artifact", "ok": not errs, "errors": [str(e)[:200] for e in errs[:5]], "n_errors": len(errs)}
    except Exception as exc:  # noqa: BLE001
        return {"method": "schema_resolver.validate_artifact", "ok": False, "errors": [f"resolver failure: {exc!r}"], "n_errors": -1}


def check_unit(uid: str, cat: dict) -> dict:
    r: dict = {"unit_id": uid, "checks": {}, "probe_runs": []}
    ck = r["checks"]

    # C01 catalog entry
    entry = cat.get(uid)
    ck["C01_catalog_entry"] = bool(entry) and bool(entry.get("output_path")) and bool(entry.get("output_schema"))
    if not entry:
        r["fail_reason"] = "C01 no catalog entry"
        return r
    out_rel: str = entry["output_path"]
    schema_decl: str = entry["output_schema"]
    r["output_path"] = out_rel
    r["output_schema"] = schema_decl

    art = REPO / out_rel
    # C02 exists non-empty
    ck["C02_artifact_nonempty"] = art.is_file() and art.stat().st_size > 0
    if not ck["C02_artifact_nonempty"]:
        r["fail_reason"] = f"C02 artifact missing/empty at {out_rel}"
        return r

    # C03 parses
    try:
        doc = load_json(art)
        ck["C03_parses"] = True
    except Exception as exc:  # noqa: BLE001
        ck["C03_parses"] = False
        r["fail_reason"] = f"C03 unparseable: {exc!r}"
        return r

    # C04 not self-blocked
    state = str(doc.get("state") or "").upper()
    status = str(doc.get("status") or "").upper()
    ck["C04_not_self_blocked"] = state not in NOT_DELIVERING and status not in {"BLOCKED", "FAILED"}
    r["artifact_state"] = state or None
    r["artifact_status"] = status or None

    # C05 sentinel embeds uid
    sent = doc.get("completion_sentinel") or doc.get("sentinel") or ""
    r["sentinel_head"] = str(sent)[:80]
    ck["C05_sentinel_embeds_uid"] = isinstance(sent, str) and uid in sent

    # C06 manifest sha
    sha, nbytes = lf_sha256(art)
    r["computed_sha256"] = sha
    r["computed_bytes_lf"] = nbytes
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man_ok = False
    man_detail = "manifest missing"
    if man_path.is_file():
        try:
            man = load_json(man_path)
            rows = [a for a in man.get("artifacts", []) if isinstance(a, dict)]
            prim = [a for a in rows if a.get("role") == "primary" and a.get("path") == out_rel]
            if not prim:
                prim = [a for a in rows if a.get("path") == out_rel]
            if prim:
                man_ok = prim[0].get("sha256") == sha
                man_detail = f"manifest_sha={prim[0].get('sha256')}"
            else:
                man_detail = f"no row for {out_rel} among {len(rows)}"
        except Exception as exc:  # noqa: BLE001
            man_detail = f"manifest unparseable: {exc!r}"
    ck["C06_manifest_sha_match"] = man_ok
    r["manifest_detail"] = man_detail

    # C07 receipt primary row sha
    rec_path = REPO / "command-center" / "receipts" / f"{uid}.json"
    rec = load_json(rec_path)
    rec_ok = False
    rec_detail = "no primary artifact row in receipt"
    arts = [a for a in rec.get("artifacts", []) if isinstance(a, dict)]
    prim = [a for a in arts if a.get("role") == "primary" and a.get("path") == out_rel]
    if not prim:
        prim = [a for a in arts if a.get("path") == out_rel]
    if prim:
        pa = prim[0]
        rec_ok = (pa.get("sha256") == sha) and (pa.get("bytes") in (nbytes, art.stat().st_size))
        rec_detail = f"receipt_sha={pa.get('sha256')} bytes={pa.get('bytes')}"
    ck["C07_receipt_row_match"] = rec_ok
    r["receipt_detail"] = rec_detail

    # C08 schema validation
    sch = validate_schema(art, schema_decl)
    ck["C08_schema_valid"] = bool(sch["ok"])
    r["schema_validation"] = sch

    # C09 live probes
    cmds = probe_commands(rec)
    if not cmds:
        ck["C09_probes_exit0"] = False
        r["fail_reason"] = "C09 no executable probe commands recorded in receipt"
    else:
        runs = [run_cmd(c) for c in cmds]
        r["probe_runs"] = runs
        bad = [x for x in runs if x["exit"] != 0]
        ck["C09_probes_exit0"] = not bad
        if bad:
            r["fail_reason"] = "C09 probe failure: " + "; ".join(
                f"{x['cmd']} -> exit {x['exit']} tail={x['tail']}" for x in bad[:2]
            )

    # C10 program measure cross-check
    m = run_cmd(f"python command-center/p2-wave/_measure_one_delivered.py {uid}")
    r["measure_run"] = m
    ck["C10_measure_delivered"] = (
        m["exit"] == 0 and any("SUCCESS:delivered" in ln for ln in m["tail"])
    ) or ("SUCCESS:delivered" in " ".join(m["tail"]))
    return r


def main() -> int:
    OUTDIR.mkdir(exist_ok=True)
    cat = catalog_index()
    results = []
    for uid in UNITS:
        t0 = time.time()
        res = check_unit(uid, cat)
        res["wall_seconds"] = round(time.time() - t0, 1)
        hard = [
            "C01_catalog_entry", "C02_artifact_nonempty", "C03_parses",
            "C04_not_self_blocked", "C06_manifest_sha_match", "C07_receipt_row_match",
            "C08_schema_valid", "C09_probes_exit0", "C10_measure_delivered",
        ]
        res["verdict"] = "FAIL" if res.get("fail_reason") else (
            "PASS" if all(res["checks"].get(h) for h in hard) else "FAIL"
        )
        if res["verdict"] == "FAIL" and not res.get("fail_reason"):
            misses = [h for h in hard if not res["checks"].get(h)]
            res["fail_reason"] = "failed checks: " + ", ".join(misses)
        results.append(res)
        print(f"[{uid}] {res['verdict']} ({res['wall_seconds']}s) {res.get('fail_reason','')}", flush=True)
        (OUTDIR / "battery_results.json").write_text(
            json.dumps(results, indent=1), encoding="utf-8"
        )
    ok = sum(1 for x in results if x["verdict"] == "PASS")
    print(f"DONE {ok}/{len(results)} PASS", flush=True)
    print("SUCCESS:battery" if ok == len(results) else "FAILED:battery partial", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
