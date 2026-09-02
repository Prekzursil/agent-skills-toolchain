#!/usr/bin/env python3
"""SYN-0016 omitted-dissent detector.

Two mechanically different extraction passes (structural JSON walk vs textual
scan). Matching is semantic token coverage with synonym canonicalisation, not
substring search. Quoted spans are stripped before matching (use-vs-mention).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

STOP = frozenset(
    """
    a an the and or but if then else when than that this these those it its
    is are was were be been being to of in on for from by with as at into
    over after before not no nor so such do does did doing done have has had
    can may must should would will shall also only own same other more most
    less least very just both each few many much any all some because while
    where which who whom whose what why how about against between through
    during without within upon per via rather doesn isn wasn than
    exist exists existed
    """.split()
)

SYN: dict[str, str] = {}


def _group(canon: str, *words: str) -> None:
    for w in words:
        SYN[w] = canon


_group("skip", "skip", "skips", "skipped", "omit", "omits", "omission", "drop", "drops", "dropped", "elide", "absent", "unlisted", "missing", "silent", "silently", "silence")
_group("refuse", "refuse", "refuses", "refused", "reject", "rejects", "rejected", "deny", "denies", "denied", "block", "blocks", "forbid", "forbids", "banned")
_group("hatch", "hatch", "escape", "passthrough", "pass")
_group("opaque", "opaque", "untyped", "blob", "body")
_group("typed", "typed", "type", "schema", "validation")
_group("clean", "clean", "launder", "launders", "laundered", "wash")
_group("drift", "drift", "tamper", "tampered")
_group("manifest", "manifest", "admission")
_group("minimise", "minimise", "minimize", "minimises", "minimizes", "minimised", "minimized")
_group("skill", "skill", "skills", "capability", "capabilities")
_group("generate", "generate", "generated", "generator", "ssot")
_group("overwrite", "overwrite", "overwrites", "overwritten", "rewritten", "rewrite", "rewrites")
_group("provenance", "provenance", "version")
_group("dissent", "dissent", "dissents", "dissenting", "minority", "objection", "objections", "refutation", "counterargument", "counter")
_group("survive", "survive", "survives", "survived", "survival", "preserve", "preserved")
_group("synthesis", "synthesis", "syntheses", "summary", "summaries")
_group("handedit", "hand", "edit")
_group("ondisk", "disk", "on-disk", "ondisk")
_group("configfirst", "config-first", "configfirst")
_group("current", "current", "today", "todays")
_group("copy", "copy", "copies", "copied", "copying")
_group("stop", "stop", "stops", "stopped", "prevent", "prevents", "prevented")
_group("drift", "reintroduce", "reintroduces", "reintroduced")

TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*")
QUOTE_RE = re.compile(r'"[^"\n]{8,}"|\'[^\'\n]{8,}\'')
NEGATED_CURRENCY = re.compile(
    r"not\s+today'?s\s+measurement|historical\s+rather\s+than\s+current|"
    r"is\s+not\s+(?:the\s+)?current",
    re.I,
)
ASSERTS_CURRENCY = re.compile(r"is the current measurement|current measurement of", re.I)
DISSENT_KEYS = frozenset(
    {
        "dissent",
        "dissents",
        "minority_report",
        "minority_reports",
        "minority-report",
        "minority-reports",
        "objection",
        "objections",
        "strongest_surviving_counterargument",
    }
)
TEXT_HIT = re.compile(
    r"(minority[\s-]+report|dissenting\s+(?:position|view|opinion)|"
    r"\bdissent\b|refuter\s+objection|surviving\s+counterargument)",
    re.I,
)
LIVE_GLOBS = [
    "command-center/phase3/**/*.json",
    "command-center/synthesis/**/*.json",
    "command-center/confirmation/**/*.json",
    "command-center/adversarial/**/*.json",
    "command-center/design/**/*.json",
]
PHASE14_CANDIDATES = [
    "command-center/synthesis/SYN-0008.candidate-syntheses.json",
    "command-center/synthesis/SYN-0009.raw-source-control.json",
    "command-center/synthesis/SYN-0011.adjudications.json",
]
SKIP_PATH_PARTS = (
    "/probes/SYN-0016/",
    "/receipts/SYN-0016.json",
    "/schema/dissent-audit.schema.json",
)
SYNTHESIS_ABSENT_REASON = (
    "phase14-synthesis-absent: command-center/synthesis/"
    "SYN-0008.candidate-syntheses.json is not on disk; the dissent cannot be "
    "shown to have survived into a Phase-14 candidate synthesis"
)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def strip_quoted(text: str) -> str:
    return QUOTE_RE.sub(" ", text or "")


def _stem(word: str) -> str:
    w = word
    for suf in ("ing", "ted", "ied", "ies", "es", "ed", "s"):
        if len(w) > 5 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    return w


def tokens(text: str, *, strip_quotes: bool = True) -> set[str]:
    body = strip_quoted(text) if strip_quotes else (text or "")
    out: set[str] = set()
    for raw in TOKEN_RE.findall(body.lower()):
        parts = re.split(r"[-_]", raw)
        for part in parts:
            if not part or part in STOP or part.isdigit():
                continue
            if part in SYN:
                out.add(SYN[part])
                continue
            stemmed = _stem(part)
            if stemmed in SYN:
                out.add(SYN[stemmed])
            elif stemmed not in STOP and len(stemmed) > 2:
                out.add(stemmed)
    return out


def coverage(dissent_text: str, synthesis_text: str) -> tuple[float, int, set[str]]:
    dt = tokens(dissent_text, strip_quotes=False)
    st = tokens(synthesis_text, strip_quotes=True)
    if not dt:
        return 0.0, 0, set()
    overlap = dt & st
    return len(overlap) / len(dt), len(overlap), overlap


def contradicted(dissent_text: str, synthesis_text: str) -> bool:
    """A later remeasurement that denies currency is not survival of the dissent."""
    if not ASSERTS_CURRENCY.search(dissent_text or ""):
        return False
    return bool(NEGATED_CURRENCY.search(strip_quoted(synthesis_text or "")))


def semantic_match(dissent_text: str, synthesis_text: str) -> bool:
    if contradicted(dissent_text, synthesis_text):
        return False
    cov, n, _ = coverage(dissent_text, synthesis_text)
    return cov >= 0.55 and n >= 3


def substring_match(dissent_text: str, synthesis_text: str) -> bool:
    needle = (dissent_text or "").strip().lower()
    hay = (synthesis_text or "").lower()
    return bool(needle) and needle in hay


def line_anchor(path: Path, snippet: str) -> str:
    text = path.read_text(encoding="utf-8")
    probe = (snippet or "").strip()
    if probe.startswith("REFUTED:"):
        probe = probe[len("REFUTED:") :].strip()
    for n in (96, 48, 32):
        chunk = probe[:n]
        if len(chunk) < 16:
            break
        idx = text.find(chunk)
        if idx >= 0:
            return f"{rel(path)}:{text[:idx].count(chr(10)) + 1}"
    return f"{rel(path)}:1"


def _skip_rel(posix: str) -> bool:
    return any(part in f"/{posix}" or posix.endswith(part.strip("/")) for part in SKIP_PATH_PARTS)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _emit(
    bag: list[dict],
    *,
    ident: str,
    text: str,
    kind: str,
    source: Path,
    snippet: str,
    found_by: str,
    extra: dict | None = None,
) -> None:
    body = " ".join((text or "").split())
    if len(body) < 16:
        return
    row = {
        "id": ident,
        "text": body[:800],
        "kind": kind,
        "source_anchor": line_anchor(source, snippet or body),
        "corpus": "live",
        "found_by": [found_by],
    }
    if extra:
        row.update(extra)
    bag.append(row)


def pass_a_walk(obj: Any, source: Path, bag: list[dict], trail: str = "$") -> None:
    if isinstance(obj, dict):
        verdict = obj.get("verdict")
        if verdict == "REFUTED":
            loc = (
                obj.get("scoped_restatement")
                or obj.get("why_locus")
                or obj.get("claim")
                or ""
            )
            text = (
                str(obj.get("scoped_restatement") or obj.get("why_locus") or "")
                or (("REFUTED: " + str(obj.get("claim"))) if obj.get("claim") else "")
            )
            cid = str(obj.get("id") or trail)
            _emit(
                bag,
                ident=f"live:{rel(source)}:{cid}",
                text=str(text),
                kind="refuter-objection",
                source=source,
                snippet=str(loc)[:120],
                found_by="pass-a",
                extra={"claim_targeted": str(obj.get("claim") or "")[:400]},
            )
        for key, val in obj.items():
            if key in DISSENT_KEYS and isinstance(val, str):
                kind = (
                    "surviving-counterargument"
                    if key == "strongest_surviving_counterargument"
                    else "dissent-field"
                )
                if key.startswith("minority"):
                    kind = "minority-report"
                _emit(
                    bag,
                    ident=f"live:{rel(source)}:{key}",
                    text=val,
                    kind=kind,
                    source=source,
                    snippet=val[:96],
                    found_by="pass-a",
                )
            pass_a_walk(val, source, bag, f"{trail}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            pass_a_walk(item, source, bag, f"{trail}[{i}]")


def pass_b_scan(path: Path, bag: list[dict]) -> None:
    text = path.read_text(encoding="utf-8")
    for match in TEXT_HIT.finditer(text):
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 120)
        window = " ".join(text[start:end].split())
        if len(window) < 80:
            continue
        if "unanimous-or-record-dissent" in window:
            continue
        if re.search(r'"id"\s*:\s*"FC-11\d{3}"', window):
            continue
        if "cite the file:line that makes the loss silent" in window:
            continue
        if re.search(r'"name"\s*:\s*"minority report', window):
            continue
        _emit(
            bag,
            ident=f"live:{rel(path)}:text-{match.start()}",
            text=window,
            kind="dissent-field",
            source=path,
            snippet=match.group(0),
            found_by="pass-b",
        )


def _near_duplicate(a: str, b: str) -> bool:
    ta, tb = tokens(a, strip_quotes=False), tokens(b, strip_quotes=False)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    return inter / min(len(ta), len(tb)) >= 0.85


def merge_population(rows: Iterable[dict]) -> list[dict]:
    merged: list[dict] = []
    for row in rows:
        found = False
        for prev in merged:
            if prev["source_anchor"].rsplit(":", 1)[0] == row["source_anchor"].rsplit(":", 1)[0] and _near_duplicate(
                prev["text"], row["text"]
            ):
                fb = list(dict.fromkeys(prev.get("found_by", []) + row.get("found_by", [])))
                prev["found_by"] = fb
                found = True
                break
        if not found:
            merged.append(dict(row))
    return merged


def live_sources() -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for pattern in LIVE_GLOBS:
        for path in sorted(REPO.glob(pattern)):
            if not path.is_file():
                continue
            posix = rel(path)
            if _skip_rel(posix) or posix in seen:
                continue
            seen.add(posix)
            out.append(path)
    return out


def extract_live() -> tuple[list[dict], dict]:
    a_rows: list[dict] = []
    b_rows: list[dict] = []
    for path in live_sources():
        doc = load_json(path)
        if isinstance(doc, (dict, list)):
            pass_a_walk(doc, path, a_rows)
        pass_b_scan(path, b_rows)
    merged = merge_population(a_rows + b_rows)
    a_ids = {r["id"] for r in a_rows}
    b_ids = {r["id"] for r in b_rows}
    only_a = sorted(i for i in a_ids if i not in b_ids)
    only_b = sorted(i for i in b_ids if i not in a_ids)
    meta = {
        "pass_a_count": len(a_rows),
        "pass_b_count": len(b_rows),
        "delta": {"only_pass_a": only_a, "only_pass_b": only_b},
        "finding": (
            "Both extraction passes kept. Pass A (structural REFUTED/"
            "dissent keys) and pass B (textual minority/dissent scan) differ; "
            f"delta only_a={len(only_a)} only_b={len(only_b)}."
        ),
    }
    return merged, meta


def load_control() -> tuple[list[dict], str, str, dict[str, str]]:
    spec = json.loads((FIX / "control_corpus.json").read_text(encoding="utf-8"))
    paragraphs = spec["paragraphs"]
    full = "\n\n".join(p["text"] for p in paragraphs)
    omitted = "\n\n".join(p["text"] for p in paragraphs if p.get("id") != "hatch")
    dissents = []
    for row in spec["dissents"]:
        item = dict(row)
        item["corpus"] = "control"
        item["source_anchor"] = (
            "command-center/p2-wave/probes/SYN-0016/fixtures/control_corpus.json:"
            + item["id"]
        )
        dissents.append(item)
    return dissents, full, omitted, spec.get("disposal") or {}


def phase14_status() -> dict:
    present = []
    for p in PHASE14_CANDIDATES:
        path = REPO / p
        present.append(
            {
                "path": p,
                "exists": path.is_file() and path.stat().st_size > 0,
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return {"paths": list(PHASE14_CANDIDATES), "present": present}


def read_phase14_text() -> str:
    chunks: list[str] = []
    for p in PHASE14_CANDIDATES:
        path = REPO / p
        if path.is_file() and path.stat().st_size > 0:
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def join(
    dissents: list[dict],
    synthesis_text: str,
    *,
    default_disposal: str | None,
    disposal_map: dict[str, dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    matched: list[dict] = []
    unmatched: list[dict] = []
    disposal_map = disposal_map or {}
    for row in dissents:
        hit = bool(synthesis_text) and semantic_match(row["text"], synthesis_text)
        if hit:
            matched.append(
                {
                    "id": row["id"],
                    "text": row["text"],
                    "kind": row["kind"],
                    "source_anchor": row["source_anchor"],
                    "corpus": row["corpus"],
                    "coverage": round(coverage(row["text"], synthesis_text)[0], 4),
                }
            )
            continue
        rec = {
            "id": row["id"],
            "text": row["text"],
            "kind": row["kind"],
            "source_anchor": row["source_anchor"],
            "corpus": row["corpus"],
        }
        mapped = disposal_map.get(row["id"])
        if mapped:
            rec["disposal_reason"] = mapped["disposal_reason"]
            if mapped.get("superseding_evidence"):
                rec["superseding_evidence"] = mapped["superseding_evidence"]
        elif default_disposal:
            rec["disposal_reason"] = default_disposal
        unmatched.append(rec)
    return matched, unmatched


def assert_disposed(unmatched: list[dict]) -> None:
    for row in unmatched:
        reason = str(row.get("disposal_reason") or "").strip()
        if len(reason) < 16:
            raise AssertionError(f"unmatched {row.get('id')} missing disposal_reason")
        if re.search(r"superseded", reason, re.I) and not str(
            row.get("superseding_evidence") or ""
        ).strip():
            raise AssertionError(
                f"unmatched {row.get('id')} superseded without superseding_evidence"
            )
