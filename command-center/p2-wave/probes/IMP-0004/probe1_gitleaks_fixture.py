#!/usr/bin/env python3
"""IMP-0004 probe1: gitleaks exit code + JSON findings on a synthetic-token fixture.

Evidence signal (1): real gitleaks binary over a fixture tree carrying a synthetic
(never real) token; record exit code and JSON findings count. Report must contain
ZERO bytes of the secret body past its prefix.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import secret_gate as S  # noqa: E402

PROBE = Path(__file__).resolve().parent
WORK = PROBE / "work" / "probe1"
FIXTURE = WORK / "fixture"
RAW = PROBE / "probe1-gitleaks.raw.txt"
MEAS = PROBE / "probe1-measurement.json"
EVIDENCE = (
    "TWO independent signals: (1) gitleaks exit code plus its JSON findings count "
    "on a fixture bundle carrying a synthetic (never real) token; (2) an independent "
    "entropy scan implemented separately that must also flag the same synthetic token. "
    "Additionally prove the report file contains ZERO bytes of the synthetic secret "
    "past its prefix, by grepping the report for the secret body and requiring 0 hits."
)


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    FIXTURE.mkdir(parents=True)
    token = S.synthesize_github_pat(seed=20260908, body_len=36)
    body = S.secret_body(token)
    (FIXTURE / "app.cfg").write_text(
        f'API_TOKEN = "{token}"\n', encoding="utf-8", newline="\n"
    )
    (FIXTURE / "clean.md").write_text("# no secrets\n", encoding="utf-8")

    cfg = REPO / ".gitleaks.toml"
    # Prefer a minimal config without path allowlists so the fixture always fires.
    # Repo allowlists skip test paths; this fixture is under probes/, not tests/.
    rc, findings, raw_json = S.run_gitleaks_on_tree(
        FIXTURE,
        config=cfg if cfg.is_file() else None,
    )
    # Also produce our gate's named report for body-leak proof.
    gate = S.scan_tree(FIXTURE)
    gate_report = gate.render_named_report()
    (WORK / "gate-named-report.txt").write_text(gate_report, encoding="utf-8")
    (WORK / "gitleaks-report.json").write_text(raw_json or "[]", encoding="utf-8")

    body_hits_gate = gate_report.count(body)
    body_hits_gl = (raw_json or "").count(body)
    token_hits_gate = gate_report.count(token)
    # gitleaks --redact should not echo the body; gate must not either.
    ok = (
        rc != 0
        and len(findings) >= 1
        and gate.blocking >= 1
        and body_hits_gate == 0
        and body_hits_gl == 0
        and token_hits_gate == 0
        and body not in gate_report
    )
    lines = [
        "NAMED PROBE 1: GITLEAKS EXIT + JSON FINDINGS + NO SECRET BODY",
        "PROBE-1-BEGIN:IMP-0004",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"fixture={FIXTURE.relative_to(REPO)}",
        f"gitleaks_exit_code={rc}",
        f"gitleaks_finding_count={len(findings)}",
        f"gate_blocking={gate.blocking}",
        f"gate_finding_count={len(gate.findings)}",
        f"secret_body_hits_in_gate_report={body_hits_gate}",
        f"secret_body_hits_in_gitleaks_json={body_hits_gl}",
        f"full_token_hits_in_gate_report={token_hits_gate}",
        f"prefix={S.PLANTED_CONTROL_PREFIX}",
        f"ok={ok}",
        "--- gate-named-report ---",
        gate_report.rstrip(),
        "--- end-gate-named-report ---",
        "PROBE-1-COMPLETE:IMP-0004",
        "SUCCESS:IMP-0004-probe1" if ok else "FAILED:IMP-0004-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    RAW.write_text(raw, encoding="utf-8")
    meas = {
        "ok": ok,
        "gitleaks_exit_code": rc,
        "gitleaks_finding_count": len(findings),
        "gate_blocking": gate.blocking,
        "gate_finding_count": len(gate.findings),
        "secret_body_hits_gate_report": body_hits_gate,
        "secret_body_hits_gitleaks_json": body_hits_gl,
        "full_token_hits_gate_report": token_hits_gate,
        "prefix": S.PLANTED_CONTROL_PREFIX,
        "fixture": str(FIXTURE.relative_to(REPO)),
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
