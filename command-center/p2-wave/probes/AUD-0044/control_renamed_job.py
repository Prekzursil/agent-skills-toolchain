#!/usr/bin/env python3
"""AUD-0044 control: renamed job in scratch workflow → non-empty symmetric diff.

tests_required:
  control: confirm the comparator reports a non-empty symmetric difference on a
  deliberately renamed job in a scratch workflow

Uses fixtures under probes/AUD-0044/fixtures/ — does NOT mutate live workflows.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE))
from compare_contexts import compare, yaml_job_names  # noqa: E402

OUT_JSON = PROBE / "control-renamed-job.json"
OUT_RAW = PROBE / "control-renamed-job.raw.txt"
BASELINE = PROBE / "fixtures" / "scratch-workflow-baseline.yml"
RENAMED = PROBE / "fixtures" / "scratch-workflow-renamed.yml"
P1_JSON = PROBE / "probe1-required-status-checks.json"

# Fallback required set used only if probe1 is unavailable (control stays hermetic).
FALLBACK_REQUIRED = [
    "gate-lint-format (ruff)",
    "gate-types (basedpyright)",
    "gate-tests-coverage (node workspaces)",
    "gate-tests-coverage (python packages)",
    "gate-sast (opengrep)",
    "gate-secrets (gitleaks)",
    "gate-deps (osv-scanner)",
]


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines: list[str] = []

    if P1_JSON.is_file():
        p1 = json.loads(P1_JSON.read_text(encoding="utf-8"))
        required = list(p1.get("required_status_checks") or [])
        required_source = "probe1-required-status-checks.json"
    else:
        required = list(FALLBACK_REQUIRED)
        required_source = "FALLBACK_REQUIRED (probe1 missing)"

    if not required:
        # Still exercise the fixture rename against the fallback so the control
        # stays meaningful even when probe1 recorded an empty required set.
        required = list(FALLBACK_REQUIRED)
        required_source = "FALLBACK_REQUIRED (probe1 required empty)"

    baseline_text = BASELINE.read_text(encoding="utf-8")
    renamed_text = RENAMED.read_text(encoding="utf-8")
    baseline_names = yaml_job_names(baseline_text)
    renamed_names = yaml_job_names(renamed_text)

    baseline_cmp = compare(required, baseline_names)
    renamed_cmp = compare(required, renamed_names)

    baseline_empty = baseline_cmp["symmetric_difference_count"] == 0
    renamed_nonempty = renamed_cmp["symmetric_difference_count"] > 0
    ok = baseline_empty and renamed_nonempty

    raw_lines.append(f"required_source={required_source}\n")
    raw_lines.append(f"required={required}\n")
    raw_lines.append(f"baseline_job_names={baseline_names}\n")
    raw_lines.append(f"renamed_job_names={renamed_names}\n")
    raw_lines.append(
        f"baseline_symmetric_difference_count="
        f"{baseline_cmp['symmetric_difference_count']}\n"
    )
    raw_lines.append(
        f"renamed_symmetric_difference_count="
        f"{renamed_cmp['symmetric_difference_count']}\n"
    )
    raw_lines.append(
        f"renamed_required_but_never_emitted="
        f"{renamed_cmp['required_but_never_emitted']}\n"
    )
    raw_lines.append(
        f"renamed_emitted_but_not_required={renamed_cmp['emitted_but_not_required']}\n"
    )
    raw_lines.append(f"ok={ok} (expect baseline_empty AND renamed_nonempty)\n")

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "probe": "AUD-0044-control-renamed-job",
        "started_at": started,
        "ended_at": ended,
        "tests_required": (
            "control: confirm the comparator reports a non-empty symmetric "
            "difference on a deliberately renamed job in a scratch workflow"
        ),
        "required_source": required_source,
        "required_status_checks": required,
        "fixtures": {
            "baseline": str(BASELINE.relative_to(PROBE.parent.parent.parent.parent)),
            "renamed": str(RENAMED.relative_to(PROBE.parent.parent.parent.parent)),
            "deliberate_rename": {
                "from": "gate-tests-coverage (python packages)",
                "to": "gate-tests-coverage (python packages RENAMED)",
            },
        },
        "baseline_job_names": baseline_names,
        "renamed_job_names": renamed_names,
        "baseline_compare": baseline_cmp,
        "renamed_compare": renamed_cmp,
        "expect": {
            "baseline_symmetric_difference_empty": True,
            "renamed_symmetric_difference_nonempty": True,
        },
        "observed": {
            "baseline_symmetric_difference_empty": baseline_empty,
            "renamed_symmetric_difference_nonempty": renamed_nonempty,
            "renamed_symmetric_difference_count": renamed_cmp[
                "symmetric_difference_count"
            ],
        },
        "ok": ok,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("".join(raw_lines), encoding="utf-8")
    print(
        f"control ok={ok} baseline_symdiff={baseline_cmp['symmetric_difference_count']} "
        f"renamed_symdiff={renamed_cmp['symmetric_difference_count']}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
