#!/usr/bin/env python3
"""Unresolved-question ledger with an executable settling experiment per entry (IMP-0341).

Every unresolved question a council leaves behind must name the EXACT experiment that
would settle it. The module separates two layers so that a vague entry is caught by the
right one:

* **schema** (:func:`schema_errors_entry`): an entry needs ``id``, ``question`` and a
  non-empty ``settling_experiment``; an object experiment needs a ``command``. A bare
  string is *schema-present* (the schema cannot tell an aspiration from an experiment),
  so it passes here and is left to the audit.
* **executability audit** (:func:`audit_entry` / :func:`audit_ledger`): a named
  experiment is an object whose ``command`` resolves on PATH or disk, whose declared
  ``inputs`` exist on disk, and whose ``oracle`` (``kind`` + ``expect``) says which
  observation settles the question. Anything else - notably an aspiration such as
  ``"investigate further"`` - fails with machine-readable reason codes.

:func:`stopping_condition_15` is the program gate on residual unknowns: a run may stop
only when every leftover carries an executable settling experiment. ``fail_count`` is
always the length of the failing per-entry rows, never a summary.

CLI::

    python3 -B tools/council/outcomes/unresolved.py --root . --audit ledger.json
    python3 -B tools/council/outcomes/unresolved.py --root . --audit ledger.json --schema-only
    python3 -B tools/council/outcomes/unresolved.py --root . --capture council-artifact.json
    python3 -B tools/council/outcomes/unresolved.py --print-schema

The last stdout line is always a single JSON document; the exit code is 1 when the audit
(or schema check) has failures and 0 otherwise.
"""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json:IMP-0341 stopping-condition-15 "
    "_USER-PROMPTS.md:11392; BLD-0029 named-experiment rule (command, input, observation)"
)
SCHEMA_REL = "tools/council/outcomes/unresolved.schema.json"
STOPPING_CONDITION_ID = 15

ORACLE_KINDS: tuple[str, ...] = (
    "exit-code",
    "stdout-contains",
    "stdout-equals",
    "stderr-contains",
    "file-exists",
    "file-sha256",
    "json-path",
    "predicate",
)

#: Phrases that mark a settling "experiment" as an aspiration rather than a procedure.
ASPIRATION_MARKERS: tuple[str, ...] = (
    "investigate",
    "look into",
    "explore",
    "consider",
    "think about",
    "revisit",
    "follow up",
    "later",
    "someday",
    "eventually",
    "figure out",
    "wait and see",
    "further",
    "more research",
    "tbd",
    "todo",
)

_SCRIPT_SUFFIXES = (".py", ".sh", ".ps1", ".js", ".mjs", ".rb")

ENTRY_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_REL,
    "title": "council unresolved-question ledger entry",
    "description": (
        "One unresolved question left by a council together with the settling experiment "
        "that would close it. A string experiment is schema-present but audit-failing."
    ),
    "type": "object",
    "required": ["id", "question", "settling_experiment"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "question": {"type": "string", "minLength": 1},
        "source": {"type": "string"},
        "impact_statement": {"type": "string"},
        "settling_experiment": {
            "oneOf": [
                {"type": "string", "minLength": 1},
                {
                    "type": "object",
                    "required": ["command"],
                    "properties": {
                        "command": {"type": "string", "minLength": 1},
                        "inputs": {"type": "array", "items": {"type": "string"}},
                        "oracle": {
                            "type": "object",
                            "required": ["kind", "expect"],
                            "properties": {
                                "kind": {"type": "string", "enum": list(ORACLE_KINDS)},
                            },
                        },
                    },
                },
            ]
        },
    },
}


def schema_document() -> dict[str, Any]:
    """Return a fresh copy of the entry schema (what :data:`SCHEMA_REL` would hold)."""
    return json.loads(json.dumps(ENTRY_SCHEMA))


def load_path(path: Path | str) -> list[dict[str, Any]]:
    """Load ledger entries from a JSON file.

    Accepts a bare list of entries, an object with one of the ``entries`` /
    ``leftovers`` / ``unresolved`` / ``items`` lists, or a single entry object.
    Non-object rows are dropped.
    """
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if isinstance(doc, dict):
        for key in ("entries", "leftovers", "unresolved", "items"):
            rows = doc.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
        if "id" in doc or "question" in doc:
            return [doc]
    return []


def schema_errors_entry(entry: Any) -> list[str]:
    """Schema-level errors for one entry (empty list means schema-valid).

    ``settling_experiment`` must be present and non-empty. An object experiment must
    carry a non-empty ``command``. A non-empty string experiment is schema-present;
    only :func:`audit_entry` can fail it.
    """
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    errors: list[str] = []
    ident = entry.get("id")
    if not isinstance(ident, str) or not ident.strip():
        errors.append("missing id")
    question = entry.get("question")
    if not isinstance(question, str) or not question.strip():
        errors.append("missing question")
    if "settling_experiment" not in entry:
        errors.append("missing settling_experiment")
        return errors
    exp = entry["settling_experiment"]
    if exp is None or (isinstance(exp, str) and not exp.strip()):
        errors.append("empty settling_experiment")
        return errors
    if isinstance(exp, dict):
        if not exp:
            errors.append("empty settling_experiment object")
            return errors
        command = exp.get("command")
        if not isinstance(command, str) or not command.strip():
            errors.append("command missing from settling_experiment")
        inputs = exp.get("inputs")
        if inputs is not None and not (
            isinstance(inputs, list) and all(isinstance(i, str) for i in inputs)
        ):
            errors.append("settling_experiment.inputs must be a list of paths")
        oracle = exp.get("oracle")
        if oracle is not None and not isinstance(oracle, dict):
            errors.append("settling_experiment.oracle must be an object")
        return errors
    if isinstance(exp, str):
        return errors
    errors.append(f"settling_experiment has unsupported type {type(exp).__name__}")
    return errors


def schema_errors(entries: Iterable[Any]) -> list[str]:
    """Flattened schema errors over a ledger, prefixed with the entry id/index."""
    out: list[str] = []
    for i, entry in enumerate(entries):
        ident = entry.get("id") if isinstance(entry, dict) else None
        label = str(ident) if ident else f"#{i}"
        out.extend(f"{label}: {err}" for err in schema_errors_entry(entry))
    return out


def _is_aspiration(text: str) -> bool:
    """True when a string experiment reads as an intention rather than a procedure."""
    low = " ".join(text.lower().split())
    if any(marker in low for marker in ASPIRATION_MARKERS):
        return True
    tokens = low.split()
    invocable = any(
        "/" in tok or "\\" in tok or tok.endswith(_SCRIPT_SUFFIXES) or tok.startswith("-")
        for tok in tokens
    )
    return not invocable


def _exists_under(rel: str, root: Path | None) -> bool:
    cand = Path(rel)
    if cand.is_absolute():
        return cand.exists()
    if root is not None and (Path(root) / rel).exists():
        return True
    return cand.exists()


def _resolve_command(command: str, root: Path | None) -> tuple[bool, str]:
    """Resolve the executable (and any script argument) of a command line.

    Returns ``(exists, detail)``. The first token must be on PATH or on disk (absolute,
    or relative to ``root``/cwd); script-looking arguments (``*.py`` etc.) must also
    exist, because an interpreter without its script cannot run the experiment.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as exc:
        return False, f"command {command!r} is not parseable: {exc}"
    if not tokens:
        return False, "command is empty"
    exe = tokens[0]
    on_disk = shutil.which(exe) is not None or _exists_under(exe, root)
    if not on_disk:
        return False, f"command {command!r} is not on PATH or disk"
    for arg in tokens[1:]:
        if arg.startswith("-"):
            continue
        if arg.lower().endswith(_SCRIPT_SUFFIXES) and not _exists_under(arg, root):
            return False, f"command {command!r} names script {arg!r} that is not on disk"
    return True, exe


def _oracle_defined(oracle: Any) -> bool:
    return (
        isinstance(oracle, dict)
        and isinstance(oracle.get("kind"), str)
        and bool(oracle.get("kind", "").strip())
        and "expect" in oracle
    )


def audit_entry(entry: Any, root: Path | str | None = None, index: int = 0) -> dict[str, Any]:
    """Executability audit of one entry.

    Row shape: ``id``, ``index``, ``ok``, ``command_exists``, ``inputs_exist``,
    ``oracle_defined`` and ``reasons`` (list of ``{"code", "detail"}``). Reason codes:
    ``schema-invalid``, ``unstructured-experiment``, ``aspiration``, ``command-missing``,
    ``input-undeclared``, ``input-missing``, ``oracle-undefined``, ``oracle-kind-unknown``.
    ``ok`` is true only when the reasons list is empty.
    """
    root_path = Path(root) if root is not None else None
    reasons: list[dict[str, str]] = []
    ident = entry.get("id") if isinstance(entry, dict) else None
    row: dict[str, Any] = {
        "id": ident if isinstance(ident, str) else f"#{index}",
        "index": index,
        "ok": False,
        "command_exists": False,
        "inputs_exist": False,
        "oracle_defined": False,
        "reasons": reasons,
    }
    for err in schema_errors_entry(entry):
        reasons.append({"code": "schema-invalid", "detail": err})
    exp = entry.get("settling_experiment") if isinstance(entry, dict) else None
    if not isinstance(exp, dict):
        if isinstance(exp, str) and exp.strip():
            reasons.append(
                {
                    "code": "unstructured-experiment",
                    "detail": (
                        "settling_experiment is a string; a named experiment is an object "
                        "with command, inputs, and oracle"
                    ),
                }
            )
            if _is_aspiration(exp):
                reasons.append(
                    {
                        "code": "aspiration",
                        "detail": f"settling_experiment names an aspiration: {exp.strip()!r}",
                    }
                )
        row["ok"] = not reasons
        return row

    command = exp.get("command")
    if isinstance(command, str) and command.strip():
        exists, detail = _resolve_command(command, root_path)
        row["command_exists"] = exists
        if not exists:
            reasons.append({"code": "command-missing", "detail": detail})
    else:
        reasons.append({"code": "command-missing", "detail": "settling_experiment has no command"})

    inputs = exp.get("inputs")
    if isinstance(inputs, list) and inputs:
        missing = [str(i) for i in inputs if not _exists_under(str(i), root_path)]
        row["inputs_exist"] = not missing
        if missing:
            reasons.append(
                {"code": "input-missing", "detail": "declared inputs not on disk: " + ", ".join(missing)}
            )
    else:
        reasons.append(
            {
                "code": "input-undeclared",
                "detail": "settling_experiment declares no inputs; a named experiment names what it reads",
            }
        )

    oracle = exp.get("oracle")
    row["oracle_defined"] = _oracle_defined(oracle)
    if not row["oracle_defined"]:
        reasons.append({"code": "oracle-undefined", "detail": "oracle must be an object with kind and expect"})
    elif oracle.get("kind") not in ORACLE_KINDS:
        reasons.append(
            {
                "code": "oracle-kind-unknown",
                "detail": f"oracle kind {oracle.get('kind')!r} is not one of {list(ORACLE_KINDS)}",
            }
        )
    row["ok"] = not reasons
    return row


def audit_ledger(entries: Iterable[Any], root: Path | str | None = None) -> dict[str, Any]:
    """Audit every entry; counts are derived from the per-entry rows."""
    rows = [audit_entry(entry, root=root, index=i) for i, entry in enumerate(entries)]
    failures = [r for r in rows if not r["ok"]]
    return {
        "spec_anchor": SPEC_ANCHOR,
        "entry_count": len(rows),
        "pass_count": len(rows) - len(failures),
        "fail_count": len(failures),
        "derived": True,
        "entries": rows,
        "failures": failures,
        "failing_ids": [r["id"] for r in failures],
    }


def stopping_condition_15(entries: Iterable[Any], root: Path | str | None = None) -> dict[str, Any]:
    """Program stopping condition 15: stop only when every leftover is executable.

    An empty ledger (no residual unknowns) allows stopping. Any entry whose settling
    experiment fails the audit blocks the stop and is listed in ``blocking_ids``.
    """
    report = audit_ledger(entries, root=root)
    stop_allowed = report["fail_count"] == 0
    if stop_allowed:
        reason = (
            f"all {report['entry_count']} unresolved entries name an executable settling experiment"
            if report["entry_count"]
            else "no unresolved entries recorded"
        )
    else:
        reason = (
            f"{report['fail_count']} of {report['entry_count']} unresolved entries name an "
            "aspiration or an unexecutable experiment"
        )
    return {
        "condition": STOPPING_CONDITION_ID,
        "spec_anchor": SPEC_ANCHOR,
        "stop_allowed": stop_allowed,
        "verdict": "STOP-ALLOWED" if stop_allowed else "STOP-BLOCKED",
        "entry_count": report["entry_count"],
        "executable_count": report["pass_count"],
        "blocking_count": report["fail_count"],
        "blocking_ids": report["failing_ids"],
        "reason": reason,
    }


def capture(council_artifact: dict[str, Any], source: str = "council") -> list[dict[str, Any]]:
    """Capture the unresolved leftovers of a council artifact as ledger entries.

    Leftovers are read from ``unresolved`` / ``leftovers`` / ``open_questions`` or from
    ``outcomes.unresolved_questions`` / ``outcomes.leftovers`` / ``questions``. String
    rows become entries with a positional ``CQ-STRING-<i>`` id. Capture never invents a
    ``settling_experiment``: a leftover that did not name one stays schema-invalid so the
    ledger shows the gap. An artifact that records no leftovers at all yields a single
    ``CQ-NONE-RECORDED`` entry stating that fact.
    """
    leftovers = (
        council_artifact.get("unresolved")
        or council_artifact.get("leftovers")
        or council_artifact.get("open_questions")
        or []
    )
    outcomes = council_artifact.get("outcomes") or {}
    if isinstance(outcomes, dict):
        leftovers = leftovers or outcomes.get("unresolved_questions") or outcomes.get("leftovers") or []
    if not leftovers and isinstance(council_artifact.get("questions"), list):
        leftovers = council_artifact["questions"]
    out: list[dict[str, Any]] = []
    for i, row in enumerate(leftovers):
        if isinstance(row, str):
            out.append({"id": f"CQ-STRING-{i}", "question": row, "source": source})
            continue
        if not isinstance(row, dict):
            continue
        entry = dict(row)
        entry.setdefault("source", source)
        out.append(entry)
    if not out:
        out.append(
            {
                "id": "CQ-NONE-RECORDED",
                "question": (
                    f"{council_artifact.get('charter_id') or council_artifact.get('council_id') or source}: "
                    "the council artifact recorded no unresolved questions - is that true or unrecorded?"
                ),
                "source": source,
            }
        )
    return out


def _emit(doc: dict[str, Any], summary: str) -> None:
    print(summary)
    print(json.dumps(doc, sort_keys=True, ensure_ascii=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="unresolved-question ledger audit")
    parser.add_argument("--root", default=".", help="repo root that relative commands/inputs resolve against")
    parser.add_argument("--audit", metavar="LEDGER", help="ledger JSON to audit")
    parser.add_argument("--capture", metavar="COUNCIL", help="council artifact JSON to capture leftovers from")
    parser.add_argument("--schema-only", action="store_true", help="with --audit: schema check only")
    parser.add_argument("--stop-check", action="store_true", help="with --audit: evaluate stopping condition 15")
    parser.add_argument("--print-schema", action="store_true", help="print the entry schema and exit")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.print_schema:
        _emit(schema_document(), f"schema {SCHEMA_REL}")
        return 0

    entries: list[dict[str, Any]] | None = None
    if args.capture:
        artifact = json.loads(Path(args.capture).read_text(encoding="utf-8"))
        if not isinstance(artifact, dict):
            print("FAILED:unresolved council artifact is not an object", file=sys.stderr)
            return 2
        entries = capture(artifact, source=Path(args.capture).name)
        if not args.audit:
            errs = schema_errors(entries)
            _emit(
                {"entries": entries, "entry_count": len(entries), "schema_errors": errs, "schema_ok": not errs},
                f"captured {len(entries)} leftovers schema_errors={len(errs)}",
            )
            return 0
    if args.audit:
        ledger = load_path(args.audit)
        entries = (entries or []) + ledger
    if entries is None:
        parser.print_usage(file=sys.stderr)
        return 2

    if args.schema_only:
        errs = schema_errors(entries)
        _emit(
            {"entry_count": len(entries), "schema_errors": errs, "schema_ok": not errs, "schema": SCHEMA_REL},
            f"schema entries={len(entries)} errors={len(errs)}",
        )
        return 0 if not errs else 1
    if args.stop_check:
        gate = stopping_condition_15(entries, root=root)
        _emit(gate, f"stopping-condition-15 {gate['verdict']} blocking={gate['blocking_count']}")
        return 0 if gate["stop_allowed"] else 1
    report = audit_ledger(entries, root=root)
    _emit(
        report,
        f"audit entries={report['entry_count']} pass={report['pass_count']} fail={report['fail_count']}",
    )
    return 0 if report["fail_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
