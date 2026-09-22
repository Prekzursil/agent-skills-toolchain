#!/usr/bin/env python3
"""IMP-0004 negative control: clean bundle passes; planted-control bundle fails same run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import secret_gate as S  # noqa: E402

PROBE = Path(__file__).resolve().parent
RAW = PROBE / "negative-control.raw.txt"
MEAS = PROBE / "negative-control-measurement.json"


def main() -> int:
    token = S.synthesize_github_pat(seed=20260908, body_len=36)
    body = S.secret_body(token)
    clean_members = [
        ("ok.py", b"x = 1\n"),
        ("readme.md", b"hello\n"),
    ]
    planted_members = [
        ("ok.py", b"x = 1\n"),
        (S.PLANTED_CONTROL_REL, f"token={token}\n".encode("utf-8")),
    ]
    clean = S.scan_members(clean_members)
    planted = S.scan_members(
        planted_members,
        planted_token=token,
        planted_rel=S.PLANTED_CONTROL_REL,
    )
    # Packer-facing assert: clean OK, planted raises.
    S.assert_members_clean(clean_members)
    blocked = False
    try:
        S.assert_members_clean(planted_members)
    except S.SecretGateError:
        blocked = True
    planted_report = planted.render_named_report()
    body_leaked = body in planted_report
    ok = (
        clean.clean
        and not planted.clean
        and planted.blocking >= 1
        and planted.planted_control_found
        and blocked
        and not body_leaked
    )
    lines = [
        "NEGATIVE CONTROL: CLEAN PASS + PLANTED FAIL (SAME RUN)",
        "NEG-BEGIN:IMP-0004",
        f"clean_blocking={clean.blocking}",
        f"clean_ok={clean.clean}",
        f"planted_blocking={planted.blocking}",
        f"planted_clean={planted.clean}",
        f"planted_control_found={planted.planted_control_found}",
        f"assert_members_clean_raised_on_plant={blocked}",
        f"secret_body_leaked_in_planted_report={body_leaked}",
        f"ok={ok}",
        "NEG-COMPLETE:IMP-0004",
        "SUCCESS:IMP-0004-negative" if ok else "FAILED:IMP-0004-negative",
    ]
    raw = "\n".join(lines) + "\n"
    RAW.write_text(raw, encoding="utf-8")
    meas = {
        "ok": ok,
        "clean_blocking": clean.blocking,
        "clean_ok": clean.clean,
        "planted_blocking": planted.blocking,
        "planted_clean": planted.clean,
        "planted_control_found": planted.planted_control_found,
        "assert_raised_on_plant": blocked,
        "secret_body_leaked": body_leaked,
        "negative_control_fired": ok,
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
