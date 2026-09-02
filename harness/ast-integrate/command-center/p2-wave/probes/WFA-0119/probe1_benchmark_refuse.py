#!/usr/bin/env python3
"""Probe 1: capability-superset vs retired-benchmark refusal (signals A and B).

Live re-run of the engine. A matrix-superset replacement whose notify behaviour
is disconnected must be refused even though signal A passes. A lossy replacement
missing notify in the matrix must be refused on signal A. The happy successor
must be accepted. Probes also check the emitted CertificationRecord agrees.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import supersession as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0119-decertification-and-supersession.json"


def main() -> int:
    ctrls = S.run_controls()
    ok, failed = S.controls_ok(ctrls)
    h, d, l = ctrls["happy"], ctrls["disconnected"], ctrls["lossy"]
    print(
        f"happy accepted={h['accepted']} a={h['signal_a']['pass']} "
        f"b={h['signal_b']['pass']} edge={h['superseded_by']}"
    )
    print(
        f"disconnected accepted={d['accepted']} a={d['signal_a']['pass']} "
        f"b={d['signal_b']['pass']} refusals={d['refusals']} "
        f"status={d['retired_status_after']}"
    )
    print(
        f"lossy accepted={l['accepted']} a={l['signal_a']['pass']} "
        f"b={l['signal_b']['pass']} missing={l['signal_a']['missing']} "
        f"refusals={l['refusals']}"
    )
    if not ok:
        print("FAILED:WFA-0119-probe1 " + ",".join(failed))
        return 1

    if d["independence_check"]["a_pass"] == d["independence_check"]["b_pass"]:
        print("FAILED:WFA-0119-probe1 signals-did-not-diverge-on-disconnected")
        return 1
    if "bk-notify" not in d["signal_b"]["cases_failed"]:
        print("FAILED:WFA-0119-probe1 disconnected-did-not-fail-retired-notify-case")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0119-probe1 artifact-missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0119-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0119" not in text:
        print("FAILED:WFA-0119-probe1 sentinel-absent")
        return 1
    tests = doc.get("tests") or {}
    if tests.get("failed_retired_benchmark_refused") is not True:
        print("FAILED:WFA-0119-probe1 artifact-missing-benchmark-refuse")
        return 1
    if tests.get("signals_a_and_b_diverge_on_disconnected") is not True:
        print("FAILED:WFA-0119-probe1 artifact-missing-divergence")
        return 1
    sup = doc.get("supersession") or {}
    if sup.get("superseded_by") != "wf-certified-intake-v2":
        print("FAILED:WFA-0119-probe1 artifact-edge-drift")
        return 1
    if doc.get("certified") is not True:
        print("FAILED:WFA-0119-probe1 artifact-not-certified")
        return 1
    print("SUCCESS:WFA-0119-probe1 benchmark-refuse independent-signals happy-accept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
