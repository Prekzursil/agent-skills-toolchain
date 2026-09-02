"""Hunt the three 08/09/10 bodies and the numbered ledger set."""
from __future__ import annotations

from pathlib import Path

from names import ARTIFACTS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SEARCH_BASES = (
    Path("/root/.claude/harness-restore-20260806"),
    Path.home() / ".claude/harness-restore-20260806",
    Path("/home/Prekzursil/.claude/harness-restore-20260806"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806"),
    REPO,
    REPO / "command-center",
    REPO / "command-center/wfa",
    REPO / "command-center/sources",
    REPO / "command-center/p2-wave",
    REPO / "harness-restore-20260806",
    HERE / "fixtures" / "live",
)

LEDGER_NAMES = (
    "01-PROGRAM-CHARTER.json",
    "02-OWNER-DECISIONS.json",
    "03-CONSTRAINT-REGISTER.json",
    "04-RISK-REGISTER.json",
    "05-OPEN-QUESTIONS.json",
    "06-GLOSSARY.json",
    "07-OPTION-UNIVERSE.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "13-ARCHITECTURE-CANDIDATES.md",
)


def _rel_or_abs(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def hunt_one(name: str) -> dict:
    repo_hits: list[str] = []
    external: list[dict] = []
    seen: set[str] = set()
    for base in SEARCH_BASES:
        path = Path(base) / name
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        exists = path.is_file()
        try:
            inside = REPO.resolve() in path.resolve().parents or path.resolve() == REPO.resolve()
        except OSError:
            inside = False
        rec = {"path": str(path) if not inside else _rel_or_abs(path), "present": exists}
        if inside:
            if exists:
                repo_hits.append(_rel_or_abs(path))
        else:
            external.append(rec)
    return {
        "name": name,
        "present": bool(repo_hits) or any(x["present"] for x in external),
        "repo_hits": repo_hits,
        "external": external,
    }


def hunt_artifacts() -> list[dict]:
    return [hunt_one(name) for name in ARTIFACTS]


def hunt_ledgers() -> list[dict]:
    return [hunt_one(name) for name in LEDGER_NAMES]
