"""Both-states mutants: adapters that manufacture structure."""
from __future__ import annotations

import re
from pathlib import Path

from adapter import EXTRACTED, NOT_EXTRACTABLE, extract_skill

OL_ANY = re.compile(r"^(\s*)(\d+)\.\s+(\S.*)$", re.MULTILINE)


def mutant_never_refuse(path: Path) -> dict:
    """Always emits at least one invented stage. Accuracy without refusal is fake."""
    got = extract_skill(path)
    if got["verdict"] == NOT_EXTRACTABLE:
        rel = Path(path).as_posix()
        got = {
            **got,
            "verdict": EXTRACTED,
            "reason": "MUTANT: invented a stage rather than refuse",
            "stages": [
                {
                    "id": "stage-1",
                    "order": 1,
                    "title": "Follow the skill",
                    "kind": "invented",
                    "source_anchor": {
                        "path": rel,
                        "line": 1,
                        "snippet": "invented",
                    },
                }
            ],
            "mutant": "never-refuse",
        }
    return got


def mutant_whole_file(path: Path) -> dict:
    """Treats frontmatter and fences as body. Use-versus-mention failure."""
    text = Path(path).read_text(encoding="utf-8")
    stages = []
    for i, line in enumerate(text.splitlines(), 1):
        m = OL_ANY.match(line)
        if not m:
            continue
        stages.append(
            {
                "id": f"stage-{m.group(2)}",
                "order": int(m.group(2)),
                "title": m.group(3).strip(),
                "kind": "whole-file",
                "source_anchor": {
                    "path": Path(path).as_posix(),
                    "line": i,
                    "snippet": line.strip()[:200],
                },
            }
        )
    if len(stages) >= 2:
        return {
            "skill_id": Path(path).parent.name,
            "path": Path(path).as_posix(),
            "verdict": EXTRACTED,
            "reason": "MUTANT: whole-file ordinals including frontmatter/fences",
            "stages": stages,
            "mutant": "whole-file",
        }
    return extract_skill(path)
