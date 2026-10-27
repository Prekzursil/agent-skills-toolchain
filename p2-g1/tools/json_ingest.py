"""Lenient-versus-strict JSON ingest for TST-0058 (rebuild, shard21-w2).

The estate rule this module enforces: a document the dev tool accepts and the
shipped client rejects is a green-not-live defect. Therefore:

  strict_loads   - RFC 8259 only (json.loads); rejects every json5-ism.
  lenient_loads  - the dev-tool ingest: DIAGNOSES json5-isms (comments,
                   trailing commas, single quotes) and then REFUSES them, so
                   ingest never accepts what the shipped client rejects.
  jsonc_loads    - the detector CONTROL: tolerates the isms (strip + normalise
                   then parse). Used only to prove the adversarial fixtures
                   are real json5-isms, never for production ingest.

decisions_agree / values_agree compute the lenient-vs-strict agreement matrix
over a corpus. ParseResult carries ism locations for diagnostics.

(g1-mod: real-surface rebuild 2026-10-25. The previous file was a decorative
stub whose every loader returned Result(ok=True) unconditionally - the exact
green-not-live pathology this unit exists to detect.)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "_t58_strict_json", Path(__file__).resolve().parent / "plugin" / "strict_json.py"
)
_sj = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_sj)

_C10 = chr(10)


@dataclass
class ParseResult:
    ok: bool
    status: str
    value: Any = None
    isms: list = field(default_factory=list)
    line: int | None = None
    column: int | None = None
    error: str = ""

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "status": self.status, "line": self.line,
                "column": self.column, "isms": self.isms, "error": self.error}


def _line_col(text: str, pos: int) -> tuple[int, int]:
    line = text.count(_C10, 0, pos) + 1
    last = text.rfind(_C10, 0, pos)
    return line, pos - last


def strict_loads(text: str) -> ParseResult:
    """RFC 8259 (shipped client). Rejects every json5-ism."""
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        line, col = _line_col(text, exc.pos)
        return ParseResult(ok=False, status="rejected", line=line, column=col,
                           error=f"JSONDecodeError: {exc.msg} at line {line} column {col}")
    return ParseResult(ok=True, status="accepted", value=value)


def jsonc_loads(text: str) -> ParseResult:
    """Detector control only: tolerates json5-isms (strip comments/trailing
    commas, normalise single quotes and bare keys) then parses. NOT for
    production ingest."""
    stripped = _sj.strip_json5(text)
    # single-quoted values: {'a': 'x'} -> {"a": "x"}
    stripped = re.sub(r"'([^'\n]*)'", lambda m: '"' + m.group(1).replace('"', '\\"') + '"', stripped)
    # single-quoted keys: {'a': 1} -> {"a": 1}
    stripped = re.sub(r"([{,]\s*)'([^'\n]*)'(\s*:)", lambda m: m.group(1) + '"' + m.group(2).replace('"', '\\"') + '"' + m.group(3), stripped)
    # bare keys: {a: 1} -> {"a": 1}
    stripped = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)(\s*:)", r'\1"\2"\3', stripped)
    # trailing commas left against a brace after comment stripping: {.. , } -> {.. }
    stripped = re.sub(r",\s*([}\]])", r"\1", stripped)
    stripped = re.sub(r",\s*([}\]])", r"\1", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError as exc:
        line, col = _line_col(stripped, exc.pos)
        return ParseResult(ok=False, status="rejected", line=line, column=col,
                           error=f"JSONDecodeError after jsonc normalisation: {exc.msg}")
    return ParseResult(ok=True, status="accepted", value=value)


def lenient_loads(text: str) -> ParseResult:
    """Dev-tool ingest: diagnose then REFUSE json5-isms (agrees with strict)."""
    isms = _sj.locate_json5_isms(text)
    if isms:
        kinds = sorted({str(i.get("kind", i)) if isinstance(i, dict) else str(i) for i in isms})
        first = isms[0]
        pos = int(first.get("pos", 0)) if isinstance(first, dict) and isinstance(first.get("pos"), int) else 0
        line, col = _line_col(text, min(pos, len(text) - 1)) if text else (1, 1)
        return ParseResult(ok=False, status="refused", isms=isms, line=line, column=col,
                           error=f"json5-isms present ({', '.join(kinds)}); refusing so ingest never accepts what the shipped client rejects")
    return strict_loads(text)


def values_agree(a: ParseResult, b: ParseResult) -> bool:
    """Both accepted with equal values, or both not accepted."""
    if a.ok and b.ok:
        return a.value == b.value
    return (not a.ok) and (not b.ok)


def decisions_agree(a: ParseResult, b: ParseResult) -> bool:
    """Accept/reject verdicts agree (regardless of the diagnostics payload)."""
    return a.ok == b.ok


def _iter_files(root: Path):
    if root.is_file():
        yield root
    elif root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix in {".json", ".jsonc", ".json5"}:
                yield p


def run_corpus(corpus_root: Path, adversarial_root: Path | None = None) -> dict:
    """The accept/reject agreement matrix over real documents + adversarial ones."""
    rows: list[dict] = []
    disagree: list[str] = []
    adversarial_all_rejected = True
    count = 0
    for p in _iter_files(Path(corpus_root)):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lenient = lenient_loads(text)
        strict = strict_loads(text)
        agree = decisions_agree(lenient, strict)
        rows.append({"path": p.as_posix(), "lenient": lenient.status,
                     "strict": strict.status, "agree": agree})
        count += 1
        if not agree:
            disagree.append(p.as_posix())
    if adversarial_root is not None and Path(adversarial_root).is_dir():
        for p in sorted(Path(adversarial_root).glob("*")):
            if not p.is_file():
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            lenient = lenient_loads(text)
            strict = strict_loads(text)
            control = jsonc_loads(text)
            rejected_both = (not lenient.ok) and (not strict.ok)
            adversarial_all_rejected = adversarial_all_rejected and rejected_both
            # the control MUST tolerate what both production paths reject -
            # otherwise the fixture is not a real json5-ism
            rows.append({"path": p.as_posix(), "lenient": lenient.status,
                         "strict": strict.status, "jsonc_control": control.status,
                         "agree": decisions_agree(lenient, strict),
                         "adversarial_rejected_by_both": rejected_both,
                         "control_tolerates": control.ok})
            count += 1
    return {
        "documents": count,
        "agree_all": not disagree,
        "disagreeing": disagree,
        "adversarial_all_rejected_by_lenient_and_strict": adversarial_all_rejected,
        "rows": rows,
    }


__all__ = ["ParseResult", "jsonc_loads", "lenient_loads", "strict_loads",
           "decisions_agree", "values_agree", "run_corpus"]
