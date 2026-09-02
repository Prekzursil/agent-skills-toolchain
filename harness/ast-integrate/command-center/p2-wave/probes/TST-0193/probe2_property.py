#!/usr/bin/env python3
"""Probe 2: property test over 300 injection payloads plus source scan.

PASS: every payload reaches every sink byte-identical, the canary file is
never created, the pipeline source does not enable subprocess shell mode,
and a sampled splice-eval of dollar-paren payloads still creates the canary
(non-vacuous: the property is not 'nothing ever fires').
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from payloads import injection_payloads  # noqa: E402
from tools.shell.param_pipeline import (  # noqa: E402
    SINKS,
    run_pipeline,
    source_enables_shell,
    tools_ok,
    unsafe_splice_eval,
)

PIPELINE_SRC = REPO / "tools" / "shell" / "param_pipeline.py"


def main() -> int:
    tools = tools_ok()
    if not (tools["bash_exists"] and tools["printf_exists"] and tools["cat_exists"]):
        print("FAILED:TST-0193-probe2 missing bash/printf/cat")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="tst0193-p2-"))
    canary = tmp / "CANARY.marker"
    rows = injection_payloads(str(canary))
    if len(rows) != 300:
        print(f"FAILED:TST-0193-probe2 expected 300 payloads got {len(rows)}")
        return 1

    shell_on = source_enables_shell(PIPELINE_SRC)
    mismatches: list[dict[str, str]] = []
    canary_hits = 0
    family_ok: Counter[str] = Counter()

    for item in rows:
        canary.unlink(missing_ok=True)
        records = run_pipeline(
            item["value"], workdir=tmp / "pipe" / item["token"], canary=canary
        )
        if canary.is_file():
            canary_hits += 1
            mismatches.append(
                {
                    "token": item["token"],
                    "family": item["family"],
                    "why": "canary-present",
                }
            )
            continue
        bad = [r.sink for r in records if not r.literal]
        if bad:
            mismatches.append(
                {
                    "token": item["token"],
                    "family": item["family"],
                    "why": "literal-mismatch:" + ",".join(bad),
                    "sent_len": str(len(item["value"])),
                    "recv": records[0].received[:80] if records else "",
                }
            )
            continue
        family_ok[item["family"]] += 1

    # Non-vacuous: splice-eval a clean dollar-paren payload (the property
    # corpus suffixes a token; the detector uses the unsuffixed form).
    sample_canary = tmp / "SAMPLE.marker"
    sample_payload = f"$(touch {sample_canary})"
    sample_canary.unlink(missing_ok=True)
    unsafe_splice_eval(sample_payload, cwd=str(tmp))
    sample_fired = sample_canary.is_file()
    sample_canary.unlink(missing_ok=True)

    substitutionish = sum(
        1
        for r in rows
        if "$(" in r["value"] or "`" in r["value"] or "%" in r["value"]
    )

    ok = (
        not shell_on
        and canary_hits == 0
        and not mismatches
        and sample_fired
        and substitutionish >= 200
        and len(rows) == 300
        and sum(family_ok.values()) == 300
    )
    report = {
        "probe": "probe2-property-300",
        "unit_id": "TST-0193",
        "pass": ok,
        "payload_count": len(rows),
        "sinks": list(SINKS),
        "literal_pass_count": sum(family_ok.values()),
        "canary_hits": canary_hits,
        "mismatch_count": len(mismatches),
        "mismatches_head": mismatches[:8],
        "family_ok": dict(family_ok),
        "substitution_token_count": substitutionish,
        "source_enables_shell": shell_on,
        "sample_splice_eval_fired": sample_fired,
        "pipeline": str(PIPELINE_SRC.relative_to(REPO).as_posix()),
        "canary_path": str(canary),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    shutil.rmtree(tmp, ignore_errors=True)
    if not ok:
        print("FAILED:TST-0193-probe2 property test over 300 payloads")
        return 1
    print(
        "SUCCESS:TST-0193-probe2 300 payloads literal at every sink; "
        "canary absent; splice sample still fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
