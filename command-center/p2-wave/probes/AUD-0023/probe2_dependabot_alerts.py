#!/usr/bin/env python3
"""AUD-0023 named probe 2: the GitHub Dependabot alert list for this repo.

Catalog evidence_requirement names this explicitly as the SECOND independent
advisory source (osv-scanner being the first). This probe:

  1. Calls the real per-repo endpoint
     `GET /repos/{owner}/{repo}/dependabot/alerts` via `gh api`. This is the
     literal "Dependabot alert list" the catalog names.
  2. Records the verbatim result, including failure. A 403
     ("Resource not accessible by integration") is NOT retried into a fake
     success -- it is the honest residual for this unit.
  3. As a clearly-labeled FALLBACK (not a substitute for step 1, and never
     silently promoted to "the Dependabot alert list"), cross-checks the
     packages probe1 flagged against the public GitHub Security Advisories
     REST API (`GET /advisories?ecosystem=...&affects=...`), the same
     database Dependabot alerts are generated from, to see whether a second,
     differently-scoped GitHub-hosted source corroborates probe1's findings
     for at least a sample of the affected packages.

Never invents an alert count. If the real endpoint 403s, `dependabot_alert_ok`
is False and stays False -- the fallback populates `advisory_db_cross_check`
only, which is reported as a SEPARATE, weaker signal.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_JSON = Path(__file__).resolve().parent / "probe2-dependabot-alerts.json"
OUT_RAW = Path(__file__).resolve().parent / "probe2-dependabot-alerts.raw.txt"
P1_JSON = Path(__file__).resolve().parent / "probe1-osv-scan.json"

OWNER_REPO = "Prekzursil/agent-skills-toolchain"


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(REPO_ROOT)
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"


def try_real_dependabot_alerts() -> dict:
    rc, out = run(
        ["gh", "api", f"repos/{OWNER_REPO}/dependabot/alerts", "--paginate"]
    )
    ok = rc == 0
    alerts = None
    if ok:
        try:
            alerts = json.loads(out)
        except json.JSONDecodeError:
            ok = False
    status = None
    if not ok:
        brace = out.find("{")
        if brace != -1:
            try:
                decoder = json.JSONDecoder()
                err_doc, _end = decoder.raw_decode(out[brace:])
                status = err_doc.get("status")
            except (json.JSONDecodeError, AttributeError):
                status = None
    return {
        "endpoint": f"repos/{OWNER_REPO}/dependabot/alerts",
        "exit_code": rc,
        "ok": ok,
        "http_status": status,
        "alert_count": len(alerts) if isinstance(alerts, list) else None,
        "raw_tail": out[-4000:],
    }


def advisory_db_lookup(ecosystem: str, package: str) -> dict:
    rc, out = run(
        [
            "gh",
            "api",
            f"/advisories?ecosystem={ecosystem}&affects={package}&per_page=100",
        ]
    )
    ok = rc == 0
    data = None
    if ok:
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            ok = False
    ghsa_ids = sorted({a.get("ghsa_id") for a in (data or []) if a.get("ghsa_id")})
    return {
        "ecosystem": ecosystem,
        "package": package,
        "ok": ok,
        "exit_code": rc,
        "advisory_count": len(ghsa_ids),
        "ghsa_ids": ghsa_ids,
    }


ECOSYSTEM_MAP = {"PyPI": "pip", "npm": "npm"}


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    real = try_real_dependabot_alerts()

    sample_packages: list[tuple[str, str]] = []
    if P1_JSON.is_file():
        p1 = json.loads(P1_JSON.read_text(encoding="utf-8"))
        seen = set()
        for pkg in p1.get("affected_packages", []):
            eco = ECOSYSTEM_MAP.get(pkg.get("ecosystem"))
            name = pkg.get("name")
            if not eco or not name or (eco, name) in seen:
                continue
            seen.add((eco, name))
            sample_packages.append((eco, name))
    # Bound the cross-check to a documented sample so this probe cannot
    # silently balloon into hundreds of GitHub API calls.
    SAMPLE_LIMIT = 15
    sample_packages = sample_packages[:SAMPLE_LIMIT]

    cross_check = [advisory_db_lookup(eco, name) for eco, name in sample_packages]
    cross_check_ok = all(c["ok"] for c in cross_check) if cross_check else False
    corroborated = sum(1 for c in cross_check if c["ok"] and c["advisory_count"] > 0)

    doc = {
        "started_at": started,
        "real_dependabot_alert_probe": real,
        "advisory_db_cross_check_sample_limit": SAMPLE_LIMIT,
        "advisory_db_cross_check_sample_size": len(cross_check),
        "advisory_db_cross_check": cross_check,
        "advisory_db_cross_check_ok": cross_check_ok,
        "advisory_db_corroborated_package_count": corroborated,
        "ok": cross_check_ok,  # fallback signal succeeding; real endpoint tracked separately
        "dependabot_alert_ok": real["ok"],
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines = [
        "AUD-0023 NAMED PROBE 2: GitHub Dependabot alert list (+ advisory-DB fallback)",
        "unit=AUD-0023",
        f"real_endpoint={real['endpoint']}",
        f"real_exit_code={real['exit_code']} real_ok={real['ok']} http_status={real['http_status']}",
        f"real_alert_count={real['alert_count']}",
        "---- real endpoint raw tail ----",
        real["raw_tail"],
        f"advisory_db_cross_check_sample_size={len(cross_check)} (limit={SAMPLE_LIMIT})",
        f"advisory_db_cross_check_ok={cross_check_ok}",
        f"advisory_db_corroborated_package_count={corroborated}",
        json.dumps(cross_check, indent=2)[:20000],
        f"{'SUCCESS' if cross_check_ok else 'FAILED'}:AUD-0023-probe2 "
        f"(real_dependabot_ok={real['ok']})",
    ]
    raw = "\n".join(raw_lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(
        f"unit=AUD-0023 real_dependabot_ok={real['ok']} http_status={real['http_status']} "
        f"advisory_db_cross_check_ok={cross_check_ok} corroborated={corroborated}/{len(cross_check)}"
    )
    return 0 if cross_check_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
