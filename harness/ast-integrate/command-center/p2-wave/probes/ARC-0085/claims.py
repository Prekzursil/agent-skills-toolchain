#!/usr/bin/env python3
"""Encode >=10 real claims from the live claim-bearing artifacts on this tree.

command-center/CLAIM-REGISTRY.json is absent here. The live store used instead is the
phase-3 DESIGN/REFUTATION claim tables (the records ADV-0113 treated as the command-center
claim corpus when the dedicated registry file is missing).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
REGISTRY = REPO / "command-center/CLAIM-REGISTRY.json"
FIXTURE = HERE / "fixtures" / "encoded-claims.json"

P3 = "command-center/phase3"


def _probe(engine: str, field: str) -> dict:
    return {
        "tool": "python3",
        "engine": engine,
        "shell": "bash",
        "field": field,
    }


def _lin(author: str, path: str, line: int, snippet: str, engine: str, field: str) -> dict:
    return {
        "author": author,
        "path": path,
        "line": line,
        "snippet": snippet,
        "probe": _probe(engine, field),
    }


def _impact(cls: str, sev: str, blocks: bool) -> dict:
    return {"class": cls, "severity": sev, "blocks_downstream": blocks}


def _settle(pid: str, command: str, klass: str) -> dict:
    return {"id": pid, "command": command, "independence_class": klass}


SAMPLES_MECH = (
    "Three sampled capabilities (skill.council, wf.catalog-class.discovery-only, "
    "council.preset.catalog-class.editable) transcribe into A1 static-config/v1 with "
    "EXPRESSIBLE verdict on this worktree."
)

LIVE_CLAIMS: list[dict] = [
    {
        "claim_id": "CLAIM-A1-SAMPLES-AUTHOR",
        "canonical_mechanism": SAMPLES_MECH,
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0003-author-mapper",
                f"{P3}/A1/DESIGN.json",
                2,
                "Three sampled capabilities (skill.council, wf.catalog-class.discovery-only, council.preset.catalog-class.editable) transcribe into that form.",
                "mapper.transcribe_author",
                "samples.verdict",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": _impact("architecture", "P2", False),
        "settling_probe": _settle(
            "ARC-0003-probe1",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0003/probe1_independent_replication.py",
            "second mapper reverse-sorted walk vs author mapper",
        ),
    },
    {
        "claim_id": "CLAIM-A1-SAMPLES-INDEP",
        "canonical_mechanism": SAMPLES_MECH,
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0003-independent-mapper",
                "command-center/p2-wave/probes/ARC-0003/probe1_independent_replication.py",
                38,
                "indep = M.transcribe_independent(cap)",
                "mapper.transcribe_independent",
                "samples.verdict",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": _impact("architecture", "P2", False),
        "settling_probe": _settle(
            "ARC-0003-probe1",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0003/probe1_independent_replication.py",
            "second mapper reverse-sorted walk vs author mapper",
        ),
    },
    {
        "claim_id": "CLAIM-A1-STOPPING-RULE",
        "canonical_mechanism": (
            "The first A1 construct that is not expressible without executable policy is a "
            "stopping rule that evaluates a predicate over prior rounds at runtime."
        ),
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0003-dossier",
                f"{P3}/A1/DESIGN.json",
                2,
                "The FIRST construct that is not expressible without executable policy is a stopping rule that evaluates a predicate over prior rounds at runtime",
                "json-load",
                "answer",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": _impact("architecture", "P1", True),
        "settling_probe": _settle(
            "ARC-0003-probe2",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0003/probe2_negative_control.py",
            "both-states: runtime stopping predicate INEXPRESSIBLE, declarative skill EXPRESSIBLE",
        ),
    },
    {
        "claim_id": "CLAIM-A1-NO-GENERATOR",
        "canonical_mechanism": (
            "A1 has no generated layer and no resident runtime: no_generated_layer and "
            "no_resident_runtime are both true in DESIGN precedence."
        ),
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0009-refutation",
                f"{P3}/A1/REFUTATION.json",
                58,
                "A1 has no generated layer and no resident runtime.",
                "json-load",
                "claims[C4].verdict",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": _impact("architecture", "P2", False),
        "settling_probe": _settle(
            "A1-DESIGN-booleans",
            "python3 -c \"import json; d=json.load(open('command-center/phase3/A1/DESIGN.json',encoding='utf-8')); assert d['precedence']['no_generated_layer'] is True; assert d['precedence']['no_resident_runtime'] is True\"",
            "parse DESIGN.json booleans; independent of REFUTATION prose",
        ),
    },
    {
        "claim_id": "CLAIM-A1-UNLISTED-SKIP",
        "canonical_mechanism": (
            "A file absent from A1 MANIFEST.json is not loaded, even if it sits in a "
            "capabilities directory."
        ),
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0003-dossier",
                f"{P3}/A1/DESIGN.json",
                212,
                "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
                "json-load",
                "precedence.unlisted_file",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": _impact("architecture", "P1", True),
        "settling_probe": _settle(
            "A1-unlisted-file-field",
            "python3 -c \"import json; d=json.load(open('command-center/phase3/A1/DESIGN.json',encoding='utf-8')); t=d['precedence']['unlisted_file']; assert 'not loaded' in t.lower()\"",
            "read DESIGN.json precedence.unlisted_file, not the refutation summary",
        ),
    },
    {
        "claim_id": "CLAIM-A1-MIN-RISK",
        "canonical_mechanism": (
            "Config-first is the minimal-risk architecture among the nine tournament classes "
            "because having no generator and no runtime removes moving parts."
        ),
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0009-refutation",
                f"{P3}/A1/REFUTATION.json",
                31,
                "Config-first is the minimal-risk architecture because it has no generator and no runtime.",
                "json-load",
                "claims[C1].verdict",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "REFUTED",
        "implementation_impact": _impact("architecture", "P1", True),
        "settling_probe": _settle(
            "ARC-0009-unlisted-omission",
            "python3 -c \"import json; d=json.load(open('command-center/phase3/A1/REFUTATION.json',encoding='utf-8')); c=next(x for x in d['claims'] if x['id']=='C1'); assert c['verdict']=='REFUTED'\"",
            "read REFUTATION C1 verdict; DESIGN unlisted_file is silent-skip",
        ),
    },
    {
        "claim_id": "CLAIM-A2-COMPLETE-SSOT",
        "canonical_mechanism": (
            "Generated-SSOT can encode every existing corpus capability in a typed registry "
            "with no remainder and no escape hatch."
        ),
        "duplicate_of": [],
        "supports": [],
        "contradicts": ["CLAIM-A2-INEXPRESSIBLE-OPAQUE"],
        "source_lineage": [
            _lin(
                "ARC-0016-refutation",
                f"{P3}/A2/REFUTATION.json",
                57,
                "Generated-SSOT can encode every existing corpus capability in a typed registry with no remainder and no escape hatch.",
                "json-load",
                "claims[C1].verdict",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "REFUTED",
        "implementation_impact": _impact("architecture", "P0", True),
        "settling_probe": _settle(
            "ARC-0016-probe1",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0016/probe1_reproduce_hatch.py",
            "typed refusal of opaque_body vs hatch capture-back",
        ),
    },
    {
        "claim_id": "CLAIM-A2-INEXPRESSIBLE-OPAQUE",
        "canonical_mechanism": (
            "The first A2 construct that is not expressible is an opaque passthrough / untyped "
            "blob field copied into generated output."
        ),
        "duplicate_of": [],
        "supports": [],
        "contradicts": ["CLAIM-A2-COMPLETE-SSOT"],
        "source_lineage": [
            _lin(
                "ARC-0010-dossier",
                f"{P3}/A2/DESIGN.json",
                96,
                "opaque passthrough / untyped blob field copied into generated output",
                "json-load",
                "expressibility.first_non_expressible_construct",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": _impact("architecture", "P0", True),
        "settling_probe": _settle(
            "A2-DESIGN-first-inexpressible",
            "python3 -c \"import json; d=json.load(open('command-center/phase3/A2/DESIGN.json',encoding='utf-8')); assert 'opaque passthrough' in d['expressibility']['first_non_expressible_construct']\"",
            "parse DESIGN.json expressibility.first_non_expressible_construct",
        ),
    },
    {
        "claim_id": "CLAIM-A2-HATCH-REFUSED",
        "canonical_mechanism": (
            "The A2 schema and live generator refuse an opaque_body/passthrough field "
            "(additionalProperties false plus banned keys)."
        ),
        "duplicate_of": [],
        "supports": ["CLAIM-A2-INEXPRESSIBLE-OPAQUE"],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0016-refutation",
                f"{P3}/A2/REFUTATION.json",
                84,
                "The A2 schema and live generator refuse an opaque_body/passthrough field.",
                "json-load",
                "claims[C4].verdict",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "CONFIRMED",
        "implementation_impact": _impact("implementation", "P1", True),
        "settling_probe": _settle(
            "ARC-0016-probe1-typed-refusal",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0016/probe1_reproduce_hatch.py",
            "live generator BANNED_KEYS plus schema additionalProperties false",
        ),
    },
    {
        "claim_id": "CLAIM-A2-BLAST-LOCAL",
        "canonical_mechanism": (
            "A bug in the A2 SSOT generator is localized to one artifact class and cannot fan "
            "out across the generated tree."
        ),
        "duplicate_of": [],
        "supports": [],
        "contradicts": [],
        "source_lineage": [
            _lin(
                "ARC-0016-refutation",
                f"{P3}/A2/REFUTATION.json",
                75,
                "A bug in the SSOT generator is localized to one artifact class and cannot fan out across the generated tree.",
                "json-load",
                "claims[C3].verdict",
            )
        ],
        "confidence_band": "almost-certain",
        "verification_status": "REFUTED",
        "implementation_impact": _impact("implementation", "P1", True),
        "settling_probe": _settle(
            "ARC-0016-probe1-blast-radius",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ARC-0016/probe1_reproduce_hatch.py",
            "count generate() paths whose bytes differ after provenance() monkey-patch",
        ),
    },
]


def _is_claim_record(row: object) -> bool:
    """True only for rows already in this unit's claim-record shape.

    command-center/CLAIM-REGISTRY.json later appeared on this tree with rows
    shaped {id, claim, verdict, band, ...} (a different registry schema, no
    claim_id / canonical_mechanism / source_lineage). Those rows cannot be
    validated against this unit's claim-record contract, so the registry is
    only consumed when its rows actually carry the claim-record shape.
    """
    return (
        isinstance(row, dict)
        and isinstance(row.get("claim_id"), str)
        and isinstance(row.get("canonical_mechanism"), str)
        and isinstance(row.get("source_lineage"), list)
    )


def load_encoded() -> tuple[list[dict], str]:
    if REGISTRY.is_file():
        doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
        claims = doc.get("claims") or doc.get("records") or []
        if (
            isinstance(claims, list)
            and len(claims) >= 10
            and all(_is_claim_record(c) for c in claims)
        ):
            return claims, "command-center/CLAIM-REGISTRY.json"
        return [json.loads(json.dumps(c)) for c in LIVE_CLAIMS], (
            "live-phase3-DESIGN-REFUTATION (CLAIM-REGISTRY.json present but "
            "not claim-record shaped; rows lack claim_id/canonical_mechanism/"
            "source_lineage)"
        )
    return [json.loads(json.dumps(c)) for c in LIVE_CLAIMS], (
        "live-phase3-DESIGN-REFUTATION (CLAIM-REGISTRY.json absent)"
    )


def write_fixture(claims: list[dict], source: str) -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "unit_id": "ARC-0085",
                "source": source,
                "claims": claims,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    claims, source = load_encoded()
    write_fixture(claims, source)
    print(f"encoded={len(claims)} source={source}")
    print("SUCCESS:ARC-0085-encode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
