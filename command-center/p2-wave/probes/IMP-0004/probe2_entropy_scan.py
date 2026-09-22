#!/usr/bin/env python3
"""IMP-0004 probe2: independent Shannon-entropy scan flags the same synthetic token.

Evidence signal (2): entropy instrument is implemented separately from the
gitleaks-style pattern table and must flag the identical synthetic token.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import secret_gate as S  # noqa: E402

PROBE = Path(__file__).resolve().parent
RAW = PROBE / "probe2-entropy.raw.txt"
MEAS = PROBE / "probe2-measurement.json"
EVIDENCE = (
    "independent entropy scan implemented separately that must also flag the "
    "same synthetic token"
)


def main() -> int:
    token = S.synthesize_github_pat(seed=20260908, body_len=36)
    body = S.secret_body(token)
    bits = S.shannon_bits(token)
    body_bits = S.shannon_bits(body)
    entropy_flags = S.entropy_flags_token(token)
    # Pattern table (instrument 1) vs entropy (instrument 2) on the same token.
    pattern_findings = S.scan_text(f'token="{token}"\n', relpath="probe2.py")
    pattern_rules = sorted(
        {f.rule for f in pattern_findings if f.severity == "blocking"}
    )
    pattern_fires = "github_token" in pattern_rules
    # Prove instruments are distinct: SECRET_RULES names vs high_entropy_token rule.
    rule_names = {name for name, _ in S.SECRET_RULES}
    entropy_is_separate = "high_entropy_token" not in rule_names
    report = S.scan_members([("probe2.py", f'token="{token}"\n'.encode("utf-8"))])
    report_text = report.render_named_report()
    body_hits = report_text.count(body)
    ok = (
        entropy_flags
        and pattern_fires
        and entropy_is_separate
        and body_hits == 0
        and bits >= S.HIGH_ENTROPY_BITS
        and body_bits >= S.HIGH_ENTROPY_BITS
    )
    lines = [
        "NAMED PROBE 2: INDEPENDENT ENTROPY SCAN",
        "PROBE-2-BEGIN:IMP-0004",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"entropy_flags_token={entropy_flags}",
        f"shannon_bits_token={bits:.4f}",
        f"shannon_bits_body={body_bits:.4f}",
        f"high_entropy_floor={S.HIGH_ENTROPY_BITS}",
        f"pattern_fires_github_token={pattern_fires}",
        f"pattern_rules={pattern_rules}",
        f"entropy_instrument_separate_from_SECRET_RULES={entropy_is_separate}",
        f"secret_body_hits_in_report={body_hits}",
        f"ok={ok}",
        "PROBE-2-COMPLETE:IMP-0004",
        "SUCCESS:IMP-0004-probe2" if ok else "FAILED:IMP-0004-probe2",
    ]
    raw = "\n".join(lines) + "\n"
    RAW.write_text(raw, encoding="utf-8")
    meas = {
        "ok": ok,
        "entropy_flags_token": entropy_flags,
        "shannon_bits_token": round(bits, 4),
        "shannon_bits_body": round(body_bits, 4),
        "pattern_fires_github_token": pattern_fires,
        "pattern_rules": pattern_rules,
        "entropy_instrument_separate": entropy_is_separate,
        "secret_body_hits_in_report": body_hits,
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
