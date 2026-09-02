#!/usr/bin/env python3
"""Fixture corpus and live-file search for BLD-0021.

Live docs 16/18/19, 07-OPTION-UNIVERSE, and OPTION-ID-RESOLUTION.json are
absent from this Linux worktree. The 58 UNDECIDABLE M-NN control is
reproduced here as an explicit reconstruction, not as recovered live bytes.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
REG = FIX / "registries"
CORPUS = FIX / "corpus"

DOC16 = "16-GRILL-QUEUE.md"
DOC18 = "18-OPEN-UNKNOWNS-AND-PROBES.md"
DOC19 = "19-SUBSTANCE-AUDIT-BLUEPRINTS.md"

# 58 USE occurrences of bare M-NN whose numbers exist in both option-universe
# (M-1..M-33) and architecture-candidates (MECH-1..MECH-38). No discriminating
# tokens in the surrounding prose.
UNDECIDABLE_NUMBERS: list[int] = list(range(1, 34)) + list(range(1, 26))
assert len(UNDECIDABLE_NUMBERS) == 58

SPLITS = (20, 20, 18)
assert sum(SPLITS) == 58

LIVE_SOUGHT = [
    "07-OPTION-UNIVERSE.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "16-GRILL-QUEUE.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
    "17-DECISION-LOG.md",
    "OPTION-ID-RESOLUTION.json",
    "wave1/REGISTER.md",
    "wave3/ast-cc/skills/deep-research/SKILL.md",
]

HEADER = (
    "<!-- Fixture reconstruction for unit BLD 0021. "
    "This is not recovered live-estate bytes. -->\n"
)

USE_LINE = "Cross-ref M-{n} appears in the shared queue without a namespace cue.\n"

PLANTED_ABSENT = "ZX-9999"


def _write_json(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def option_cards() -> list[dict]:
    return [
        {
            "id": f"M-{n}",
            "number": n,
            "title": f"option-universe card M-{n}",
        }
        for n in range(1, 34)
    ]


def mechanism_cards() -> list[dict]:
    return [
        {
            "id": f"MECH-{n}",
            "number": n,
            "historical_id": f"M-{n}",
            "title": f"architecture-candidates mechanism MECH-{n}",
        }
        for n in range(1, 39)
    ]


def split_undecidable() -> dict[str, list[int]]:
    a, b, c = SPLITS
    nums = UNDECIDABLE_NUMBERS
    return {
        DOC16: nums[:a],
        DOC18: nums[a : a + b],
        DOC19: nums[a + b : a + b + c],
    }


def _doc_body(name: str, numbers: list[int]) -> str:
    lines = [HEADER, f"# {name} (fixture reconstruction)\n", "\n"]
    for n in numbers:
        lines.append(USE_LINE.format(n=n))
    return "".join(lines)


def mention_control_text() -> str:
    return (
        HEADER
        + "# mention-control\n\n"
        + "A fenced example:\n\n"
        + "```\nM-16 is only a mention here\n```\n\n"
        + 'Quoted example: "M-16"\n\n'
        + "Inline: `M-22`\n\n"
        + "A discriminated USE: the option M-8 is selected.\n"
    )


def controls_text() -> str:
    return (
        HEADER
        + "# resolver-controls\n\n"
        + "MECH-4 is a unique prefix and must RESOLVES-ONE.\n"
        + "The mechanism M-20 is discriminated toward architecture-candidates.\n"
        + "The Research Harness M-16 is discriminated by harness.\n"
        + "The mission-grade M-1 is discriminated toward wave1-register.\n"
        + "See RRR-1 in the shared queue.\n"
        + f"See {PLANTED_ABSENT} in the shared queue.\n"
    )


def ensure_fixtures() -> dict:
    REG.mkdir(parents=True, exist_ok=True)
    CORPUS.mkdir(parents=True, exist_ok=True)

    _write_json(
        REG / "option-universe.json",
        {
            "namespace_id": "option-universe",
            "prefix": "M",
            "also_bare_m": True,
            "source": "fixtures/registries/option-universe.json",
            "note": "33 cards; live 07-OPTION-UNIVERSE.md absent",
            "cards": option_cards(),
        },
    )
    _write_json(
        REG / "architecture-candidates.json",
        {
            "namespace_id": "architecture-candidates",
            "prefix": "MECH",
            "also_bare_m": True,
            "source": "fixtures/registries/architecture-candidates.json",
            "note": "38 MECH-NN cards; historical M-NN; live 13-ARCHITECTURE-CANDIDATES.md absent",
            "cards": mechanism_cards(),
        },
    )
    _write_json(
        REG / "wave3-deep-research.json",
        {
            "namespace_id": "wave3-deep-research",
            "prefix": "M",
            "also_bare_m": True,
            "source": "fixtures/registries/wave3-deep-research.json",
            "cards": [
                {
                    "id": "M-16",
                    "number": 16,
                    "title": "Research Harness (M-16)",
                }
            ],
        },
    )
    _write_json(
        REG / "wave1-register.json",
        {
            "namespace_id": "wave1-register",
            "prefix": "M",
            "also_bare_m": True,
            "source": "fixtures/registries/wave1-register.json",
            "cards": [
                {"id": "M-1", "number": 1, "title": "wave1 mission-grade M-1"},
                {"id": "M-3", "number": 3, "title": "wave1 mission-grade M-3"},
            ],
        },
    )
    _write_json(
        REG / "rrr-duplicate-a.json",
        {
            "namespace_id": "rrr-duplicate",
            "prefix": "RRR",
            "also_bare_m": False,
            "source": "fixtures/registries/rrr-duplicate-a.json",
            "cards": [{"id": "RRR-1", "number": 1, "title": "RRR-1 declaration A"}],
        },
    )
    _write_json(
        REG / "rrr-duplicate-b.json",
        {
            "namespace_id": "rrr-duplicate",
            "prefix": "RRR",
            "also_bare_m": False,
            "source": "fixtures/registries/rrr-duplicate-b.json",
            "cards": [{"id": "RRR-1", "number": 1, "title": "RRR-1 declaration B"}],
        },
    )
    _write_json(
        FIX / "OPTION-ID-RESOLUTION.json",
        {
            "schema_version": 1,
            "live_file": "command-center/OPTION-ID-RESOLUTION.json",
            "live_present": False,
            "colliding_bare_prefix": "M",
            "namespaces": [
                {
                    "id": "option-universe",
                    "prefix": "M",
                    "card_count": 33,
                },
                {
                    "id": "architecture-candidates",
                    "prefix": "MECH",
                    "historical_prefix": "M",
                    "card_count": 38,
                },
                {
                    "id": "wave3-deep-research",
                    "prefix": "M",
                    "card_count": 1,
                    "ids": ["M-16"],
                },
                {
                    "id": "wave1-register",
                    "prefix": "M",
                    "card_count": 2,
                    "ids": ["M-1", "M-3"],
                },
            ],
            "discriminating_tokens": {
                "option-universe": ["option", "options"],
                "architecture-candidates": ["MECH", "mechanism", "mechanisms"],
                "wave3-deep-research": ["harness"],
                "wave1-register": ["mission-grade", "mission grade"],
            },
        },
    )

    parts = split_undecidable()
    _write_text(CORPUS / DOC16, _doc_body(DOC16, parts[DOC16]))
    _write_text(CORPUS / DOC18, _doc_body(DOC18, parts[DOC18]))
    _write_text(CORPUS / DOC19, _doc_body(DOC19, parts[DOC19]))
    _write_text(CORPUS / "mention-control.md", mention_control_text())
    _write_text(CORPUS / "controls.md", controls_text())

    return {
        "root": "command-center/p2-wave/probes/BLD-0021/fixtures",
        "known_undecidable_planted": 58,
        "docs": {
            DOC16: len(parts[DOC16]),
            DOC18: len(parts[DOC18]),
            DOC19: len(parts[DOC19]),
        },
        "reconstruction": (
            "Live 16-GRILL-QUEUE.md, 18-OPEN-UNKNOWNS-AND-PROBES.md, and "
            "19-SUBSTANCE-AUDIT-BLUEPRINTS.md are absent. Fifty-eight bare "
            "M-NN USE lines were planted across fixture reconstructions of "
            "those three names, using numbers declared in both option-universe "
            "and architecture-candidates, with no discriminating token."
        ),
    }


def registry_paths() -> list[Path]:
    return sorted(REG.glob("*.json"))


def corpus_files() -> list[tuple[str, Path]]:
    files = []
    for path in sorted(CORPUS.glob("*.md")):
        rel = path.relative_to(REPO).as_posix()
        files.append((rel, path))
    return files


def docs_161819() -> set[str]:
    return {
        (CORPUS / DOC16).relative_to(REPO).as_posix(),
        (CORPUS / DOC18).relative_to(REPO).as_posix(),
        (CORPUS / DOC19).relative_to(REPO).as_posix(),
    }


def search_live() -> dict:
    found: list[str] = []
    by_name: dict[str, list[str]] = {}
    for name in LIVE_SOUGHT:
        hits = []
        if "/" in name:
            p = REPO / name
            if p.is_file():
                hits.append(name)
        else:
            for p in REPO.rglob(name):
                if p.is_file():
                    try:
                        rel = p.relative_to(REPO).as_posix()
                    except ValueError:
                        continue
                    # Sibling probe fixtures are not the live Prompt Two docs.
                    if "p2-wave/probes/" in rel.replace("\\", "/"):
                        continue
                    hits.append(rel)
        by_name[name] = hits
        found.extend(hits)
    docs_present = all(
        by_name.get(n)
        for n in (DOC16, DOC18, DOC19)
    )
    opt = REPO / "command-center" / "OPTION-ID-RESOLUTION.json"
    return {
        "sought": LIVE_SOUGHT,
        "found": found,
        "by_name": by_name,
        "docs_16_18_19_present": bool(docs_present),
        "option_id_resolution_present": opt.is_file(),
    }
