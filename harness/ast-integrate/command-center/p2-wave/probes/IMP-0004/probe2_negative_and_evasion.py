#!/usr/bin/env python3
"""IMP-0004 probe 2: same-run negative control + reviewer evasions.

NEGATIVE CONTROL: clean bundle passes while the planted bundle fails
in the same process.

Reviewer evasions (must be recorded, not silently dropped):
  * base64 wrapping of the synthetic token
  * split string literal ("ghp_" + body)
  * .env.sample carrying the token
"""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from canary import leak_in, synthetic_github_pat  # noqa: E402
from secret_gate import build_report  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0004-probe2 {msg}")
    return 1


def _scan(root: Path) -> dict:
    return build_report(root)


def main() -> int:
    token = synthetic_github_pat()
    with tempfile.TemporaryDirectory(prefix="imp0004-p2-") as td:
        base = Path(td)
        planted = base / "planted"
        clean = base / "clean"
        (planted / "payload").mkdir(parents=True)
        (clean / "payload").mkdir(parents=True)
        (planted / "payload" / "secrets.env").write_text(
            f"GITHUB_TOKEN={token}\n", encoding="utf-8"
        )
        (clean / "payload" / "plugin.json").write_text(
            '{"name":"demo","version":"1.0.0"}\n', encoding="utf-8"
        )
        (clean / "payload" / "README.md").write_text(
            "Mentions GITHUB_TOKEN and ghp_ without a body.\n", encoding="utf-8"
        )
        planted_report = _scan(planted)
        clean_report = _scan(clean)
        if planted_report["blocked"] is not True or planted_report["exit_code"] != 1:
            return fail("planted bundle did not fail")
        if clean_report["blocked"] is not False or clean_report["exit_code"] != 0:
            return fail("clean bundle did not pass in the same run")
        if clean_report["findings"]:
            return fail("clean bundle produced findings")
        if leak_in(json.dumps(planted_report)) or leak_in(json.dumps(clean_report)):
            return fail("report leaked secret body")

        b64_root = base / "b64"
        (b64_root / "payload").mkdir(parents=True)
        wrapped = base64.b64encode(token.encode("ascii")).decode("ascii")
        (b64_root / "payload" / "encoded.txt").write_text(
            f"BUNDLE_TOKEN={wrapped}\n", encoding="utf-8"
        )
        b64_report = _scan(b64_root)
        b64_blocked = bool(b64_report["blocked"])

        split_root = base / "split"
        (split_root / "payload").mkdir(parents=True)
        body = token[len("ghp_") :]
        (split_root / "payload" / "build.py").write_text(
            f'token = "ghp_" + "{body}"\n',
            encoding="utf-8",
        )
        split_report = _scan(split_root)
        split_blocked = bool(split_report["blocked"])
        if leak_in(json.dumps(split_report)):
            return fail("split-literal report leaked body")

        sample_root = base / "sample"
        (sample_root / "payload").mkdir(parents=True)
        (sample_root / "payload" / ".env.sample").write_text(
            f"GITHUB_TOKEN={token}\n", encoding="utf-8"
        )
        sample_report = _scan(sample_root)
        sample_blocked = bool(sample_report["blocked"])

        print(
            "negative_control planted_fail={0} clean_pass={1}".format(
                planted_report["blocked"], not clean_report["blocked"]
            )
        )
        print(
            "evasion base64_blocked={0} split_literal_blocked={1} env_sample_blocked={2}".format(
                b64_blocked, split_blocked, sample_blocked
            )
        )
        if not (b64_blocked and split_blocked and sample_blocked):
            return fail("a recorded evasion bypassed the gate")
        print("SUCCESS:IMP-0004-probe2 negative-control + reviewer evasions blocked")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
