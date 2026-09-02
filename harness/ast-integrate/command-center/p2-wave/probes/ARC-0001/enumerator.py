#!/usr/bin/env python3
"""Two independent enumerations of architecture candidates plus spec classes.

Heading regex and section-3 hazard-matrix column headers must agree before
any mapping is written. Live Windows harness-restore paths are tried first;
a reconstructed stand-in is used only when every live path is absent.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FIXTURE_CANDIDATES = HERE / "fixtures" / "13-ARCHITECTURE-CANDIDATES.md"
FIXTURE_SPEC = HERE / "fixtures" / "USER-PROMPTS-phase3-fragment.md"
UNIT = "ARC-0001"

HEADING_RE = re.compile(r"^(#{2,3})\s+(A\d+)\s*(?:\(([^)]*)\))?\s*$", re.MULTILINE)
REVIEWER_HEADING_RE = re.compile(r"(?im)^#{2,3}\s*A(\d{1,2})\s*\(([^)]*)\)\s*$")
SECTION3_RE = re.compile(r"(?im)^##\s*3\b.*$")
CANDIDATE_ID_RE = re.compile(r"^A\d+$")
CLASS_LIST_RE = re.compile(r"_USER-PROMPTS\.md:10771-10783 \(([^)]+)\)")
SEVEN_LENS_TITLE_RE = re.compile(r"^A(\d+)\s*\(([^)]+)\)")

LIVE_ROOTS = [
    Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path.home() / ".claude" / "harness-restore-20260806",
    REPO / "harness-restore-20260806",
    REPO / "command-center" / "sources",
]


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def first_existing(name: str) -> Path | None:
    for root in LIVE_ROOTS:
        cand = root / name
        if cand.is_file():
            return cand
    repo_hit = REPO / name
    if repo_hit.is_file():
        return repo_hit
    return None


def locate_candidates() -> tuple[Path, str]:
    live = first_existing("13-ARCHITECTURE-CANDIDATES.md")
    if live is not None:
        return live, "live"
    if not FIXTURE_CANDIDATES.is_file():
        raise FileNotFoundError("candidates document missing and stand-in absent")
    return FIXTURE_CANDIDATES, "reconstructed-stand-in"


def locate_spec() -> tuple[Path, str]:
    live = first_existing("_USER-PROMPTS.md") or first_existing("USER-PROMPTS.md")
    names = spec_classes_from_catalog_question(catalog_unit()["question_or_target"])
    if live is not None:
        text = live.read_text(encoding="utf-8", errors="replace")
        if all(name.lower() in text.lower() for name in names):
            return live, "live"
    if FIXTURE_SPEC.is_file():
        return FIXTURE_SPEC, "reconstructed-stand-in"
    if live is not None:
        return live, "live"
    raise FileNotFoundError("spec fragment missing and stand-in absent")


def line_of(text: str, idx: int) -> int:
    return text[:idx].count("\n") + 1


def enumerate_headings(text: str) -> list[dict]:
    rows = []
    for m in HEADING_RE.finditer(text):
        cid = m.group(2)
        title = (m.group(3) or "").strip()
        rows.append(
            {
                "id": cid,
                "heading": title or cid,
                "heading_line": line_of(text, m.start()),
                "raw": m.group(0).strip(),
            }
        )
    return rows


def enumerate_headings_reviewer(text: str) -> list[dict]:
    """Different anchor: requires the parenthetical title; uses A(\\d{1,2})."""
    rows = []
    for m in REVIEWER_HEADING_RE.finditer(text):
        cid = f"A{int(m.group(1))}"
        rows.append(
            {
                "id": cid,
                "heading": m.group(2).strip(),
                "heading_line": line_of(text, m.start()),
                "raw": m.group(0).strip(),
            }
        )
    return rows


def _first_table_after(text: str, start: int) -> str | None:
    chunk = text[start:]
    buf: list[str] = []
    in_table = False
    for line in chunk.splitlines():
        if line.startswith("|"):
            in_table = True
            buf.append(line)
            continue
        if in_table:
            break
    return "\n".join(buf) if buf else None


def enumerate_matrix(text: str) -> list[str]:
    m = SECTION3_RE.search(text)
    if not m:
        return []
    table = _first_table_after(text, m.start())
    if not table:
        return []
    header = table.splitlines()[0]
    cells = [c.strip() for c in header.split("|")]
    return [c for c in cells if CANDIDATE_ID_RE.fullmatch(c)]


def ids_of(rows: list[dict]) -> list[str]:
    return [r["id"] for r in rows]


def agree(headings: list[dict], matrix_ids: list[str]) -> bool:
    return ids_of(headings) == matrix_ids


def inject_synthetic_twelfth(text: str) -> str:
    heading = (
        "## A12 (synthetic-injected)\n\n"
        "Both-states control heading. Not a committed candidate.\n\n"
    )
    m = SECTION3_RE.search(text)
    if not m:
        raise ValueError("section 3 hazard matrix heading not found")
    text = text[: m.start()] + heading + text[m.start() :]
    m = SECTION3_RE.search(text)
    chunk = text[m.start() :]
    lines = chunk.splitlines(True)
    out: list[str] = []
    table_on = False
    sep_done = False
    for line in lines:
        if line.startswith("|") and not table_on:
            table_on = True
            stripped = line.rstrip("\n")
            line = (
                stripped + " A12 |\n"
                if stripped.endswith("|")
                else stripped + " | A12\n"
            )
        elif table_on and (not sep_done) and re.match(r"^\|[\s:|-]+\|", line):
            stripped = line.rstrip("\n")
            line = (
                stripped + " --- |\n"
                if stripped.endswith("|")
                else stripped + " | ---\n"
            )
            sep_done = True
        elif table_on and line.startswith("|"):
            stripped = line.rstrip("\n")
            line = (
                stripped + " ? |\n"
                if stripped.endswith("|")
                else stripped + " | ?\n"
            )
        elif table_on and not line.startswith("|"):
            table_on = False
        out.append(line)
    return text[: m.start()] + "".join(out)


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_unit(uid: str = UNIT) -> dict:
    data = load_catalog()
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def spec_classes_from_catalog_question(question: str) -> list[str]:
    m = CLASS_LIST_RE.search(question)
    if not m:
        raise ValueError("ARC-0001 question lacks the nine-class parenthetical")
    names = [p.strip() for p in m.group(1).split(",") if p.strip()]
    if len(names) != 9:
        raise ValueError(f"expected 9 spec classes, got {len(names)}: {names}")
    return names


def spec_classes_from_file(path: Path, kind: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    names_catalog = spec_classes_from_catalog_question(
        catalog_unit()["question_or_target"]
    )
    rows = []
    if kind == "live":
        lines = text.splitlines()
        window = lines[10770:10783] if len(lines) >= 10783 else lines
        blob = "\n".join(window)
        for name in names_catalog:
            loc = blob.lower().find(name.lower())
            if loc < 0:
                loc = text.lower().find(name.lower())
                if loc < 0:
                    raise ValueError(f"spec class {name!r} not in live prompts")
                line = line_of(text, loc)
            else:
                prefix = "\n".join(lines[:10770])
                prefix = (prefix + "\n") if prefix else ""
                line = line_of(prefix + blob, len(prefix) + loc)
            rows.append(
                {
                    "id": slug(name),
                    "name": name,
                    "spec_line": line,
                    "source_path": rel(path),
                }
            )
        return rows
    for name in names_catalog:
        loc = text.lower().find(name.lower())
        if loc < 0:
            raise ValueError(f"spec class {name!r} not in stand-in fragment")
        rows.append(
            {
                "id": slug(name),
                "name": name,
                "spec_line": line_of(text, loc),
                "source_path": rel(path),
            }
        )
    return rows


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def normalize(name: str) -> str:
    s = name.lower()
    s = s.replace("single-source-of-truth", "ssot")
    s = s.replace("single source of truth", "ssot")
    s = re.sub(r"[/_.,]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def seven_lens_titles() -> dict[str, str]:
    data = load_catalog()
    found: dict[str, str] = {}
    for u in data.get("work_units") or []:
        if not isinstance(u, dict):
            continue
        t = str(u.get("title") or "")
        m = SEVEN_LENS_TITLE_RE.match(t)
        if not m:
            continue
        cid = f"A{int(m.group(1))}"
        found.setdefault(cid, m.group(2).strip())
    return found


def catalog_question_line() -> int:
    text = CATALOG.read_text(encoding="utf-8")
    needle = '"id": "ARC-0001"'
    idx = text.find(needle)
    if idx < 0:
        return 0
    qidx = text.find("question_or_target", idx)
    if qidx < 0:
        return line_of(text, idx)
    return line_of(text, qidx)


def snapshot() -> dict:
    cpath, ckind = locate_candidates()
    spath, skind = locate_spec()
    ctext = cpath.read_text(encoding="utf-8")
    headings = enumerate_headings(ctext)
    matrix_ids = enumerate_matrix(ctext)
    reviewer = enumerate_headings_reviewer(ctext)
    classes = spec_classes_from_file(spath, skind)
    unit = catalog_unit()
    return {
        "candidates_path": rel(cpath),
        "candidates_kind": ckind,
        "spec_path": rel(spath),
        "spec_kind": skind,
        "candidates_text": ctext,
        "headings": headings,
        "matrix_ids": matrix_ids,
        "reviewer_headings": reviewer,
        "agreed": agree(headings, matrix_ids),
        "spec_classes": classes,
        "seven_lens": seven_lens_titles(),
        "catalog_question": unit["question_or_target"],
        "catalog_question_line": catalog_question_line(),
        "unit": unit,
    }


if __name__ == "__main__":
    s = snapshot()
    print(
        f"kind={s['candidates_kind']} path={s['candidates_path']} "
        f"headings={ids_of(s['headings'])} matrix={s['matrix_ids']} "
        f"agreed={s['agreed']} spec={len(s['spec_classes'])} "
        f"seven={sorted(s['seven_lens'])}"
    )
