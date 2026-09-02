"""Build on-disk reconstructed fixtures for CNL-0002."""
from __future__ import annotations

import json
from pathlib import Path

from constants import (
    CATALOGUE_ROOT_KEYS,
    CM01_UNRECOGNISED,
    DISCOVERY_STATUS,
    OVERLAP_OPTIONAL,
    PRESET_COUNT,
    PROTOCOL_COUNT,
    REQUIRED_12,
    SCHEMA_RELATIONSHIP_PROSE,
)
from schemas import (
    catalogue_schema,
    spec_ref,
    tagged_union_schema,
    v1_charter_schema,
)

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def cm01_record() -> dict:
    """20-key protocol record: 4 keys overlap v1 properties, description is object."""
    rec = {
        "id": "C-M01",
        "title": "Majority-with-dissent protocol",
        "status": DISCOVERY_STATUS,
        "description": {
            "kind": "protocol",
            "notes": "reconstructed stand-in; object on purpose so v1 string type fires",
        },
        "name": "majority-with-dissent",
        "protocol_class": "deliberation",
        "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        "anti_failure": {"on_split": "surface-disagreement"},
        "audit": {"persist_transcript": True},
        "consensus": {"reducer": "shared-completion-predicate-name"},
        "discovery_only": True,
        "version": "0.0-reconstructed",
        "seats": 4,
        "budgets": {"max_rounds": 8},
        "evidence": {"votes_require_evidence": True},
        "outcomes": {"on_unresolved": "BLOCKED"},
        "integrity": {"hash_inputs": True},
        "artifacts": {"transcript": True},
        "execution": {"substrate": "simulator"},
        "bound_preset_ids": ["P-001"],
    }
    assert len(rec) == 20, len(rec)
    recognised = set(rec) & set(list(REQUIRED_12) + list(OVERLAP_OPTIONAL) + ["meta"])
    # recognised against v1.properties which includes required+optional+overlap
    assert recognised == set(OVERLAP_OPTIONAL), recognised
    unknown = [k for k in rec if k in CM01_UNRECOGNISED]
    assert len(unknown) == 16, len(unknown)
    return rec


def protocol_n(n: int) -> dict:
    if n == 1:
        return cm01_record()
    return {
        "id": f"C-M{n:02d}",
        "status": DISCOVERY_STATUS,
        "title": f"reconstructed protocol {n:02d}",
        "description": f"stand-in protocol record {n:02d}",
    }


def preset_n(n: int) -> dict:
    bound = f"C-M{((n - 1) % PROTOCOL_COUNT) + 1:02d}"
    return {
        "id": f"P-{n:03d}",
        "status": DISCOVERY_STATUS,
        "bound_protocol": bound,
        "title": f"reconstructed preset {n:03d}",
        "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        "voting": {"rule": "unanimous-or-record-dissent"},
        "stopping": {"max_rounds": 8},
    }


def catalogue_mismatch() -> dict:
    """Original-shape catalogue root: disjoint from the 12 required keys."""
    protocols = [protocol_n(i) for i in range(1, PROTOCOL_COUNT + 1)]
    presets = [preset_n(i) for i in range(1, PRESET_COUNT + 1)]
    doc = {
        "schema_relationship": SCHEMA_RELATIONSHIP_PROSE,
        "protocols": protocols,
        "presets": presets,
    }
    assert tuple(doc.keys()) == CATALOGUE_ROOT_KEYS or set(doc) == set(
        CATALOGUE_ROOT_KEYS
    )
    assert not (set(doc) & set(REQUIRED_12))
    assert len(protocols) == PROTOCOL_COUNT
    assert len(presets) == PRESET_COUNT
    return doc


def catalogue_repaired() -> dict:
    doc = catalogue_mismatch()
    doc["spec_ref"] = spec_ref()
    return doc


def valid_charter() -> dict:
    body = {k: f"charter-{k}" for k in REQUIRED_12}
    body["meta"] = "thirteenth-instance-property"
    return body


def invalid_protocol() -> dict:
    return {"title": "missing-id-and-status"}


def tagged_catalogue() -> dict:
    doc = catalogue_mismatch()
    doc["artifact_type"] = "protocol-preset-catalogue"
    return doc


def write_all() -> dict[str, str]:
    FIX.mkdir(parents=True, exist_ok=True)
    files = {
        "v1-charter.schema.json": v1_charter_schema(),
        "tagged-union.schema.json": tagged_union_schema(),
        "catalogue.schema.json": catalogue_schema(),
        "catalogue-v1-mismatch.json": catalogue_mismatch(),
        "catalogue-repaired.json": catalogue_repaired(),
        "catalogue-synthetic-tag.json": tagged_catalogue(),
        "C-M01.json": cm01_record(),
        "charter-valid.json": valid_charter(),
        "protocol-invalid.json": invalid_protocol(),
        "provenance.json": {
            "reconstructed": True,
            "reason": (
                "11-COUNCIL-SPECIFICATION.schema.json and "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this worktree"
            ),
            "protocol_count": PROTOCOL_COUNT,
            "preset_count": PRESET_COUNT,
            "required_12": list(REQUIRED_12),
            "do_not_cite_as_measurement": "schema_relationship",
        },
    }
    rels = {}
    for name, obj in files.items():
        path = FIX / name
        dump(path, obj)
        rels[name] = str(path)
    return rels


if __name__ == "__main__":
    written = write_all()
    for name in written:
        print("wrote", name)
    print("SUCCESS:CNL-0002-fixtures")
