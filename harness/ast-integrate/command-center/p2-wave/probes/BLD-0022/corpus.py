"""Load speaker-labeled utterances. Speaker comes from speakers.json, not wording."""
from __future__ import annotations

import json
from pathlib import Path

from classify import Utterance

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REPO = HERE.parents[3]


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def load_speakers(spec: Path | None = None) -> dict[str, str]:
    path = spec or (FIXTURES / "speakers.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    files = doc.get("files") or {}
    return {str(k): str(v).lower() for k, v in files.items()}


def load_fixture_utterances() -> list[Utterance]:
    speakers = load_speakers()
    out: list[Utterance] = []
    for name, speaker in speakers.items():
        path = FIXTURES / name
        if not path.is_file():
            raise FileNotFoundError(path)
        rel = _rel(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, raw in enumerate(lines, 1):
            text = raw.strip()
            if not text or text.startswith("#") or text.startswith("{"):
                continue
            if text.startswith("Owner utterance") or text.startswith("Agent utterance"):
                continue
            out.append(Utterance(speaker=speaker, path=rel, line=i, text=text))
    return out


def catalog_agent_utterances() -> list[Utterance]:
    """WORK-UNIT-CATALOG.json is program-authored. Every line is speaker=agent."""
    rel = "command-center/WORK-UNIT-CATALOG.json"
    path = REPO / rel
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[Utterance] = []
    for i, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text:
            continue
        out.append(Utterance(speaker="agent", path=rel, line=i, text=text))
    return out


def existing_source_paths() -> dict[str, bool]:
    candidates = [
        "07-OPTION-UNIVERSE.json",
        "07-OPTION-UNIVERSE.md",
        "17-DECISION-LOG.md",
        "command-center/OWNER-DECISIONS.md",
        "OWNER-DECISIONS.md",
        "_USER-PROMPTS.md",
        "command-center/_USER-PROMPTS.md",
        "32-OWNER-DECISIONS.md",
        "command-center/OPTION-ID-RESOLUTION.json",
    ]
    return {p: (REPO / p).is_file() for p in candidates}
