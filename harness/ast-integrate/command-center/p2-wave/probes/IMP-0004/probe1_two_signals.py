#!/usr/bin/env python3
"""IMP-0004 probe 1: two independent detectors + redaction proof.

Signal 1: gitleaks-toml rules, exit code and findings count.
Signal 2: Shannon-entropy scan of literals, implemented separately.
Also: report bytes contain zero copies of the synthetic secret body.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from canary import leak_in, synthetic_body, synthetic_github_pat  # noqa: E402
from secret_gate import build_report, write_report  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0004-probe1 {msg}")
    return 1


def main() -> int:
    token = synthetic_github_pat()
    body = synthetic_body()
    with tempfile.TemporaryDirectory(prefix="imp0004-p1-") as td:
        root = Path(td) / "bundle"
        payload = root / "payload"
        payload.mkdir(parents=True)
        planted = payload / "config.env"
        planted.write_text(
            f"PLUGIN_NAME=demo\nGITHUB_TOKEN={token}\n",
            encoding="utf-8",
        )
        (payload / "readme.md").write_text(
            "Demo payload. Mentions GITHUB_TOKEN as a name only.\n",
            encoding="utf-8",
        )
        report = build_report(root)
        report_path = Path(td) / "report.json"
        write_report(report, report_path)
        report_text = report_path.read_text(encoding="utf-8")

        gl = report["detectors"]["gitleaks_rules"]
        ent = report["detectors"]["shannon_entropy"]
        if gl["exit_code"] != 1 or gl["findings_count"] < 1:
            return fail("gitleaks-rules did not flag the synthetic token")
        if ent["findings_count"] < 1:
            return fail("entropy scan did not flag the synthetic token")
        gl_ok = any(
            f["detector"] == "gitleaks-rules" and f["prefix"] == "ghp_"
            for f in report["findings"]
        )
        en_ok = any(
            f["detector"] == "shannon-entropy" and f["prefix"] == "ghp_"
            for f in report["findings"]
        )
        if not gl_ok or not en_ok:
            return fail("both detectors must record prefix ghp_ on the canary")
        same_file = any(
            f["path"].endswith("config.env") for f in report["findings"]
        )
        if not same_file:
            return fail("findings must cite the planted path")
        if body in report_text or leak_in(report_text) or leak_in(json.dumps(report)):
            return fail("report contains synthetic secret body")
        if "ghp_" not in report_text:
            return fail("zero-entropy prefix missing from report")
        if report["blocked"] is not True or report["exit_code"] != 1:
            return fail("gate did not block emit")
        named = {
            f["variable_name"]
            for f in report["findings"]
            if f["path"].endswith("config.env")
        }
        if "GITHUB_TOKEN" not in named:
            return fail("variable_name GITHUB_TOKEN missing")
        print(
            "gitleaks_exit={0} gitleaks_n={1} entropy_n={2} body_hits=0 prefix=ghp_".format(
                gl["exit_code"], gl["findings_count"], ent["findings_count"]
            )
        )
        print("SUCCESS:IMP-0004-probe1 two-signal synthetic token + redaction")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
