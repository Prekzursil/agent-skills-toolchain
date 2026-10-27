#!/usr/bin/env python3
"""Wave-4 shard-9 INDEPENDENT REVIEWER - static battery v2.

Fixes over v1 (v1 was wrong, the units were right):
  * manifest bytes column is CRLF-NORMALIZED (proven: probe1_plan_equality.py
    live 3198 raw = 3113 normalized + 85 CRLF) -> compare manifest bytes against
    normalized live bytes (and record raw as info)
  * raw schema instrument validates via {'$ref': phys_uri[+fragment]} so internal
    '#/$defs/...' refs resolve against the FULL physical document (v1's fragment
    extraction stripped the $defs and produced PointerToNowhere artifacts)
  * 'probes' catalog field: the work-unit catalog schema carries NO per-unit
    probes field (19 mandatory fields, platform/schema/work-unit-catalog.schema.json)
    -> probes evidence = named probe scripts in the per-unit probe dir (>=2)
Read-only. Output: battery_out.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = Path(__file__).resolve().parent / "battery_out.json"
UNITS = [
    "IMP-0070", "IMP-0084", "IMP-0090", "IMP-0093",
    "IMP-0097", "IMP-0098", "IMP-0103", "IMP-0134",
    "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168",
]

sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sr  # noqa: E402


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def norm_bytes(p: Path) -> bytes:
    raw = p.read_bytes()
    return raw.replace(b"\r\n", b"\n")


def norm_sha(p: Path) -> str:
    return hashlib.sha256(norm_bytes(p)).hexdigest()


def raw_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def self_blocked(doc) -> str | None:
    if not isinstance(doc, dict):
        return None
    for key in ("state", "status", "verdict"):
        v = doc.get(key)
        if isinstance(v, str) and v.strip().upper() in ("BLOCKED", "FAILED"):
            return f"{key}={v}"
    return None


def main() -> int:
    cat = load(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    byid = {u["id"]: u for u in cat["work_units"]}
    central = load(REPO / "command-center" / "UNIT-ARTIFACT-MANIFEST.json")
    central_rows: dict = {}
    for r in central.get("artifacts", []):
        central_rows.setdefault(r.get("unit_id"), []).append(r)

    out = {}
    for uid in UNITS:
        rec: dict = {"unit_id": uid}
        checks: dict = {}

        # ---- 1. catalog ----
        e = byid.get(uid)
        if e is None:
            rec["catalog_ok"] = False
            checks["catalog_entry"] = "MISSING"
            rec["checks"] = checks
            rec["ALL_PASS"] = False
            rec["failing"] = ["catalog_entry: MISSING"]
            out[uid] = rec
            print(f"FAILED:{uid}-static catalog_entry MISSING", flush=True)
            continue
        rec["catalog_ok"] = True
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        n_probes = len(list(pdir.glob("probe*.py"))) if pdir.is_dir() else 0
        checks["probes_on_disk"] = True if n_probes >= 2 else f"only {n_probes} probe*.py in {pdir.name}"
        rec["output_path"] = e.get("output_path")
        rec["output_schema"] = e.get("output_schema")

        # ---- 2. artifact ----
        op = REPO / e["output_path"]
        art = None
        if not op.is_file():
            checks["artifact"] = "MISSING"
        else:
            size = op.stat().st_size
            rec["artifact_bytes"] = size
            if size == 0:
                checks["artifact"] = "EMPTY"
            else:
                try:
                    art = load(op)
                    sb = self_blocked(art)
                    checks["artifact"] = f"self-blocked {sb}" if sb else True
                except Exception as ex:
                    checks["artifact"] = f"PARSE-ERROR {ex}"
        rec["artifact_ok"] = checks["artifact"] is True

        # ---- 3. manifest rows (bytes+sha CRLF-normalized) ----
        mp = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not mp.is_file():
            checks["manifest"] = "MANIFEST-FILE-MISSING"
            man_rows = []
        else:
            man_rows = load(mp).get("artifacts", [])
            if not man_rows:
                checks["manifest"] = "MANIFEST-EMPTY"
            rowfail = []
            for r in man_rows:
                rp = REPO / r["path"]
                if not rp.is_file():
                    rowfail.append(f"{r['path']} absent")
                    continue
                if r.get("present") is not True:
                    rowfail.append(f"{r['path']} present!=true")
                nb = len(norm_bytes(rp))
                rb = rp.stat().st_size
                if r.get("bytes") not in (nb, rb):
                    rowfail.append(
                        f"{r['path']} bytes manifest={r.get('bytes')} live_norm={nb} live_raw={rb}")
                ns = norm_sha(rp)
                if r.get("sha256") != ns:
                    rowfail.append(
                        f"{r['path']} sha manifest={str(r.get('sha256'))[:12]} live_norm={ns[:12]}")
            checks["manifest"] = rowfail if rowfail else True
        rec["manifest_rows_checked"] = len(man_rows)
        rec["manifest_ok"] = checks["manifest"] is True

        # central manifest cross-check for the receipt path
        crows = [r for r in central_rows.get(uid, [])
                 if r.get("path") == e.get("output_path")]
        if crows and op.is_file():
            cr = crows[0]
            nb = len(norm_bytes(op))
            rec["central_manifest_row"] = {
                "bytes_match": cr.get("bytes") in (nb, op.stat().st_size),
                "sha_match": cr.get("sha256") == norm_sha(op),
            }
        else:
            rec["central_manifest_row"] = "no-central-row-for-receipt-path"

        # ---- 4. schema, two instruments ----
        schema_note: dict = {}
        if art is None:
            checks["output_schema"] = "artifact-missing-or-unparseable"
        else:
            try:
                errs_a = sr.validate_artifact(art, e["output_schema"])
                res = sr.resolve(e["output_schema"])
                schema_note["physical"] = res.physical_path
                schema_note["fragment"] = res.physical_fragment
                schema_note["resolver_n_errors"] = len(errs_a)
                schema_note["resolver_errors"] = errs_a[:8]
            except Exception as ex:
                errs_a = None
                schema_note["resolver_error"] = str(ex)[:200]
            try:
                from jsonschema import Draft202012Validator
                phys = (REPO / schema_note["physical"]).resolve()
                uri = phys.as_uri() + (schema_note["fragment"] or "")
                v = Draft202012Validator({"$ref": uri})
                errs_b = sorted(
                    f"{'/'.join(str(p) for p in er.absolute_path) or '<root>'}: {er.message}"
                    for er in v.iter_errors(art))
                schema_note["raw_n_errors"] = len(errs_b)
                schema_note["raw_errors"] = errs_b[:8]
            except Exception as ex:
                errs_b = None
                schema_note["raw_error"] = str(ex)[:300]
            a_ok = errs_a == []
            b_ok = errs_b == [] if errs_b is not None else False
            checks["output_schema"] = True if (a_ok and b_ok) else f"resolver_ok={a_ok} raw_ok={b_ok}"
        rec["schema_note"] = schema_note
        rec["schema_ok"] = checks["output_schema"] is True

        # ---- 5. closure ----
        rp = REPO / "command-center" / "receipts" / f"{uid}.json"
        try:
            receipt = load(rp)
            rv = receipt.get("reviewer") or {}
            checks["closure"] = (
                receipt.get("state") == "SUCCESS"
                and rv.get("verdict") == "PASS"
                and rv.get("independent") is True
            )
            rec["receipt_state"] = receipt.get("state")
            rec["reviewer"] = {k: rv.get(k) for k in ("verdict", "independent", "reviewer_id")}
            # ---- 6. adversarial extras ----
            mb = receipt.get("min_bytes_threshold")
            if isinstance(mb, int):
                rec["min_bytes_ok"] = op.is_file() and op.stat().st_size >= mb
                if not rec["min_bytes_ok"]:
                    checks["min_bytes_threshold"] = (
                        f"artifact {op.stat().st_size if op.is_file() else 'missing'} < {mb}")
            csent = receipt.get("sentinel") or receipt.get("completion_sentinel")
            want = e.get("completion_sentinel")
            rec["sentinel"] = {"receipt": csent, "catalog": want}
            if want and csent and want not in str(csent):
                checks["sentinel_mismatch"] = f"receipt={csent!r} catalog={want!r}"
            if receipt.get("cloud_ok") is True:
                checks["cloud_ok_true_unsubstantiated"] = "cloud_ok=true on local substrate"
        except Exception as ex:
            checks["closure"] = f"RECEIPT-ERROR {ex}"

        rec["checks"] = checks
        fails = [f"{k}: {v}" for k, v in checks.items() if v is not True]
        rec["ALL_PASS"] = not fails
        rec["failing"] = fails
        out[uid] = rec
        print(("SUCCESS:" if rec["ALL_PASS"] else "FAILED:") + f"{uid}-static "
              + ("; ".join(fails) if fails else "all checks hold"), flush=True)

    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    n_ok = sum(1 for r in out.values() if r.get("ALL_PASS"))
    print(f"SUMMARY static-battery {n_ok}/{len(out)} units all-static-pass -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
