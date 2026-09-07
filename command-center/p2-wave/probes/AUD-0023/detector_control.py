#!/usr/bin/env python3
"""AUD-0023 tests_required: detector control (fixture-bound, no live repo mutation).

Catalog wording: "seed a fixture with a package version carrying a known
published advisory and confirm BOTH sources report it; a source that stays
silent on the known-bad case measures nothing."

Fixtures (never touch a real lockfile in this repo):
  * fixtures/known-vulnerable-requirements.txt -> urllib3==1.24.1
    (multiple published GHSAs; first_patched_version=1.24.2 for at least one)
  * fixtures/clean-requirements.txt            -> six==1.16.0 (0 advisories
    in either source at time of writing -- used as the silent-on-good pair)

Source A = osv-scanner (probe1's real tool).
Source B = GitHub Security Advisories REST API (probe2's fallback source,
same underlying database Dependabot alerts are generated from).

PASS requires:
  1. Source A fires (advisory_count > 0) on known-vulnerable, is silent
     (advisory_count == 0) on clean.
  2. Source B fires on known-vulnerable, is silent on clean.
  3. At least one GHSA id is common to BOTH sources' known-vulnerable output
     (cross-source corroboration, not just "both found something").
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
FIXTURES = PROBE_DIR / "fixtures"
OUT_JSON = PROBE_DIR / "control-detector.json"
OUT_RAW = PROBE_DIR / "control-detector.raw.txt"


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def osv_scan_fixture(binary: str, fixture: Path) -> dict:
    rc, out = run([binary, "--format", "json", "-L", str(fixture)])
    brace = out.find("{")
    ghsa_ids: set[str] = set()
    if brace != -1:
        try:
            decoder = json.JSONDecoder()
            parsed, _ = decoder.raw_decode(out[brace:])
            for result in parsed.get("results", []):
                for pkg in result.get("packages", []):
                    for v in pkg.get("vulnerabilities", []):
                        vid = v.get("id")
                        if vid:
                            ghsa_ids.add(vid)
        except json.JSONDecodeError:
            pass
    return {
        "fixture": str(fixture.name),
        "exit_code": rc,
        "advisory_count": len(ghsa_ids),
        "ids": sorted(ghsa_ids),
    }


def advisory_db_lookup(package: str) -> dict:
    rc, out = run(
        ["gh", "api", f"/advisories?ecosystem=pip&affects={package}&per_page=100"]
    )
    ghsa_ids: set[str] = set()
    if rc == 0:
        try:
            data = json.loads(out)
            ghsa_ids = {a.get("ghsa_id") for a in data if a.get("ghsa_id")}
        except json.JSONDecodeError:
            pass
    return {
        "package": package,
        "exit_code": rc,
        "advisory_count": len(ghsa_ids),
        "ids": sorted(ghsa_ids),
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    binary = shutil.which("osv-scanner")
    if binary is None:
        doc = {"started_at": started, "ok": False, "error": "osv-scanner not on PATH"}
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        OUT_RAW.write_text("FAILED:AUD-0023-control osv-scanner missing\n", encoding="utf-8")
        print("FAILED:AUD-0023-control osv-scanner missing")
        return 1

    bad_fixture = FIXTURES / "known-vulnerable-requirements.txt"
    good_fixture = FIXTURES / "clean-requirements.txt"

    a_bad = osv_scan_fixture(binary, bad_fixture)
    a_good = osv_scan_fixture(binary, good_fixture)
    b_bad = advisory_db_lookup("urllib3")
    b_good = advisory_db_lookup("six")

    a_fires_bad = a_bad["advisory_count"] > 0
    a_silent_good = a_good["advisory_count"] == 0
    b_fires_bad = b_bad["advisory_count"] > 0
    b_silent_good = b_good["advisory_count"] == 0
    common_ids = sorted(set(a_bad["ids"]) & set(b_bad["ids"]))
    cross_source_corroborated = len(common_ids) > 0

    ok = (
        a_fires_bad
        and a_silent_good
        and b_fires_bad
        and b_silent_good
        and cross_source_corroborated
    )

    doc = {
        "started_at": started,
        "source_a_osv_scanner": {"bad": a_bad, "good": a_good},
        "source_b_advisory_db": {"bad": b_bad, "good": b_good},
        "a_fires_on_bad": a_fires_bad,
        "a_silent_on_good": a_silent_good,
        "b_fires_on_bad": b_fires_bad,
        "b_silent_on_good": b_silent_good,
        "common_ghsa_ids_bad": common_ids,
        "cross_source_corroborated": cross_source_corroborated,
        "ok": ok,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw = (
        "AUD-0023 tests_required: detector control (urllib3==1.24.1 known-bad vs six==1.16.0 clean)\n"
        f"unit=AUD-0023\n"
        f"source_a_osv_scanner bad_count={a_bad['advisory_count']} good_count={a_good['advisory_count']}\n"
        f"source_b_advisory_db bad_count={b_bad['advisory_count']} good_count={b_good['advisory_count']}\n"
        f"common_ghsa_ids_bad={common_ids}\n"
        f"a_fires_on_bad={a_fires_bad} a_silent_on_good={a_silent_good}\n"
        f"b_fires_on_bad={b_fires_bad} b_silent_on_good={b_silent_good}\n"
        f"cross_source_corroborated={cross_source_corroborated}\n"
        f"{'SUCCESS' if ok else 'FAILED'}:AUD-0023-control\n"
    )
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
