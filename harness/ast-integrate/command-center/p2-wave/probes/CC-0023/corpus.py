"""Pinned control corpus for the 58 undecidable bare M-NN references.

Documents 16, 18 and 19 are absent from this worktree. This corpus reconstructs
the catalogued structure: 58 live citations of 12 colliding tokens, no
discriminating token in the surrounding prose, plus separate controls.
"""
from __future__ import annotations

from pathlib import Path

# 12 foundation decisions (one per colliding token) covering 58 references.
TOKEN_COUNTS: list[tuple[str, int]] = [
    ("M-1", 6),
    ("M-3", 6),
    ("M-5", 5),
    ("M-8", 5),
    ("M-10", 5),
    ("M-12", 5),
    ("M-16", 8),
    ("M-18", 4),
    ("M-20", 4),
    ("M-22", 4),
    ("M-24", 3),
    ("M-31", 3),
]

DOC_FILES = (
    "16-GRILL-QUEUE.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
)

DOC_TITLES = {
    "16-GRILL-QUEUE.md": "16 Grill Queue",
    "18-OPEN-UNKNOWNS-AND-PROBES.md": "18 Open Unknowns And Probes",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md": "19 Substance Audit Blueprints",
}

TEMPLATES = (
    "Queue item {seq} continues at {token} after the previous checkpoint.",
    "Resume {token} once the prior gate is closed.",
    "The next work item cites {token} with no further qualifier.",
    "Carry {token} into the following session unchanged.",
)


def _placements() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    i = 0
    for token, count in TOKEN_COUNTS:
        for _ in range(count):
            rows.append((DOC_FILES[i % 3], token))
            i += 1
    return rows


def build_documents() -> dict[str, str]:
    if sum(c for _, c in TOKEN_COUNTS) != 58:
        raise RuntimeError("TOKEN_COUNTS must sum to 58")
    if len(TOKEN_COUNTS) != 12:
        raise RuntimeError("TOKEN_COUNTS must have 12 foundation tokens")
    buckets: dict[str, list[str]] = {name: [] for name in DOC_FILES}
    for i, (doc, token) in enumerate(_placements()):
        tmpl = TEMPLATES[i % len(TEMPLATES)]
        buckets[doc].append(tmpl.format(token=token, seq=i + 1))
    out: dict[str, str] = {}
    for name in DOC_FILES:
        title = DOC_TITLES[name]
        body = "\n".join(buckets[name])
        # MECH-NN must not be reported as a bare M-NN (false-positive control).
        mech_line = "False-positive control: MECH-16 already carries the architecture prefix."
        out[name] = f"# {title}\n\nWork queue notes. Tokens below are live citations, not definitions.\n\n{body}\n\n{mech_line}\n"
    out["controls.md"] = _controls()
    return out


def _controls() -> str:
    return """# Resolver controls (not part of the 58)

A currently-true uniquely-held number must resolve mechanically:

See option-universe card M-33 for the leftover family-M id.

See architecture mechanism card M-34 after the re-prefix discussion.

Use-vs-mention: a quoting document describing the collision is not a live citation.

> Mention-only: the historical 31-way M-NN collision is described here so a quoting document is not flagged. Example tokens in this sentence: M-16 and M-1.

Inline mention should also be ignored: `M-16` is quoted, not used.

Fenced mention:

```
collision example only: M-16 vs MECH-16
```
"""


def write_fixtures(dest: Path) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for name, text in build_documents().items():
        path = dest / name
        path.write_text(text, encoding="utf-8", newline="\n")
        written[name] = path
    return written


def expected_undecidable_count() -> int:
    return sum(c for _, c in TOKEN_COUNTS)


def expected_question_count() -> int:
    return len(TOKEN_COUNTS)
