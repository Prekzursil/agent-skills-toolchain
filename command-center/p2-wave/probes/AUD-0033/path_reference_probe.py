#!/usr/bin/env python3
"""AUD-0033 Probe 1: extract path-like tokens from scoped docs and test existence.

Control: finds a fenced path; does NOT emit slash-bearing prose traps.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent
FIXTURE = OUT_DIR / "detector-control.md"
PROSE_TRAPS = {"input/output", "this/that"}
PLANTED_TYPO = "command-center/does-not-exist-AUD0033-typo.json"

# Repo-relative path shapes: a/b, a/b/c.ext, .agents/skills, Windows-ish C:/...
FENCED_RE = re.compile(
    r"(?:```[^\n]*\n)(.*?)(?:```)",
    re.DOTALL,
)
BACKTICK_RE = re.compile(r"`([^`\n]{3,200})`")
PATHISH_RE = re.compile(
    r"(?P<p>"
    r"(?:[A-Za-z]:[\\/])?"
    r"(?:\.\.?/)?"
    r"(?:\.?[A-Za-z0-9_-]+)"
    r"(?:/(?:\.?[A-Za-z0-9_-]+|(?:\.\.?)))+"
    r"(?:\.[A-Za-z0-9_-]+)?"
    r")"
)
LINE_REF_STRIP = re.compile(r":\d+(?:-\d+)?$")

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    "coverage",
    "htmlcov",
}


def is_pathish(token: str, *, allow_bare_file: bool = False) -> bool:
    t = token.strip().strip("'\"")
    if not t or " " in t or "\t" in t:
        return False
    if t.lower() in PROSE_TRAPS:
        return False
    # Reject URLs and pure protocols
    if "://" in t or t.startswith("http"):
        return False
    # Reject git refs / email-ish
    if "@" in t and "/" not in t.split("@", 1)[0]:
        return False
    # Reject pure version-like tokens
    if re.fullmatch(r"\d+(?:\.\d+)+", t):
        return False
    # Reject regex / CLI flag / env-template noise
    if any(ch in t for ch in ("(", ")", "?", "*", "+", "[", "]", "^", "$", "|", "%")):
        return False
    if t.startswith("--"):
        return False
    # Source-relative bare filenames (fixture control only)
    if "/" not in t and "\\" not in t:
        if not allow_bare_file:
            return False
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*\.[A-Za-z][A-Za-z0-9_-]*", t))
    # Must look like a filesystem path: at least one slash and a wordy component
    if not PATHISH_RE.fullmatch(t) and not PATHISH_RE.fullmatch(t.replace("\\", "/")):
        # Allow Windows backslash forms by normalizing check
        if "\\" in t:
            return bool(re.search(r"[A-Za-z0-9_.-]+\\[A-Za-z0-9_.\\-]+", t))
        return False
    return True


def normalize_token(token: str) -> str:
    t = token.strip().strip("'\"")
    t = LINE_REF_STRIP.sub("", t)
    return t


def extract_from_text(text: str, *, allow_bare_file: bool = False) -> list[str]:
    found: list[str] = []
    # Prefer fenced blocks first
    for m in FENCED_RE.finditer(text):
        block = m.group(1)
        for line in block.splitlines():
            line = line.strip()
            if is_pathish(line, allow_bare_file=allow_bare_file):
                found.append(normalize_token(line))
            else:
                for pm in PATHISH_RE.finditer(line):
                    cand = normalize_token(pm.group("p"))
                    if is_pathish(cand, allow_bare_file=allow_bare_file):
                        found.append(cand)
    # Backticks
    for m in BACKTICK_RE.finditer(text):
        cand = normalize_token(m.group(1))
        if is_pathish(cand, allow_bare_file=allow_bare_file):
            found.append(cand)
    return found


def scoped_files() -> list[Path]:
    roots = [
        REPO / "command-center",
        REPO / "docs",
        REPO / "rules",
        REPO / ".agents" / "skills",
        REPO / "skills",
        REPO / "AGENTS.md",
        REPO / "README.md",
        REPO / "CLAUDE.md",
        FIXTURE,
    ]
    files: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root.is_file() and root.suffix.lower() in {".md", ".json", ".txt"}:
            if root not in seen:
                files.append(root)
                seen.add(root)
            continue
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            if p.suffix.lower() not in {".md", ".json"}:
                continue
            # Skip giant generated catalogs / receipts that cite themselves
            if p.name.endswith("-doc-path-reference-integrity.json"):
                continue
            if p.stat().st_size > 400_000:
                continue
            if p not in seen:
                files.append(p)
                seen.add(p)
    return files


def resolve_exists(token: str, source: Path) -> bool:
    # Absolute Windows path on Linux will fail closed as MISSING
    if re.match(r"^[A-Za-z]:[\\/]", token) or token.startswith("\\\\"):
        return Path(token).exists()
    candidates = [
        REPO / token,
        source.parent / token,
        Path(token),
    ]
    # Strip leading ./
    if token.startswith("./"):
        candidates.append(REPO / token[2:])
    for c in candidates:
        try:
            if c.exists():
                return True
        except OSError:
            continue
    return False


def run_control() -> dict:
    text = FIXTURE.read_text(encoding="utf-8")
    tokens = extract_from_text(text, allow_bare_file=True)
    uniq = []
    for t in tokens:
        if t not in uniq:
            uniq.append(t)
    found_fenced = "command-center/WORK-UNIT-CATALOG.json" in uniq
    emitted_traps = [t for t in uniq if t in PROSE_TRAPS]
    return {
        "fixture": str(FIXTURE.relative_to(REPO)),
        "tokens": uniq,
        "found_fenced_path": found_fenced,
        "emitted_prose_traps": emitted_traps,
        "control_ok": found_fenced and not emitted_traps,
    }


def main() -> int:
    control = run_control()
    rows = []
    files = scoped_files()
    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            rows.append({"file": str(fp), "error": str(e)})
            continue
        allow_bare = fp.resolve() == FIXTURE.resolve()
        for tok in extract_from_text(text, allow_bare_file=allow_bare):
            rows.append(
                {
                    "file": str(fp.relative_to(REPO)),
                    "token": tok,
                    "exists": resolve_exists(tok, fp),
                }
            )

    # Ensure fixture tokens are represented even if somehow missed in sweep
    for tok in control["tokens"]:
        rows.append(
            {
                "file": str(FIXTURE.relative_to(REPO)),
                "token": tok,
                "exists": resolve_exists(tok, FIXTURE),
            }
        )

    distinct: dict[str, bool] = {}
    for r in rows:
        tok = r.get("token")
        if not tok:
            continue
        # EXISTS wins if any citation resolves
        prev = distinct.get(tok)
        if prev is True:
            continue
        distinct[tok] = bool(r.get("exists"))

    exists_n = sum(1 for v in distinct.values() if v)
    missing_n = sum(1 for v in distinct.values() if not v)
    missing_sample = [k for k, v in distinct.items() if not v][:40]

    known = {
        "docs/agentic-perfection/CHANGELOG.md": (
            REPO / "docs/agentic-perfection/CHANGELOG.md"
        ).exists(),
        "scripts/claude-science/cs-doctor.ps1": (
            REPO / "scripts/claude-science/cs-doctor.ps1"
        ).exists(),
        ".agents/skills": (REPO / ".agents/skills").exists(),
        "local-rel-target.txt": resolve_exists("local-rel-target.txt", FIXTURE),
        "command-center/WORK-UNIT-CATALOG.json": (
            REPO / "command-center/WORK-UNIT-CATALOG.json"
        ).exists(),
    }
    known_counterexamples = {
        k: {
            "on_disk": bool(v),
            "extracted": k in distinct
            or (k == "local-rel-target.txt" and "local-rel-target.txt" in distinct),
            "status": "EXISTS" if distinct.get(k, v) else "MISSING",
        }
        for k, v in known.items()
    }
    # local-rel must be EXISTS via source-relative
    counterexamples_ok = (
        known_counterexamples["local-rel-target.txt"]["status"] == "EXISTS"
        and known_counterexamples[".agents/skills"]["status"] == "EXISTS"
        and known_counterexamples["command-center/WORK-UNIT-CATALOG.json"]["status"]
        == "EXISTS"
        and PLANTED_TYPO in distinct
        and distinct.get(PLANTED_TYPO) is False
    )

    result = {
        "unit": "AUD-0033",
        "stage": "linux-local-remeasure",
        "extractor": "good-extractor",
        "control": control,
        "files_scanned": len(files),
        "citation_rows": len([r for r in rows if "token" in r]),
        "distinct_tokens": len(distinct),
        "exists": exists_n,
        "missing": missing_n,
        "known_counterexamples": known_counterexamples,
        "counterexamples_ok": counterexamples_ok,
        "missing_sample": missing_sample,
        "planted_typo_missing": distinct.get(PLANTED_TYPO) is False,
        "ok": control["control_ok"] and counterexamples_ok,
        "identities": {
            k: ("EXISTS" if v else "MISSING") for k, v in sorted(distinct.items())
        },
    }

    (OUT_DIR / "probe1-results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "AUD-0033 NAMED PROBE 1: extract path tokens and test existence",
        "unit=AUD-0033",
        "stage=linux-local-remeasure",
        "extractor=good-extractor",
        f"fixture={FIXTURE}",
        "fenced_must=command-center/WORK-UNIT-CATALOG.json",
        f"found_fenced_path={control['found_fenced_path']}",
        f"emitted_prose_traps={control['emitted_prose_traps']!r}",
        f"control_ok={control['control_ok']}",
        f"tokens={control['tokens']!r}",
        f"files_scanned={len(files)}",
        f"citation_rows={result['citation_rows']}",
        f"distinct_tokens={len(distinct)}",
        f"exists={exists_n}",
        f"missing={missing_n}",
        f"known_counterexamples={json.dumps(known_counterexamples)}",
        f"counterexamples_ok={counterexamples_ok}",
        f"missing_sample={missing_sample!r}",
        "SUCCESS:AUD-0033-probe1" if result["ok"] else "FAILED:AUD-0033-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "probe1-existence.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
