"""Three-way merge for user-edited deployed files (IMP-0031).

base   = shipped vN          ours = live user-edited copy      theirs = shipped vN+1

Strategies (chosen from the path suffix, falling back to line merge when a
structured parse fails):

* ``json``  – JSON / JSONC settings: structural key merge (reorder is not a
  conflict; leading ``//`` comment lines from *ours* are preserved).
* ``toml``  – TOML settings: structural key merge over ``tomllib`` tables.
* ``line``  – markdown / scripts / everything else: diff3 over lines with
  conflict markers; every line unique to ours survives in the text or in a
  conflict record.
* ``binary`` – any NUL byte in any side: refuse with a report, never guess.

``two_way_overwrite`` is the deliberately broken negative control: it takes
theirs and silently drops ours.
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import PurePosixPath
from typing import Any

JSON_SUFFIXES = {".json", ".jsonc", ".json5"}
TOML_SUFFIXES = {".toml"}
BINARY_SNIFF = 8192


@dataclass
class Conflict:
    region: str
    base: list[str] = field(default_factory=list)
    ours: list[str] = field(default_factory=list)
    theirs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"region": self.region, "base": self.base, "ours": self.ours, "theirs": self.theirs}


@dataclass
class MergeResult:
    status: str  # merged | conflict | refused
    strategy: str  # json | toml | line | binary | overwrite
    text: str | None = None
    data: bytes | None = None
    conflicts: list[Conflict] = field(default_factory=list)
    path: str | None = None
    report: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "merged"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "strategy": self.strategy,
            "path": self.path,
            "conflicts": [c.as_dict() for c in self.conflicts],
            "report": self.report,
            "text": self.text,
        }


# --------------------------------------------------------------------------- helpers
def is_binary(*blobs: bytes) -> bool:
    return any(b"\x00" in blob[:BINARY_SNIFF] for blob in blobs)


def strategy_for(path: str | None, *texts: str) -> str:
    suffix = PurePosixPath(path).suffix.lower() if path else ""
    if suffix in JSON_SUFFIXES:
        return "json"
    if suffix in TOML_SUFFIXES:
        return "toml"
    if not path and texts:
        stripped = [t.strip() for t in texts]
        if all(s.startswith(("{", "[")) for s in stripped):
            return "json"
    return "line"


def _split_lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


_COMMENT_RE = re.compile(r"^\s*//")


def _split_jsonc(text: str) -> tuple[list[str], str]:
    """Return (leading comment lines, json body) – JSONC tolerated on input."""
    lines = text.splitlines(keepends=True)
    comments: list[str] = []
    i = 0
    while i < len(lines) and (_COMMENT_RE.match(lines[i]) or not lines[i].strip()):
        if lines[i].strip():
            comments.append(lines[i])
        i += 1
    body_lines = [ln for ln in lines[i:] if not _COMMENT_RE.match(ln)]
    body = "".join(body_lines)
    body = re.sub(r",(\s*[}\]])", r"\1", body)  # trailing commas
    return comments, body


def _merge_values(base: Any, ours: Any, theirs: Any, key_path: str, conflicts: list[Conflict]) -> Any:
    if ours == theirs:
        return ours
    if ours == base:
        return theirs
    if theirs == base:
        return ours
    if isinstance(base, dict) and isinstance(ours, dict) and isinstance(theirs, dict):
        return _merge_dicts(base, ours, theirs, key_path, conflicts)
    conflicts.append(Conflict(region=key_path or "$",
                              base=[json.dumps(base, sort_keys=True)],
                              ours=[json.dumps(ours, sort_keys=True)],
                              theirs=[json.dumps(theirs, sort_keys=True)]))
    return ours


_MISSING = object()


def _merge_dicts(base: dict, ours: dict, theirs: dict, prefix: str, conflicts: list[Conflict]) -> dict:
    out: dict[str, Any] = {}
    order = list(ours.keys()) + [k for k in theirs.keys() if k not in ours] + [
        k for k in base.keys() if k not in ours and k not in theirs
    ]
    for key in order:
        kp = f"{prefix}.{key}" if prefix else key
        b, o, t = base.get(key, _MISSING), ours.get(key, _MISSING), theirs.get(key, _MISSING)
        if o is _MISSING and t is _MISSING:
            continue  # deleted on both sides
        if o is _MISSING:  # ours deleted
            if t == b:
                continue
            if b is _MISSING:
                out[key] = t  # theirs added
                continue
            conflicts.append(Conflict(region=kp, base=[json.dumps(b)], ours=[], theirs=[json.dumps(t)]))
            continue
        if t is _MISSING:  # theirs deleted
            if o == b:
                continue
            if b is _MISSING:
                out[key] = o  # ours added
                continue
            conflicts.append(Conflict(region=kp, base=[json.dumps(b)], ours=[json.dumps(o)], theirs=[]))
            out[key] = o
            continue
        if b is _MISSING:
            if o == t:
                out[key] = o
            elif isinstance(o, dict) and isinstance(t, dict):
                out[key] = _merge_dicts({}, o, t, kp, conflicts)
            else:
                conflicts.append(Conflict(region=kp, base=[], ours=[json.dumps(o)], theirs=[json.dumps(t)]))
                out[key] = o
            continue
        out[key] = _merge_values(b, o, t, kp, conflicts)
    return out


# --------------------------------------------------------------------------- json
def merge_json(base: str, ours: str, theirs: str, path: str | None = None) -> MergeResult:
    comments_o, body_o = _split_jsonc(ours)
    comments_t, body_t = _split_jsonc(theirs)
    _comments_b, body_b = _split_jsonc(base)
    try:
        b, o, t = json.loads(body_b or "null"), json.loads(body_o or "null"), json.loads(body_t or "null")
    except json.JSONDecodeError as exc:
        res = merge_lines(base, ours, theirs, path)
        res.report["json_fallback"] = f"{type(exc).__name__}: {exc}"
        return res
    conflicts: list[Conflict] = []
    if isinstance(b, dict) and isinstance(o, dict) and isinstance(t, dict):
        merged = _merge_dicts(b, o, t, "", conflicts)
    else:
        merged = _merge_values(b, o, t, "", conflicts)
    comments = comments_o or comments_t
    text = "".join(comments) + json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    status = "conflict" if conflicts else "merged"
    return MergeResult(status=status, strategy="json", text=text, conflicts=conflicts, path=path,
                       report={"keys": len(merged) if isinstance(merged, dict) else None,
                               "comments_preserved": len(comments)})


# --------------------------------------------------------------------------- toml
def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_scalar(v) for v in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value))


def dumps_toml(doc: dict[str, Any]) -> str:
    """Minimal deterministic TOML writer for scalar / list / nested-table documents."""
    lines: list[str] = []

    def emit(table: dict[str, Any], prefix: str) -> None:
        scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
        tables = {k: v for k, v in table.items() if isinstance(v, dict)}
        if prefix and (scalars or not tables):
            if lines:
                lines.append("")
            lines.append(f"[{prefix}]")
        for k, v in scalars.items():
            lines.append(f"{k} = {_toml_scalar(v)}")
        for k, v in tables.items():
            emit(v, f"{prefix}.{k}" if prefix else k)

    emit(doc, "")
    return "\n".join(lines).strip("\n") + "\n"


def merge_toml(base: str, ours: str, theirs: str, path: str | None = None) -> MergeResult:
    try:
        b, o, t = tomllib.loads(base), tomllib.loads(ours), tomllib.loads(theirs)
    except tomllib.TOMLDecodeError as exc:
        res = merge_lines(base, ours, theirs, path)
        res.report["toml_fallback"] = f"{type(exc).__name__}: {exc}"
        return res
    conflicts: list[Conflict] = []
    merged = _merge_dicts(b, o, t, "", conflicts)
    status = "conflict" if conflicts else "merged"
    return MergeResult(status=status, strategy="toml", text=dumps_toml(merged), conflicts=conflicts,
                       path=path, report={"keys": len(merged)})


# --------------------------------------------------------------------------- line diff3
def _sync_regions(base: list[str], a: list[str], b: list[str]) -> list[tuple[int, int, int, int, int, int]]:
    """Regions where base, a and b all match: (base_lo, base_hi, a_lo, a_hi, b_lo, b_hi)."""
    ma = [m for m in SequenceMatcher(None, base, a, autojunk=False).get_matching_blocks() if m.size]
    mb = [m for m in SequenceMatcher(None, base, b, autojunk=False).get_matching_blocks() if m.size]
    out: list[tuple[int, int, int, int, int, int]] = []
    ia = ib = 0
    while ia < len(ma) and ib < len(mb):
        ra, rb = ma[ia], mb[ib]
        lo = max(ra.a, rb.a)
        hi = min(ra.a + ra.size, rb.a + rb.size)
        if hi > lo:
            out.append((lo, hi, ra.b + (lo - ra.a), ra.b + (hi - ra.a), rb.b + (lo - rb.a), rb.b + (hi - rb.a)))
        if ra.a + ra.size < rb.a + rb.size:
            ia += 1
        else:
            ib += 1
    return out


def merge_lines(base: str, ours: str, theirs: str, path: str | None = None,
                labels: tuple[str, str] = ("ours", "theirs")) -> MergeResult:
    b, o, t = _split_lines(base), _split_lines(ours), _split_lines(theirs)
    regions = _sync_regions(b, o, t)
    out: list[str] = []
    conflicts: list[Conflict] = []
    ib = io_ = it = 0

    def resolve(b_lo: int, b_hi: int, o_lo: int, o_hi: int, t_lo: int, t_hi: int) -> None:
        bs, os_, ts = b[b_lo:b_hi], o[o_lo:o_hi], t[t_lo:t_hi]
        if os_ == ts:
            out.extend(os_)
        elif os_ == bs:
            out.extend(ts)
        elif ts == bs:
            out.extend(os_)
        else:
            conflicts.append(Conflict(region=f"lines {b_lo + 1}-{b_hi}", base=bs, ours=os_, theirs=ts))
            nl = "\n"
            out.append(f"<<<<<<< {labels[0]}{nl}")
            out.extend(_ensure_nl(os_))
            out.append(f"======={nl}")
            out.extend(_ensure_nl(ts))
            out.append(f">>>>>>> {labels[1]}{nl}")

    for b_lo, b_hi, o_lo, o_hi, t_lo, t_hi in regions:
        resolve(ib, b_lo, io_, o_lo, it, t_lo)
        out.extend(b[b_lo:b_hi])
        ib, io_, it = b_hi, o_hi, t_hi
    resolve(ib, len(b), io_, len(o), it, len(t))
    text = "".join(out)
    status = "conflict" if conflicts else "merged"
    return MergeResult(status=status, strategy="line", text=text, conflicts=conflicts, path=path,
                       report={"sync_regions": len(regions), "lines": len(out)})


def _ensure_nl(lines: list[str]) -> list[str]:
    return [ln if ln.endswith("\n") else ln + "\n" for ln in lines]


# --------------------------------------------------------------------------- entry points
def merge_texts(base: str, ours: str, theirs: str, path: str | None = None) -> MergeResult:
    strat = strategy_for(path, base, ours, theirs)
    if strat == "json":
        return merge_json(base, ours, theirs, path)
    if strat == "toml":
        return merge_toml(base, ours, theirs, path)
    return merge_lines(base, ours, theirs, path)


def merge_bytes(base: bytes, ours: bytes, theirs: bytes, path: str | None = None) -> MergeResult:
    if is_binary(base, ours, theirs):
        return MergeResult(
            status="refused", strategy="binary", path=path, data=None, text=None,
            report={"reason": "binary content; three-way merge refused",
                    "sizes": {"base": len(base), "ours": len(ours), "theirs": len(theirs)},
                    "ours_equals_base": ours == base, "theirs_equals_base": theirs == base},
        )
    try:
        b, o, t = base.decode("utf-8"), ours.decode("utf-8"), theirs.decode("utf-8")
    except UnicodeDecodeError as exc:
        return MergeResult(status="refused", strategy="binary", path=path,
                           report={"reason": f"undecodable: {exc}"})
    res = merge_texts(b, o, t, path)
    res.data = (res.text or "").encode("utf-8")
    return res


def two_way_overwrite(base: bytes | str, ours: bytes | str, theirs: bytes | str,
                      path: str | None = None) -> MergeResult:
    """NEGATIVE CONTROL: take theirs, drop ours, record nothing."""
    text = theirs.decode("utf-8", "replace") if isinstance(theirs, bytes) else theirs
    data = theirs if isinstance(theirs, bytes) else theirs.encode("utf-8")
    return MergeResult(status="merged", strategy="overwrite", text=text, data=data, path=path,
                       report={"dropped_ours": True})


def merge_with_provenance(record: dict[str, Any], ours: bytes, theirs: bytes,
                          path: str | None = None) -> MergeResult:
    """Merge using an IMP-0033 provenance record carrying base_bytes or base_path."""
    if "base_bytes" in record:
        base = record["base_bytes"]
        if isinstance(base, str):
            base = base.encode("utf-8")
    elif record.get("base_path"):
        with open(record["base_path"], "rb") as fh:
            base = fh.read()
    else:
        return MergeResult(status="refused", strategy="binary", path=path,
                           report={"reason": "provenance record lacks base_bytes/base_path"})
    return merge_bytes(base, ours, theirs, path or record.get("path"))


__all__ = [
    "Conflict",
    "MergeResult",
    "dumps_toml",
    "is_binary",
    "merge_bytes",
    "merge_json",
    "merge_lines",
    "merge_texts",
    "merge_toml",
    "merge_with_provenance",
    "strategy_for",
    "two_way_overwrite",
]
