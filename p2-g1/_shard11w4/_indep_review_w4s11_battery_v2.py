#!/usr/bin/env python3
"""Independent reviewer battery v2 - wave 4 shard 11 (12 units).

Resume of _indep_review_w4s11_battery.py (2026-10-26 08:52 run, 12/12 FAIL).
v2 changes vs v1:
  * output_schema validation uses the repo-blessed schema_resolver
    (platform/lib/schema_resolver.validate_artifact) - the same instrument the
    2026-10-26 18:38 w3s10 census_v4 used - and enumerates ALL errors, not 5.
  * cross-checks receipt_core directly (Draft 2020-12) as a second instrument;
    divergence between the two instruments is reported, not silently resolved.
  * live probes re-run via the program's own gate
    (command-center/p2-wave/_measure_one_delivered.py <UID>), i.e. the exact
    probe selection + manifest-sha rule the program measures DELIVERED with.
  * full manifest row audit (every row: on-disk, sha256 CRLF->LF, bytes),
    artifact_paths existence, reviewer-closure validity, sentinel-in-text.

Verdict rule: PASS only if every check holds; else FAIL with precise reasons.
Receipts are NEVER edited by this battery (closure writes are a separate step).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
IDS = [
    "IMP-0261", "IMP-0264", "IMP-0269", "IMP-0270", "IMP-0271", "IMP-0272",
    "IMP-0273", "IMP-0274", "IMP-0275", "IMP-0279", "IMP-0303", "IMP-0304",
]
MEASURE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
MEASURE_TIMEOUT = 900  # s per unit (measure internally caps probes at 2700s each)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def lf_sha256(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def norm(p: str) -> str:
    return p.replace("\\", "/")


def load_json(p: Path):
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    from schema_resolver import validate_artifact  # noqa: E402
    import jsonschema  # noqa: E402

    phys = load_json(REPO / "platform" / "schema" / "receipt.schema.json")
    wrapper = {"$ref": "#/$defs/receipt_core", "$defs": phys["$defs"]}
    core_validator = jsonschema.Draft202012Validator(wrapper)

    cat = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    byid = {u["id"]: u for u in (cat.get("work_units") or [])}

    summary: dict[str, dict] = {}
    n_pass = 0
    for uid in IDS:
        t0 = time.time()
        issues: list[str] = []
        detail: dict = {"checks": {}}
        cu = byid.get(uid)
        expected_rel = f"command-center/receipts/{uid}.json"

        # A. catalog entry
        if cu is None:
            issues.append("catalog:no-entry")
        else:
            op = norm(cu.get("output_path") or "")
            detail["checks"]["catalog_output_path"] = op
            if op != expected_rel:
                issues.append(f"catalog:output-path-mismatch:{op}")

        # B. receipt exists / parses / not self-blocked / unit_id / closure
        rcpt_path = REPO / expected_rel
        doc = None
        if not rcpt_path.is_file() or rcpt_path.stat().st_size == 0:
            issues.append("receipt:missing-or-empty")
        else:
            try:
                doc = load_json(rcpt_path)
                if not isinstance(doc, dict):
                    issues.append("receipt:not-an-object")
            except Exception as exc:  # noqa: BLE001
                issues.append(f"receipt:unparseable:{type(exc).__name__}:{exc}")
                doc = None
        if doc is not None:
            detail["receipt_bytes"] = rcpt_path.stat().st_size
            state = str(doc.get("state") or "").upper()
            detail["checks"]["state"] = state
            if state in NOT_DELIVERING:
                issues.append(f"receipt:self-declared-{state}")
            if doc.get("unit_id") != uid:
                issues.append(f"receipt:unit_id:{doc.get('unit_id')!r}")
            sentinel = str(cu.get("completion_sentinel") or "") if cu else ""
            text = rcpt_path.read_text(encoding="utf-8")
            if sentinel and sentinel not in text:
                issues.append("receipt:completion-sentinel-absent-in-text")
            rv = doc.get("reviewer") or {}
            if isinstance(rv, str):
                issues.append("receipt:reviewer-is-string-not-object")
                rv = {}
            rv_verdict = rv.get("verdict")
            rv_indep = rv.get("independent")
            detail["checks"]["reviewer"] = f"{rv_verdict}/independent={rv_indep}"
            if rv_verdict != "PASS" or rv_indep is not True:
                issues.append(
                    f"receipt:reviewer-closure:{rv_verdict}/independent={rv_indep}"
                )

            # C. output_schema validation - canonical resolver, ALL errors
            try:
                errs = validate_artifact(doc, str(cu.get("output_schema") or ""))
            except Exception as exc:  # noqa: BLE001
                errs = [f"resolver-exception:{type(exc).__name__}:{exc}"]
            detail["resolver_error_count"] = len(errs)
            detail["resolver_errors"] = errs
            if errs:
                issues.append(f"schema-resolver:{len(errs)}-errors")
            # cross-instrument: direct receipt_core
            core_errs = sorted(
                core_validator.iter_errors(doc), key=lambda e: list(e.path)
            )
            detail["receipt_core_error_count"] = len(core_errs)
            detail["receipt_core_errors"] = [
                f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message[:200]}"
                for e in core_errs
            ]
            if len(core_errs) != len(errs):
                issues.append(
                    f"schema:instrument-divergence:resolver={len(errs)}:core={len(core_errs)}"
                )

            # D. artifact_paths existence
            missing_art = []
            for ap in doc.get("artifact_paths") or []:
                p = Path(ap) if Path(ap).is_absolute() else REPO / norm(str(ap))
                if not p.is_file():
                    missing_art.append(norm(str(ap)))
            if missing_art:
                issues.append(f"artifact-paths-missing:{missing_art}")

        # E. live probes via the program's own measure gate
        mrc = None
        try:
            r = subprocess.run(
                [sys.executable, "-B", str(MEASURE), uid],
                cwd=str(REPO), capture_output=True, text=True,
                timeout=MEASURE_TIMEOUT,
            )
            mrc = r.returncode
            detail["measure"] = {
                "exit": r.returncode,
                "tail": ((r.stdout or "") + (r.stderr or ""))[-1200:],
            }
            if r.returncode != 0 or "FAILED:delivered" in (r.stdout or ""):
                first = ""
                for line in (r.stdout or "").splitlines():
                    if line.startswith("FAILED:"):
                        first = line
                        break
                issues.append(f"measure:exit={r.returncode}:{first}")
        except subprocess.TimeoutExpired:
            issues.append(f"measure:TIMEOUT>{MEASURE_TIMEOUT}s")

        # F. full manifest audit (every row, independent of the measure's check)
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if not man_path.is_file():
            issues.append("manifest:missing")
        else:
            try:
                man = load_json(man_path)
            except Exception as exc:  # noqa: BLE001
                issues.append(f"manifest:unparseable:{type(exc).__name__}")
                man = None
            if isinstance(man, dict):
                rows = man.get("artifacts") or []
                if not rows:
                    issues.append("manifest:no-rows")
                receipt_row = False
                for row in rows:
                    if not isinstance(row, dict):
                        issues.append("manifest:row-not-object")
                        continue
                    rel = norm(str(row.get("path") or ""))
                    p = REPO / rel
                    if not p.is_file():
                        issues.append(f"manifest:row-missing-on-disk:{rel}")
                        continue
                    if rel == expected_rel:
                        receipt_row = True
                    live_sha = lf_sha256(p)
                    if str(row.get("sha256") or "") != live_sha:
                        issues.append(
                            f"manifest:sha-mismatch:{rel}:manifest={str(row.get('sha256'))[:12]}:live={live_sha[:12]}"
                        )
                    try:
                        mbytes = int(row.get("bytes"))
                    except (TypeError, ValueError):
                        mbytes = -1
                    if mbytes != p.stat().st_size:
                        issues.append(
                            f"manifest:bytes-mismatch:{rel}:manifest={row.get('bytes')}:live={p.stat().st_size}"
                        )
                if not receipt_row:
                    issues.append("manifest:no-receipt-row")
        if not pdir.is_dir():
            issues.append("probes:dir-absent")

        verdict = "PASS" if not issues else "FAIL"
        if verdict == "PASS":
            n_pass += 1
        summary[uid] = {
            "verdict": verdict,
            "issues": issues,
            "detail": detail,
            "seconds": round(time.time() - t0, 1),
        }
        print(f"{uid}: {verdict}"
              + (f"  issues={issues}" if issues else "")
              + f"  [{round(time.time()-t0,1)}s]", flush=True)

    out = REPO / "_shard11w4" / "_indep_review_w4s11_summary_v2.json"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1)
    print(f"\nsummary -> {out}")
    print(f"PASS {n_pass}/12")
    print("BATTERY-OVERALL:", "PASS" if n_pass == 12 else "FAIL")
    return 0 if n_pass == 12 else 1


if __name__ == "__main__":
    raise SystemExit(main())
