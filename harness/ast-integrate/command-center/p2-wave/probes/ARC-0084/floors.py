"""Derive per-class size floors from real on-disk artifacts, not a guessed constant.

Rule: for each class with at least one real member, the floor is the largest
power of two strictly below the observed minimum. That is always > 1 byte on
this tree (a 1-byte floor is forbidden because it cannot reject a stub).
Fixture trees under probes/*/fixtures/ are excluded so toy MANIFEST.json
files do not collapse the manifest class. Empty JSON objects (`{}`) and
other content-less stubs are skipped as not-real artifacts and listed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CLASSES = ("receipt", "schema", "dossier", "manifest", "markdown", "contract")

# Inherit only when the class has no real members (this unit's own contract is
# excluded from the contract population so emit is not circular).
INHERIT: dict[str, str] = {}
FALLBACK_INHERIT = {"contract": "schema", "dossier": "schema"}


def _is_fixture(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return "fixtures" in parts or any(p.startswith("_") for p in parts)


def _json_object(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _is_real(cls: str, path: Path) -> tuple[bool, str]:
    """Population filter: stubs are not the distribution that floors come from."""
    if cls == "markdown":
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text.strip()) < 32 or not text.lstrip().startswith("#"):
            return False, "markdown-not-a-document"
        return True, ""
    doc = _json_object(path)
    if doc is None:
        return False, "unparseable-or-not-object"
    if not doc:
        return False, "empty-object-stub"
    if cls == "schema":
        if not any(k in doc for k in ("$schema", "$id", "title", "properties", "$defs")):
            return False, "schema-without-schema-keys"
        return True, ""
    if cls == "receipt":
        if not doc.get("unit_id"):
            return False, "receipt-without-unit_id"
        return True, ""
    if cls == "manifest":
        arts = doc.get("artifacts")
        if not isinstance(arts, list) or not arts:
            return False, "manifest-without-artifacts"
        return True, ""
    if cls in {"dossier", "contract"}:
        if not (doc.get("unit_id") or doc.get("architecture_id") or doc.get("$schema")):
            return False, "dossier-without-identity"
        return True, ""
    return True, ""


def _collect() -> tuple[dict[str, list[tuple[str, int]]], list[dict[str, Any]]]:
    cc = REPO / "command-center"
    groups: dict[str, list[tuple[str, int]]] = {c: [] for c in CLASSES}
    skipped: list[dict[str, Any]] = []

    def add(cls: str, path: Path) -> None:
        if not path.is_file():
            return
        rel = path.relative_to(REPO).as_posix()
        if _is_fixture(rel):
            skipped.append({"path": rel, "reason": "fixture", "class": cls})
            return
        ok, reason = _is_real(cls, path)
        if not ok:
            skipped.append(
                {
                    "path": rel,
                    "reason": reason,
                    "class": cls,
                    "bytes": path.stat().st_size,
                }
            )
            return
        groups[cls].append((rel, path.stat().st_size))

    schema_dir = cc / "schema"
    if schema_dir.is_dir():
        for path in sorted(schema_dir.glob("*.json")):
            add("schema", path)
    phase3 = cc / "phase3"
    if phase3.is_dir():
        for path in sorted(phase3.rglob("*.json")):
            add("dossier", path)
    # Catalog inputs WINNING-ARCHITECTURE.json / ARCHITECTURE-RATIFICATION.json
    # are absent on this worktree (phase3 is .gitkeep only). Live architecture
    # records with architecture_id are the substitute population; fixtures stay
    # excluded via _is_fixture.
    probes = cc / "p2-wave" / "probes"
    if probes.is_dir():
        skip_names = {"SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"}
        for path in sorted(probes.glob("ARC-*/*.json")):
            if path.name in skip_names:
                continue
            doc = _json_object(path)
            if isinstance(doc, dict) and doc.get("architecture_id"):
                add("dossier", path)
    add("manifest", cc / "ARTIFACT-MANIFEST.json")
    if probes.is_dir():
        for path in sorted(probes.glob("*/SUBAGENT-RETURN.json")):
            add("receipt", path)
        for path in sorted(probes.glob("*/UNIT-ARTIFACT-MANIFEST.json")):
            add("manifest", path)
    wave = cc / "p2-wave"
    if wave.is_dir():
        for path in sorted(wave.glob("*.md")):
            add("markdown", path)
    contracts = cc / "phase4" / "contracts"
    if contracts.is_dir():
        for path in sorted(contracts.glob("ARC-*.json")):
            if path.name == "ARC-0084.json":
                continue
            add("contract", path)
    return groups, skipped


def _witnesses(members: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """min / p50 / max of the live population. The floor is derived from all members."""
    if not members:
        return []
    ordered = sorted(members, key=lambda row: (row[1], row[0]))
    picks = [ordered[0], ordered[len(ordered) // 2], ordered[-1]]
    out: list[tuple[str, int]] = []
    seen: set[str] = set()
    for item in picks:
        if item[0] in seen:
            continue
        seen.add(item[0])
        out.append(item)
    return out


def _power_floor(observed_min: int) -> int:
    if observed_min <= 2:
        raise ValueError(
            f"observed_min={observed_min} cannot yield a floor > 1 that members still pass"
        )
    power = 1
    while power * 2 < observed_min:
        power *= 2
    if power <= 1:
        raise ValueError(f"floor collapsed to 1 for observed_min={observed_min}")
    return power


def derive(root: Path | None = None) -> dict[str, Any]:
    """Return derivation document. `root` unused except to keep the API honest."""
    del root
    groups, skipped = _collect()
    inherit = dict(INHERIT)
    for cls, source in FALLBACK_INHERIT.items():
        if not groups.get(cls):
            inherit[cls] = source
    classes: dict[str, Any] = {}
    floors: dict[str, int] = {}
    for cls in CLASSES:
        source_cls = inherit.get(cls, cls)
        members = sorted(groups[source_cls], key=lambda row: (row[1], row[0]))
        if cls != source_cls:
            own = groups[cls]
            note = (
                f"no measured {cls} members yet (or self excluded); "
                f"floor inherited from class {source_cls} (n={len(members)})"
            )
        else:
            own = members
            note = (
                "derived from live members excluding probes/*/fixtures/ "
                "and empty-object stubs"
            )
        if not members:
            raise ValueError(f"class {source_cls} has zero real members on disk")
        sizes = [size for _, size in members]
        floor = _power_floor(min(sizes))
        if any(size < floor for size in sizes):
            raise ValueError(f"class {cls} member below derived floor {floor}")
        floors[cls] = floor
        witnesses = _witnesses(members)
        classes[cls] = {
            "n": len(own) if cls not in inherit else len(groups[cls]),
            "source_class": source_cls,
            "observed_min": min(sizes),
            "observed_p50": sizes[len(sizes) // 2],
            "observed_max": max(sizes),
            "floor": floor,
            "floor_rule": "largest power of two strictly below observed_min",
            "note": note,
            "members": [{"path": path, "bytes": size} for path, size in witnesses],
            "members_are_population_witnesses": True,
            "witness_rule": "min, p50, and max of the live population",
        }
    return {
        "method": (
            "largest power of two strictly below the observed minimum of real "
            "on-disk members; fixtures, empty-object stubs, and content-less "
            "files excluded from the population; never 1 byte"
        ),
        "skipped_stubs": skipped,
        "historical_guess_rejected": {
            "DEFAULT_MIN_BYTES": 1024,
            "why_not_used_as_authority": (
                "TST-0007 records that reverting 1024->512 left a 15/15 green "
                "suite because tests passed min_bytes explicitly. A constant "
                "that is never derived from the live distribution is not this "
                "unit's floor."
            ),
        },
        "one_byte_forbidden": True,
        "classes": classes,
        "floors": floors,
    }


def floors() -> dict[str, int]:
    return dict(derive()["floors"])
