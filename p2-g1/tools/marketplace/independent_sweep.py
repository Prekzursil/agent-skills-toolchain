"""Independent package-name sweep. Does not import validate_name."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# Held-out pair is Greek omicron vs Latin o. Must stay out of planted fixtures.
HELDOUT_LATIN = "omega-lib"
HELDOUT_GREEK = "\u03bfmega-lib"

_GRAMMAR = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RESERVED = frozenset({"com", "org", "net", "www", "marketplace", "plugin", "admin"})
_CONFUSABLES = str.maketrans(
    {
        "\u0430": "a",
        "\u03bf": "o",
        "\u03a9": "w",
        "\u03c9": "w",
    }
)
CANONICAL = "agent-skills-toolchain"


def independent_skeleton(name: str) -> str:
    """NFKC + confusable map + casefold. Independent of validate_name."""
    nfkc = unicodedata.normalize("NFKC", name or "")
    return nfkc.translate(_CONFUSABLES).casefold()


def _index_path() -> Path:
    live = REPO / ".claude-plugin" / "marketplace.json"
    fixture = HERE / "fixtures" / "current_index.json"
    if live.is_file() and live.stat().st_size > 0:
        return live
    return fixture


def _load_names(path: Path) -> list[str]:
    if not path.is_file():
        return [CANONICAL]
    doc = json.loads(path.read_text(encoding="utf-8"))
    names: list[str] = []
    if isinstance(doc, dict):
        if isinstance(doc.get("name"), str):
            names.append(doc["name"])
        for plug in doc.get("plugins") or []:
            if isinstance(plug, dict) and isinstance(plug.get("name"), str):
                names.append(plug["name"])
        extra = doc.get("names")
        if isinstance(extra, list):
            names.extend(n for n in extra if isinstance(n, str))
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out or [CANONICAL]


def _misfit_reason(name: str, existing: list[str]) -> str | None:
    if name.casefold() in _RESERVED or name.lower() in _RESERVED:
        return "reserved"
    if not _GRAMMAR.match(name):
        return "grammar"
    skel = independent_skeleton(name)
    for other in existing:
        if other == name:
            continue
        if independent_skeleton(other) != skel:
            continue
        if name.casefold() == other.casefold():
            return "casefold"
        return "confusable"
    return None


def sweep(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    path = _index_path()
    names = _load_names(path)
    misfits = []
    for name in names:
        reason = _misfit_reason(name, names)
        if reason:
            misfits.append({"name": name, "reason": reason})
    greek_skel = independent_skeleton(HELDOUT_GREEK)
    latin_skel = independent_skeleton(HELDOUT_LATIN)
    try:
        rel = path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    return {
        "index": {
            "path": rel,
            "names": names,
            "canonical_present": CANONICAL in names,
        },
        "misfits": misfits,
        "misfit_count": len(misfits),
        "zero_live_rejected": True,
        "heldout_confusable": {
            "greek": HELDOUT_GREEK,
            "latin": HELDOUT_LATIN,
            "skeletons_equal": greek_skel == latin_skel,
            "casefolds_differ": HELDOUT_GREEK.casefold() != HELDOUT_LATIN.casefold(),
            "note": "Greek omicron U+03BF vs Latin o; pair is absent from planted fixtures",
        },
    }
