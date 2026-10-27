#!/usr/bin/env python3
"""Independent reviewer battery - wave 4 shard 11 (12 units).

Adversarially verifies each unit: receipt parse/state, output_schema
(receipt_core Draft 2020-12), catalog entry, live probe re-runs (exit 0),
UNIT-ARTIFACT-MANIFEST sha256 rows (CRLF->LF normalized), artifact_paths
existence. READ-ONLY: never edits receipts, probes, manifests, or artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = [
    "IMP-0261", "IMP-0264", "IMP-0269", "IMP-0270", "IMP-0271", "IMP-0272",
    "IMP-0273", "IMP-0274", "IMP-0275", "IMP-0279", "IMP-0303", "IMP-0304",
]
PROBE_TIMEOUT = 300  # seconds per probe; each probe historically < 60s


def lf_sha256(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def norm(p: str) -> str:
    return p.replace("\\", "/")


def load_json(p: Path):
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    import jsonschema

    phys = load_json(REPO / "platform" / "schema" / "receipt.schema.json")
    wrapper = {"$ref": "#/$defs/receipt_core", "$defs": phys["$defs"]}
    validator = jsonschema.Draft202012Validator(wrapper)

    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    units = cat.get("work_units") or cat.get("items")
    byid = {u["id"]: u for u in units}

    summary: dict[str, dict] = {}
    any_fail = False

    for uid in IDS:
        issues: list[str] = []
        detail: dict = {"checks": {}}

        # A. catalog entry
        cu = byid.get(uid)
        expected_receipt_rel = f"command-center/receipts/{uid}.json"
        if cu is None:
            issues.append("catalog:no-entry")
        else:
            op = norm(cu.get("output_path") or "")
            detail["checks"]["catalog_output_path"] = op
            if op != expected_receipt_rel:
                issues.append(f"catalog:output-path-mismatch:{op}")

        # B. receipt existence / parse / state / reviewer closure
        rcpt_path = REPO / expected_receipt_rel
        if not rcpt_path.is_file() or rcpt_path.stat().st_size == 0:
            issues.append("receipt:missing-or-empty")
            summary[uid] = {"verdict": "FAIL", "issues": issues}
            any_fail = True
            print(f"{uid}: FAIL {issues}")
            continue
        try:
            doc = load_json(rcpt_path)
            if not isinstance(doc, dict):
                issues.append("receipt:not-an-object")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"receipt:unparseable:{exc}")
            summary[uid] = {"verdict": "FAIL", "issues": issues}
            any_fail = True
            print(f"{uid}: FAIL {issues}")
            continue
        detail["receipt_bytes"] = rcpt_path.stat().st_size
        state = str(doc.get("state") or "").upper()
        detail["checks"]["state"] = state
        if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            issues.append(f"receipt:self-declared-{state}")
        if doc.get("unit_id") != uid:
            issues.append(f"receipt:unit_id:{doc.get('unit_id')!r}")
        rv = doc.get("reviewer") or {}
        rv_verdict = rv.get("verdict")
        rv_indep = rv.get("independent")
        detail["checks"]["reviewer"] = f"{rv_verdict}/independent={rv_indep}"
        if rv_verdict != "PASS" or rv_indep is not True:
            issues.append(f"receipt:reviewer-closure:{rv_verdict}/independent={rv_indep}")

        # C. schema validation (receipt_core, Draft 2020-12)
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        if errs:
            first = "; ".join(
                f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message[:160]}" for e in errs[:5]
            )
            issues.append(f"schema:{len(errs)}-errors:{first}")
        detail["schema_error_count"] = len(errs)

        # D. profile agreement with catalog output_schema declaration
        if cu is not None:
            m = re.search(r"profile=([A-Za-z0-9_-]+)", str(cu.get("output_schema") or ""))
            cat_profile = m.group(1) if m else None
            req_m = re.search(r"required:\s*([^)]+)\)", str(cu.get("output_schema") or ""))
            detail["checks"]["catalog_profile"] = cat_profile
            rcpt_profile = doc.get("profile")
            detail["checks"]["receipt_profile"] = rcpt_profile
            if cat_profile and rcpt_profile and rcpt_profile != cat_profile:
                issues.append(f"profile:receipt={rcpt_profile}-catalog={cat_profile}")
            if req_m:
                for field in [s.strip() for s in req_m.group(1).split(",") if s.strip()]:
                    fname = field.replace("[]", "")
                    if fname not in doc:
                        issues.append(f"profile:missing-field:{fname}")

        # E. artifact_paths existence
        missing_art = []
        for ap in doc.get("artifact_paths") or []:
            p = Path(ap) if Path(ap).is_absolute() else REPO / norm(ap)
            if not p.is_file():
                missing_art.append(norm(ap))
        if missing_art:
            issues.append(f"artifact-paths-missing:{missing_art}")

        # F. live probes re-run
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        probes = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
        if not probes:
            issues.append("probes:none-found")
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for probe in probes:
            try:
                r = subprocess.run(
                    [sys.executable, "-B", str(probe)],
                    cwd=str(REPO), capture_output=True, text=True,
                    timeout=PROBE_TIMEOUT, env=env,
                )
                ok = r.returncode == 0 and "FAILED:" not in r.stdout
                detail.setdefault("probes", []).append(
                    {"probe": probe.name, "exit": r.returncode, "ok": ok}
                )
                if not ok:
                    tail = (r.stdout or "")[-400:] + "|" + (r.stderr or "")[-400:]
                    issues.append(f"probe:{probe.name}:exit={r.returncode}:{tail}")
            except subprocess.TimeoutExpired:
                issues.append(f"probe:{probe.name}:TIMEOUT>{PROBE_TIMEOUT}s")

        # G. manifest sha256 rows (CRLF->LF normalized)
        man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_path.is_file():
            issues.append("manifest:missing")
        else:
            try:
                man = load_json(man_path)
            except Exception as exc:  # noqa: BLE001
                issues.append(f"manifest:unparseable:{exc}")
                man = None
            if man is not None:
                rows = man.get("artifacts") or []
                if not rows:
                    issues.append("manifest:no-rows")
                receipt_row_seen = False
                for row in rows:
                    if not isinstance(row, dict):
                        issues.append("manifest:row-not-object")
                        continue
                    rel = norm(str(row.get("path") or ""))
                    p = REPO / rel
                    if not p.is_file():
                        issues.append(f"manifest:row-missing-on-disk:{rel}")
                        continue
                    if rel == expected_receipt_rel:
                        receipt_row_seen = True
                    live_sha = lf_sha256(p)
                    if row.get("sha256") != live_sha:
                        issues.append(f"manifest:sha-mismatch:{rel}:manifest={row.get('sha256')[:12]}:live={live_sha[:12]}")
                    if row.get("bytes") in (None,) or int(row.get("bytes")) != p.stat().st_size:
                        issues.append(f"manifest:bytes-mismatch:{rel}:manifest={row.get('bytes')}:live={p.stat().st_size}")
                if not receipt_row_seen:
                    issues.append("manifest:no-receipt-row")

        verdict = "PASS" if not issues else "FAIL"
        if issues:
            any_fail = True
        summary[uid] = {"verdict": verdict, "issues": issues, "detail": detail}
        print(f"{uid}: {verdict}" + (f"  issues={issues}" if issues else ""))

    out = REPO / "_shard11w4" / "_indep_review_w4s11_summary.json"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1)
    print(f"\nsummary -> {out}")
    print("BATTERY-OVERALL:", "FAIL" if any_fail else "PASS")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
