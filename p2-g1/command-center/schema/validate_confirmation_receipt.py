#!/usr/bin/env python3
"""CNF-0001 confirmation-receipt validator CLI + library.

Rejects any receipt missing claim_id, confirmer identity, source_probe
fingerprint, a mechanically different verifier_probe fingerprint, verbatim
probe output, a verdict from the closed set, or a residual statement.

The question this instrument must answer NO to: does a receipt with
verdict=CONFIRMED and an EMPTY source_probe pass?

That is the measured hole in claim_gate.py: an absent source normalises
to empty strings that any verifier trivially differs from, so
same-probe-rerun never fires and CONFIRMED exits 0. Empty-source MUST
be checked before fingerprint comparison. Evidence is the process exit
code, not the presence of a rule in the schema text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SCHEMA_DIR / "confirmation-receipt.schema.json"
QUESTION = (
    "does a receipt with verdict=CONFIRMED and an EMPTY source_probe pass?"
)
ANSWER_NO = "NO"
VERDICTS = (
    "CONFIRMED",
    "REFUTED",
    "PARTIAL",
    "NOT-CHECKED",
    "BLOCKED",
)
# Axes used to fingerprint a probe object. `command` is not an independence
# axis: a different command string with the same tool/shell/field/kind is
# the same query re-run.
FP_AXES = ("tool", "shell", "field", "kind")


def load_schema(path: Path | None = None) -> dict:
    target = path or SCHEMA_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def _format_schema_error(err: jsonschema.ValidationError) -> str:
    loc = "/".join(str(p) for p in err.path) or "<root>"
    return f"{loc}: {err.message}"


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _identity_present(value: Any) -> bool:
    if _nonempty_text(value):
        return True
    if isinstance(value, dict):
        for key in ("id", "name", "agent_id"):
            if _nonempty_text(value.get(key)):
                return True
        return any(_nonempty_text(v) for v in value.values() if isinstance(v, str))
    return False


def _probe_empty(value: Any) -> bool:
    """Zero signals: missing, empty string, empty object, all-blank axes."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        if not value:
            return True
        if any(_nonempty_text(value.get(k)) for k in FP_AXES + ("id", "command", "engine")):
            return False
        fp = value.get("fingerprint")
        if isinstance(fp, (str, list, dict)) and fp:
            return False
        return not any(
            (isinstance(v, str) and v.strip()) or (isinstance(v, (list, dict)) and v)
            for v in value.values()
        )
    return True


def fingerprint(probe: Any) -> list[Any]:
    """Stable fingerprint. Object axes match the live fixture pair."""
    if isinstance(probe, dict):
        return ["obj", *[probe.get(k) for k in FP_AXES]]
    if isinstance(probe, str):
        return ["str", probe]
    return ["other", repr(probe)]


def semantic_violations(doc: Any) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if not isinstance(doc, dict):
        found.append(
            {
                "rule": "schema-invalid",
                "detail": "receipt is not a JSON object",
            }
        )
        return found

    claim_id = doc.get("claim_id")
    if not _nonempty_text(claim_id):
        found.append({"rule": "missing-claim_id", "detail": "claim_id is missing or empty"})

    if not _identity_present(doc.get("confirmer")):
        found.append(
            {
                "rule": "missing-confirmer",
                "detail": "confirmer identity is missing or empty",
            }
        )

    if not _nonempty_text(doc.get("verbatim_probe_output")):
        found.append(
            {
                "rule": "missing-verbatim-output",
                "detail": "verbatim_probe_output is missing or empty",
            }
        )

    if not _nonempty_text(doc.get("residual")):
        found.append(
            {
                "rule": "missing-residual",
                "detail": "residual statement is missing or empty",
            }
        )

    verdict = doc.get("verdict")
    if not _nonempty_text(verdict) or str(verdict) not in VERDICTS:
        found.append(
            {
                "rule": "invalid-verdict",
                "detail": (
                    f"verdict {verdict!r} is not in the closed set "
                    "{" + ",".join(VERDICTS) + "}"
                ),
            }
        )

    source = doc.get("source_probe") if "source_probe" in doc else None
    verifier = doc.get("verifier_probe") if "verifier_probe" in doc else None

    # MUST run before fingerprint comparison. An empty source is zero
    # signals; treating it as "different from the verifier" is the hole.
    if _probe_empty(source):
        found.append(
            {
                "rule": "empty-source",
                "detail": (
                    "source_probe is absent or empty; that is zero signals, "
                    "not one. CONFIRMED|REFUTED cannot pass this shape."
                ),
            }
        )
        return found

    if _probe_empty(verifier):
        found.append(
            {
                "rule": "empty-verifier",
                "detail": (
                    "verifier_probe is absent or empty; a confirmation "
                    "needs a mechanically different second signal"
                ),
            }
        )
        return found

    src_fp = fingerprint(source)
    ver_fp = fingerprint(verifier)
    if src_fp == ver_fp:
        found.append(
            {
                "rule": "same-probe-rerun",
                "detail": (
                    "verifier_probe fingerprint is identical to source_probe; "
                    f"fingerprint={src_fp!r}"
                ),
            }
        )
    return found


def validate_receipt(doc: Any, schema: dict | None = None) -> dict:
    schema = schema if schema is not None else load_schema()
    violations = semantic_violations(doc)
    try:
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(doc):
            violations.append(
                {"rule": "schema-invalid", "detail": _format_schema_error(err)}
            )
    except jsonschema.exceptions.SchemaError as exc:
        violations.append(
            {
                "rule": "schema-invalid",
                "detail": f"schema itself is invalid: {exc}",
            }
        )

    rules: list[str] = []
    for item in violations:
        rule = item.get("rule")
        if isinstance(rule, str) and rule not in rules:
            rules.append(rule)
    ok = not violations
    return {
        "answer_if_empty_source_confirmed": ANSWER_NO,
        "exit_code": 0 if ok else 1,
        "ok": ok,
        "path": "",
        "question": QUESTION,
        "rules": rules,
        "schema_path": str(SCHEMA_PATH.resolve()),
        "violations": violations,
    }


def validate_path(path: Path, schema: dict | None = None) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "answer_if_empty_source_confirmed": ANSWER_NO,
            "exit_code": 2,
            "ok": False,
            "path": str(path.resolve()),
            "question": QUESTION,
            "rules": ["unparseable"],
            "schema_path": str(SCHEMA_PATH.resolve()),
            "violations": [
                {
                    "rule": "unparseable",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ],
        }
    report = validate_receipt(doc, schema)
    report["path"] = str(path.resolve())
    return report


def _emit(report: dict) -> int:
    printed = dict(report)
    print(json.dumps(printed, indent=2, sort_keys=True))
    code = int(printed.get("exit_code") or (0 if printed.get("ok") else 1))
    rules = printed.get("rules") or []
    if printed.get("ok") and code == 0:
        print("ACCEPT EXIT 0")
    else:
        joined = ",".join(str(r) for r in rules) or "reject"
        print(f"REJECT:{joined} EXIT {code}")
    return code


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("FAILED:validate_confirmation_receipt usage: <receipt.json>", file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"FAILED:validate_confirmation_receipt missing {path}", file=sys.stderr)
        return 2
    return _emit(validate_path(path))


if __name__ == "__main__":
    raise SystemExit(main())
