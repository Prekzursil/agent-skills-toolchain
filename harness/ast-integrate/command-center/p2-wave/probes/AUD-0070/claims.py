"""Claim records for AUD-0070.

Loads AUD-0068 canonical records when present. On this sparse worktree they
are absent, so claims are extracted from the disclosed fixture estate with
explicit as_of, polarity, object_key, and a verbatim source span.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

import corpus as C  # noqa: E402

AUD0068 = REPO / "command-center" / "audit" / "AUD-0068-claim-extraction-canonical.json"

OBJECT_COLLISION = "architecture-option-id-collision"
OBJECT_TOOLS_LIB = "tools-lib-directory-presence"
OBJECT_LOCKFILE = "lockfile-integrity"
OBJECT_M16_OPTION = "namespace-option-universe:M-16"
OBJECT_M16_WAVE3 = "namespace-wave3-deliverable:M-16"
OBJECT_MECH12 = "namespace-architecture-mech:MECH-12"

KNOWN_A = "CLM-DEC-175"
KNOWN_B = "CLM-DOC13-MECH"
HOMONYM_A = "CLM-OPT-M16"
HOMONYM_B = "CLM-W3-M16"
COMPAT_A = "CLM-MECH12-DEF"
COMPAT_B = "CLM-MECH12-SPEC"
PLANT_SAME_A = "CLM-LIB-PRESENT"
PLANT_SAME_B = "CLM-LIB-ABSENT"
PLANT_LATER_A = "CLM-LOCK-BROKEN"
PLANT_LATER_B = "CLM-LOCK-REPAIRED"

NAMESPACES = [
    {
        "id": "NS-OPTION-UNIVERSE",
        "token_shape": "M-NN",
        "defining_artifact": "07-OPTION-UNIVERSE.md",
        "example_ids": ["M-1", "M-16"],
        "note": "Family M option cards (33 ids in the full universe).",
    },
    {
        "id": "NS-ARCHITECTURE-MECH",
        "token_shape": "MECH-NN (was M-NN before 2026-08-07)",
        "defining_artifact": "13-ARCHITECTURE-CANDIDATES.md",
        "example_ids": ["MECH-1", "MECH-12"],
        "note": "Architecture-candidate mechanisms; re-prefixed 2026-08-07.",
    },
    {
        "id": "NS-WAVE3-DELIVERABLE",
        "token_shape": "M-16 as Research Harness",
        "defining_artifact": "wave3/SKILL.md",
        "example_ids": ["M-16"],
        "note": "Wave-3 deliverable id baked into duplicated skill trees.",
    },
    {
        "id": "NS-WAVE1-REGISTER",
        "token_shape": "M-1 / M-3 mission grades",
        "defining_artifact": "wave1/REGISTER.md",
        "example_ids": ["M-1", "M-3"],
        "note": "Wave-1 register grades, not option cards.",
    },
]


def _span(path: Path, needle: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            rel = path.relative_to(HERE).as_posix()
            return {"path": rel, "line": i, "quote": line.strip()}
    raise ValueError(f"needle not found in {path}: {needle!r}")


def _claim(
    claim_id: str,
    object_key: str,
    polarity: str,
    as_of: str,
    span: dict[str, Any],
    proposition: str,
    namespace: str,
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "object_key": object_key,
        "polarity": polarity,
        "as_of": as_of,
        "source_path": span["path"],
        "source_line": span["line"],
        "span": span["quote"],
        "proposition": proposition,
        "namespace": namespace,
        "corpus_role": "fixture",
    }


def load_aud0068() -> dict[str, Any]:
    rel = AUD0068.relative_to(REPO).as_posix()
    if not AUD0068.is_file():
        return {"present": False, "path": rel, "bytes": 0, "claims": []}
    doc = json.loads(AUD0068.read_text(encoding="utf-8"))
    claims: list[dict[str, Any]] = []
    for key in ("claims", "records", "claim_records"):
        val = doc.get(key)
        if isinstance(val, list):
            claims = [c for c in val if isinstance(c, dict)]
            break
    return {
        "present": True,
        "path": rel,
        "bytes": AUD0068.stat().st_size,
        "claims": claims,
    }


def extract_fixture_claims(estate: Path) -> list[dict[str, Any]]:
    dec = estate / "17-DECISION-LOG.md"
    arch = estate / "13-ARCHITECTURE-CANDIDATES.md"
    opt = estate / "07-OPTION-UNIVERSE.md"
    w3 = estate / "wave3" / "SKILL.md"
    lib_p = estate / "notes" / "tools-lib-present.md"
    lib_a = estate / "notes" / "tools-lib-absent.md"
    lock_b = estate / "notes" / "lockfile-broken.md"
    lock_r = estate / "notes" / "lockfile-repaired.md"

    return [
        _claim(
            KNOWN_A,
            OBJECT_COLLISION,
            "OPEN",
            "2026-07-21",
            _span(dec, "still live (present tense)"),
            "The architecture-vs-option M-NN collision is still live.",
            "decision-log",
        ),
        _claim(
            KNOWN_B,
            OBJECT_COLLISION,
            "CLOSED",
            "2026-08-07",
            _span(arch, "zero bare M-NN tokens"),
            "Doc 13 re-prefixed mechanisms to MECH-NN; zero bare M-NN remain.",
            "architecture-candidates",
        ),
        _claim(
            HOMONYM_A,
            OBJECT_M16_OPTION,
            "EXISTS",
            "2026-06-01",
            _span(opt, "Family M option card M-16"),
            "M-16 is family-M option card 16 in the option universe.",
            "NS-OPTION-UNIVERSE",
        ),
        _claim(
            HOMONYM_B,
            OBJECT_M16_WAVE3,
            "EXISTS",
            "2026-07-15",
            _span(w3, "Research Harness (M-16)"),
            "M-16 is the wave-3 Research Harness deliverable.",
            "NS-WAVE3-DELIVERABLE",
        ),
        _claim(
            COMPAT_A,
            OBJECT_MECH12,
            "EXISTS",
            "2026-08-07",
            _span(arch, "Architecture-candidate mechanism MECH-12"),
            "MECH-12 is an architecture-candidate mechanism.",
            "NS-ARCHITECTURE-MECH",
        ),
        _claim(
            COMPAT_B,
            OBJECT_MECH12,
            "EXISTS",
            "2026-08-07",
            _span(arch, "Architecture-candidate mechanism MECH-12"),
            "MECH-12 is specified in 13-ARCHITECTURE-CANDIDATES after the re-prefix.",
            "NS-ARCHITECTURE-MECH",
        ),
        _claim(
            PLANT_SAME_A,
            OBJECT_TOOLS_LIB,
            "EXISTS",
            "2026-08-01",
            _span(lib_p, "tools/lib/ is present"),
            "tools/lib/ is present and is the salvage home.",
            "planted-same-time",
        ),
        _claim(
            PLANT_SAME_B,
            OBJECT_TOOLS_LIB,
            "ABSENT",
            "2026-08-01",
            _span(lib_a, "does not exist"),
            "tools/lib/ does not exist on this checkout.",
            "planted-same-time",
        ),
        _claim(
            PLANT_LATER_A,
            OBJECT_LOCKFILE,
            "OPEN",
            "2026-06-01",
            _span(lock_b, "lockfile integrity is broken"),
            "lockfile integrity is broken.",
            "planted-later-resolution",
        ),
        _claim(
            PLANT_LATER_B,
            OBJECT_LOCKFILE,
            "CLOSED",
            "2026-08-10",
            _span(lock_r, "lockfile integrity was repaired"),
            "lockfile integrity was repaired on 2026-08-10.",
            "planted-later-resolution",
        ),
    ]


def load_claims() -> dict[str, Any]:
    estate = C.materialize()
    fixture = extract_fixture_claims(estate)
    upstream = load_aud0068()
    return {
        "estate": estate.relative_to(REPO).as_posix(),
        "aud0068": {k: v for k, v in upstream.items() if k != "claims"},
        "aud0068_claim_count": len(upstream["claims"]),
        "namespaces": NAMESPACES,
        "claims": fixture,
        "live_presence": C.live_presence(REPO),
        "note": (
            "AUD-0068 canonical claim records are absent on this worktree. "
            "Claims were extracted from a disclosed reconstruction of the "
            "surfaces named in the catalog (17-DECISION-LOG.md:175, the "
            "2026-08-07 MECH re-prefix of doc 13, and the four M-NN "
            "namespaces), plus planted same-time and later-resolution pairs."
        ),
    }


def by_id(claims: list[dict[str, Any]], claim_id: str) -> dict[str, Any]:
    for c in claims:
        if c["claim_id"] == claim_id:
            return c
    raise KeyError(claim_id)
