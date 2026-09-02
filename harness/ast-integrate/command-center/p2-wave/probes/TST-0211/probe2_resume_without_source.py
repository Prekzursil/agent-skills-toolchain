#!/usr/bin/env python3
"""Probe 2: resume when the credential source is removed (catalog evidence signal b).

PASS: resume without the env source fails with CREDENTIAL_SOURCE_MISSING
(named, non-hanging). Resume with the source present re-acquires the secret,
including a rotated value. The persisted non-secret param is used even when
the original invocation map is gone.

Both-states: a naive checkpoint that stored plaintext resumes without the
source — that is the broken world this probe is built to distinguish.
"""
from __future__ import annotations

import json
import sys

HERE = __import__("pathlib").Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools" / "agentspec"))

from agentspec.checkpoint import (  # noqa: E402
    MISSING_CODE,
    CredentialSourceMissing,
    resume,
)
from harness import (  # noqa: E402
    CANARY,
    PLAIN_PARAM,
    PLAIN_VALUE,
    ROTATED,
    SECRET_PARAM,
    SECRET_REF,
    honest_checkpoint_bytes,
    naive_checkpoint_bytes,
)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAILED:TST-0211-probe2 {msg}")


def main() -> int:
    honest = honest_checkpoint_bytes()
    naive = naive_checkpoint_bytes()

    # Original argv gone: only environ + checkpoint.
    with_source = resume(honest, {SECRET_REF: CANARY})
    _need(with_source[SECRET_PARAM] == CANARY, "resume with source did not re-acquire canary")
    _need(with_source[PLAIN_PARAM] == PLAIN_VALUE, "resume dropped persisted non-secret")

    rotated = resume(honest, {SECRET_REF: ROTATED})
    _need(rotated[SECRET_PARAM] == ROTATED, "resume did not pick up rotated secret")
    _need(rotated[PLAIN_PARAM] == PLAIN_VALUE, "rotated resume dropped non-secret")

    missing_named = False
    missing_code = ""
    try:
        resume(honest, {})
    except CredentialSourceMissing as exc:
        missing_named = True
        missing_code = exc.code
    _need(missing_named, "resume without source did not fail")
    _need(missing_code == f"{MISSING_CODE}:{SECRET_REF}", f"wrong missing code {missing_code}")

    empty = False
    try:
        resume(honest, {SECRET_REF: ""})
    except CredentialSourceMissing:
        empty = True
    _need(empty, "empty credential source was treated as present")

    # Naive control: plaintext in the checkpoint lets resume succeed with no source.
    naive_doc = json.loads(naive.decode("utf-8"))
    naive_values = {n: r["value"] for n, r in naive_doc["param_bindings"].items()}
    _need(naive_values[SECRET_PARAM] == CANARY, "naive control lost plaintext")
    _need(CANARY.encode("utf-8") in naive, "naive bytes lost canary")

    print(
        json.dumps(
            {
                "probe": "probe2-resume-without-source",
                "unit_id": "TST-0211",
                "pass": True,
                "resume_with_source": True,
                "resume_rotated": True,
                "plain_used_on_resume": True,
                "missing_source_code": missing_code,
                "empty_source_refused": True,
                "naive_resume_without_source_would_succeed": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0211-probe2 resume re-acquires or fails named without source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
