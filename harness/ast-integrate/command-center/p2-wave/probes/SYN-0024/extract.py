"""Extract polarity-records from JSON trees. Identity is id, never title."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from paths import (
    CATALOG_REL,
    FIXTURE_B03,
    FIXTURE_B08,
    FIXTURE_SYN,
    REPO,
    SYNTHESIS_REL,
)

ID_KEYS = ("id", "claim_id", "record_id", "test_id", "mutant_id")
POLARITY_KEYS = ("verdict", "polarity", "test_result", "mutant_status")
SKIP_WALK_KEYS = frozenset(
    {
        "padding",
        "blob",
        "raw_output",
        "answer",
        "question",
        "question_or_target",
        "completion_sentinel",
        "evidence_requirement",
    }
)

NEGATIVE = frozenset(
    {
        "REFUTED",
        "CONTRADICTS",
        "CONTRADICTION",
        "NEGATIVE",
        "NEGATIVE-RESULT",
        "NULL",
        "NULL-RESULT",
        "FAILED",
        "FAIL",
        "RED",
        "REGRESSED",
        "SURVIVOR",
        "MUTATION-SURVIVOR",
    }
)
POSITIVE = frozenset(
    {
        "CONFIRMED",
        "SUPPORTS",
        "POSITIVE",
        "PASSED",
        "PASS",
        "GREEN",
        "IMPROVED",
        "SUCCESS",
    }
)


@dataclass(frozen=True)
class Record:
    id: str
    polarity: str
    raw: str
    path: str
    nbytes: int
    claim: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "polarity": self.polarity,
            "raw": self.raw,
            "path": self.path,
            "nbytes": self.nbytes,
            "claim": self.claim,
        }


def _norm(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "-")


def _identity(obj: dict[str, Any]) -> str | None:
    for key in ID_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _polarity_raw(obj: dict[str, Any]) -> str | None:
    for key in POLARITY_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def classify(raw: str) -> str:
    token = _norm(raw)
    if token in NEGATIVE:
        return "negative"
    if token in POSITIVE:
        return "positive"
    return "other"


def _expand_padding(obj: dict[str, Any]) -> dict[str, Any]:
    if "padding_repeat" not in obj:
        return obj
    try:
        n = int(obj["padding_repeat"])
    except (TypeError, ValueError):
        return obj
    n = max(0, min(n, 20000))
    out = dict(obj)
    out["padding"] = "A" * n
    return out


def _record_from(obj: dict[str, Any], path: str) -> Record | None:
    expanded = _expand_padding(obj)
    ident = _identity(expanded)
    raw = _polarity_raw(expanded)
    if not ident or not raw:
        return None
    polar = classify(raw)
    if polar == "other":
        return None
    claim = str(expanded.get("claim") or expanded.get("title") or ident)
    blob = json.dumps(expanded, sort_keys=True, ensure_ascii=True)
    return Record(
        id=ident,
        polarity=polar,
        raw=_norm(raw),
        path=path,
        nbytes=len(blob.encode("utf-8")),
        claim=claim[:240],
    )


def walk(node: Any, path: str, out: list[Record], seen: set[str]) -> None:
    if isinstance(node, dict):
        rec = _record_from(node, path)
        if rec is not None and rec.id not in seen:
            seen.add(rec.id)
            out.append(rec)
        for key, val in node.items():
            if key in SKIP_WALK_KEYS or key in POLARITY_KEYS:
                continue
            walk(val, path, out, seen)
        return
    if isinstance(node, list):
        for item in node:
            walk(item, path, out, seen)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_file(path: Path, rel: str | None = None) -> list[Record]:
    if not path.is_file() or path.stat().st_size <= 0:
        return []
    try:
        doc = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    rel_s = rel or path.as_posix()
    out: list[Record] = []
    walk(doc, rel_s, out, set())
    return out


def extract_files(paths: Iterable[Path], repo: Path = REPO) -> list[Record]:
    records: list[Record] = []
    seen: set[str] = set()
    for path in paths:
        rel = path.as_posix()
        try:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            pass
        for rec in extract_file(path, rel):
            if rec.id in seen:
                continue
            seen.add(rec.id)
            records.append(rec)
    return records


def fixture_source() -> list[Record]:
    return extract_files([FIXTURE_B03, FIXTURE_B08])


def fixture_synthesis() -> list[Record]:
    return extract_files([FIXTURE_SYN])


def _catalog_units() -> list[dict[str, Any]]:
    path = REPO / CATALOG_REL
    if not path.is_file():
        return []
    try:
        data = load_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        units = data.get("work_units") or []
        if isinstance(units, list):
            return [u for u in units if isinstance(u, dict)]
    if isinstance(data, list):
        return [u for u in data if isinstance(u, dict)]
    return []


def live_source_paths() -> dict[str, Any]:
    b03: list[str] = []
    b08: list[str] = []
    present_b03: list[str] = []
    present_b08: list[str] = []
    for unit in _catalog_units():
        uid = str(unit.get("id") or "")
        phase = str(unit.get("phase") or "")
        out = str(unit.get("output_path") or "").replace("\\", "/")
        if not out:
            continue
        if uid.startswith("RES-") and phase == "2":
            b03.append(out)
            if (REPO / out).is_file():
                present_b03.append(out)
        elif uid.startswith("TST-") and phase == "10":
            b08.append(out)
            if (REPO / out).is_file():
                present_b08.append(out)
    extra_dirs = (
        REPO / "command-center" / "research",
        REPO / "command-center" / "phase10",
    )
    extra: list[str] = []
    for root in extra_dirs:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                rel = path.resolve().relative_to(REPO.resolve()).as_posix()
            except ValueError:
                continue
            extra.append(rel)
            if rel.startswith("command-center/research/") and rel not in present_b03:
                if path.is_file():
                    present_b03.append(rel)
            if rel.startswith("command-center/phase10/") and rel not in present_b08:
                if path.is_file():
                    present_b08.append(rel)
    return {
        "b03_declared": len(b03),
        "b08_declared": len(b08),
        "b03_present": present_b03,
        "b08_present": present_b08,
        "extra_scanned": extra,
    }


def live_source() -> tuple[list[Record], dict[str, Any]]:
    inv = live_source_paths()
    files = [REPO / p for p in inv["b03_present"] + inv["b08_present"]]
    return extract_files(files), inv


def live_synthesis() -> tuple[list[Record], dict[str, Any]]:
    candidates = [REPO / SYNTHESIS_REL]
    synth_dir = REPO / "command-center" / "synthesis"
    present: list[str] = []
    if synth_dir.is_dir():
        candidates.extend(sorted(synth_dir.rglob("*.json")))
    uniq: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        if not path.is_file():
            continue
        try:
            rel = path.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            continue
        if rel in seen:
            continue
        seen.add(rel)
        present.append(rel)
        uniq.append(path)
    return extract_files(uniq), {
        "declared": SYNTHESIS_REL,
        "declared_present": (REPO / SYNTHESIS_REL).is_file(),
        "present": present,
    }
