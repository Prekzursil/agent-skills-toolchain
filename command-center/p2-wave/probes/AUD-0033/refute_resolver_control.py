#!/usr/bin/env python3
"""AUD-0033 both-states control: good extractor vs any-slash mutant; naive vs fixed resolver."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent
FIXTURE = OUT_DIR / "detector-control.md"
PROSE_TRAPS = {"input/output", "this/that"}

FENCED_RE = re.compile(r"(?:```[^\n]*\n)(.*?)(?:```)", re.DOTALL)
BACKTICK_RE = re.compile(r"`([^`\n]{3,200})`")
PATHISH_RE = re.compile(
    r"(?P<p>(?:[A-Za-z]:[\\/])?(?:\.\.?/)?(?:\.?[A-Za-z0-9_-]+)(?:/(?:\.?[A-Za-z0-9_-]+))+(?:\.[A-Za-z0-9_-]+)?)"
)
ANY_SLASH_RE = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")


def good_extract(text: str) -> list[str]:
    found = []
    bare_file = re.compile(r"^[A-Za-z0-9_.-]+\.[A-Za-z0-9_-]+$")
    for m in FENCED_RE.finditer(text):
        for line in m.group(1).splitlines():
            line = line.strip()
            if (PATHISH_RE.fullmatch(line) or bare_file.fullmatch(line)) and line not in PROSE_TRAPS:
                found.append(line)
    for m in BACKTICK_RE.finditer(text):
        cand = m.group(1).strip()
        if (PATHISH_RE.fullmatch(cand) or bare_file.fullmatch(cand)) and cand not in PROSE_TRAPS:
            found.append(cand)
    # uniq
    out = []
    for t in found:
        if t not in out:
            out.append(t)
    return out


def mutant_extract(text: str) -> list[str]:
    """Any-slash mutant: emits prose traps."""
    out = []
    for m in ANY_SLASH_RE.finditer(text):
        t = m.group(1)
        if t not in out:
            out.append(t)
    return out


def naive_exists(token: str) -> bool:
    return (REPO / token).is_file()


def fixed_exists(token: str, source: Path) -> bool:
    for c in (REPO / token, source.parent / token, Path(token)):
        try:
            if c.exists():
                return True
        except OSError:
            continue
    return False


def main() -> int:
    text = FIXTURE.read_text(encoding="utf-8")
    good = good_extract(text)
    mutant = mutant_extract(text)
    found_fence_good = "command-center/WORK-UNIT-CATALOG.json" in good
    found_fence_mutant = "command-center/WORK-UNIT-CATALOG.json" in mutant
    good_prose = [t for t in good if t in PROSE_TRAPS]
    mutant_prose = [t for t in mutant if t in PROSE_TRAPS]

    naive_rel = "EXISTS" if naive_exists("local-rel-target.txt") else "MISSING"
    fixed_rel = "EXISTS" if fixed_exists("local-rel-target.txt", FIXTURE) else "MISSING"
    naive_skills = "EXISTS" if naive_exists(".agents/skills") else "MISSING"
    # naive is_file misses directories
    if (REPO / ".agents/skills").is_dir() and not (REPO / ".agents/skills").is_file():
        naive_skills = "MISSING"
    fixed_skills = "EXISTS" if fixed_exists(".agents/skills", FIXTURE) else "MISSING"

    changelog = REPO / "docs/agentic-perfection/CHANGELOG.md"
    cs = REPO / "scripts/claude-science/cs-doctor.ps1"
    naive_changelog = "EXISTS" if changelog.is_file() else "MISSING"
    fixed_changelog = naive_changelog
    naive_cs = "EXISTS" if cs.is_file() else "MISSING"
    fixed_cs = naive_cs

    detector_good = found_fence_good and not good_prose
    detector_mutant_red = found_fence_mutant and bool(mutant_prose)
    resolver_fixed = fixed_rel == "EXISTS" and fixed_skills == "EXISTS"
    resolver_naive_bad = naive_rel == "MISSING"  # expected: naive misses source-relative

    fired_on_bad = detector_mutant_red and resolver_naive_bad
    silent_on_good = detector_good and resolver_fixed
    discriminates = fired_on_bad and silent_on_good

    lines = [
        "AUD-0033 REFUTE/RESOLVER CONTROL",
        f"good_tokens={good!r}",
        f"mutant_tokens={mutant!r}",
        f"found_fence_good={found_fence_good}",
        f"found_fence_mutant={found_fence_mutant}",
        f"good_prose={good_prose!r}",
        f"mutant_prose={mutant_prose!r}",
        f"naive_rel={naive_rel} fixed_rel={fixed_rel}",
        f"naive_skills={naive_skills} fixed_skills={fixed_skills}",
        f"naive_changelog={naive_changelog} fixed_changelog={fixed_changelog}",
        f"naive_cs_doctor={naive_cs} fixed_cs_doctor={fixed_cs}",
        f"fired_on_bad={fired_on_bad}",
        f"silent_on_good={silent_on_good}",
        f"detector_good={detector_good}",
        f"detector_mutant_red={detector_mutant_red}",
        f"discriminates={discriminates}",
        "SUCCESS:AUD-0033-refute-resolver-control"
        if discriminates
        else "FAILED:AUD-0033-refute-resolver-control",
    ]
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "refute-resolver-control.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if discriminates else 1


if __name__ == "__main__":
    raise SystemExit(main())
