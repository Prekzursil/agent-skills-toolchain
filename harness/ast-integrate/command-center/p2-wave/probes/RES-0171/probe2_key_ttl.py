#!/usr/bin/env python3
"""Probe 2: key-field sensitivity, unmeasured TTL honesty, schema, negative control.

Independent of probe 1's fetch-counter path: this probe mutates key fields
one at a time, checks RES-0006 absence is declared, and requires the
design-spec schema to reject garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
import schema_ctl  # noqa: E402
from cache_key import REQUIRED_QUESTION_FIELDS  # noqa: E402
from policy import SOURCE_CLASSES, res0006_present  # noqa: E402

ART = (
    REPO
    / "command-center/research/deep-research-design"
    / "RES-0171-research-cache-key-and-resume.json"
)


def main() -> int:
    keys = S.run_key_sensitivity()
    clock = S.run_unmeasured_bucket_clock_free()
    corrupt = S.run_corrupt_never_served()
    print(
        json.dumps(
            {
                "key_sensitivity_pass": keys.get("pass"),
                "distinct_keys": keys.get("distinct_keys"),
                "omitted_backend_version_rejected": keys.get(
                    "omitted_backend_version_rejected"
                ),
                "clock": clock,
                "corrupt_pass": corrupt.get("pass"),
                "res0006_present": res0006_present(REPO),
                "n_classes": len(SOURCE_CLASSES),
            },
            sort_keys=True,
        )
    )
    if not keys.get("pass"):
        print("FAILED:RES-0171-probe2 key is not sensitive to every required field")
        return 1
    if not clock.get("pass"):
        print("FAILED:RES-0171-probe2 unmeasured bucket is not clock-free")
        return 1
    if not corrupt.get("pass"):
        print("FAILED:RES-0171-probe2 corrupted entry was served")
        return 1
    if res0006_present(REPO):
        print("FAILED:RES-0171-probe2 unexpected RES-0006 present without binding")
        return 1
    if not ART.is_file():
        print("FAILED:RES-0171-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:RES-0171" not in text:
        print("FAILED:RES-0171-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() != "SUCCESS":
        print(f"FAILED:RES-0171-probe2 state={doc.get('state')}")
        return 1
    payload = schema_ctl.domain_payload(doc)
    staleness = payload.get("staleness_policy") or {}
    if staleness.get("res0006_present") is not False:
        print("FAILED:RES-0171-probe2 artifact conceals RES-0006 absence")
        return 1
    if not staleness.get("unmeasured_uses_worst_case_default"):
        print("FAILED:RES-0171-probe2 unmeasured classes not bound to worst-case default")
        return 1
    recorded_fields = list((payload.get("cache_key") or {}).get("question_fields") or [])
    if recorded_fields != list(REQUIRED_QUESTION_FIELDS):
        print(f"FAILED:RES-0171-probe2 question_fields drift {recorded_fields}")
        return 1
    claims = payload.get("claims") or []
    if len(claims) < 4:
        print(f"FAILED:RES-0171-probe2 claims under-specified n={len(claims)}")
        return 1
    schema_errs = schema_ctl.errors(doc)
    if schema_errs:
        print("FAILED:RES-0171-probe2 schema rejected live artifact")
        for e in schema_errs[:8]:
            print(" ", e)
        return 1
    try:
        gcounts = schema_ctl.garbage_rejected()
    except AssertionError:
        print("FAILED:RES-0171-probe2 schema accepted garbage")
        return 1
    mutant = json.loads(text)
    mutant["evidence"] = []
    if not schema_ctl.errors(mutant):
        print("FAILED:RES-0171-probe2 schema accepted empty evidence")
        return 1
    kind_mutant = json.loads(text)
    if isinstance(kind_mutant.get("report"), dict):
        kind_mutant["report"]["kind"] = "not-a-design-spec"
    if not schema_ctl.errors(kind_mutant):
        print("FAILED:RES-0171-probe2 schema accepted wrong report.kind")
        return 1
    print(
        "fields_ok={n} omitted_rejected={o} schema_garbage_errs={e} classes={c}".format(
            n=keys["distinct_keys"],
            o=keys["omitted_backend_version_rejected"],
            e=sum(gcounts),
            c=len(SOURCE_CLASSES),
        )
    )
    print("SUCCESS:RES-0171-probe2 key-ttl-schema negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
