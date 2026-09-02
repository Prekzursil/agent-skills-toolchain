"""Planted mutant corpus for the WFA-0097 detection envelope.

Pairs are labelled with semantic_duplicate (ground truth) and a shape id.
Settling experiments are named on shapes the combined stack is expected to miss.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from typing import Any

SEED_IR = {
    "stages": ["ingest", "score", "report"],
    "roles": ["differ-engineer"],
    "gates": ["planted-mutant-before-verdict"],
    "tools": ["token-jaccard"],
    "stop_rules": ["stop-after-matrix"],
}

SEED_DOES = (
    "scan candidate workflows for lexical near duplicates using token "
    "jaccard over name does and mechanisms"
)

REWRITE_DOES = (
    "inspect record pipelines word close copies term overlap title "
    "purpose devices"
)

SETTLING = {
    "behavioral-isomorph-divergent-ir": (
        "Execute both records against a shared fixture suite and compare "
        "canonical traces; combined lexical/embedding/structural detectors "
        "stay silent when IR labels and vocabulary both diverge. Command: "
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/"
        "WFA-0097/settle.py --class behavioral-isomorph-divergent-ir"
    ),
    "cross-language-divergent-ir": (
        "Round-trip translate both records into a pivot language (or apply "
        "a multilingual encoder) then re-run lexical+embedding; this stack "
        "has no translation step. Command: PYTHONDONTWRITEBYTECODE=1 "
        "python3 -B command-center/p2-wave/probes/WFA-0097/settle.py "
        "--class cross-language-divergent-ir"
    ),
    "ciphertext-opaque-payload": (
        "Base64-decode (or otherwise invert) the opaque payload, rebuild "
        "the plaintext record, then re-run lexical-jaccard against the "
        "seed. Command: PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0097/settle.py "
        "--class ciphertext-opaque-payload"
    ),
}


def _rec(
    rid: str,
    name: str,
    does: str,
    mechanisms: list[str],
    ir: dict[str, list[str]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": rid,
        "name": name,
        "does": does,
        "mechanisms": list(mechanisms),
        "ir": deepcopy(ir if ir is not None else SEED_IR),
    }
    row.update(extra)
    return row


def records() -> dict[str, dict[str, Any]]:
    payload = base64.b64encode(SEED_DOES.encode("utf-8")).decode("ascii")
    return {
        "seed": _rec(
            "wf-seed",
            "alpha-workflow",
            SEED_DOES,
            ["token-jaccard"],
        ),
        "exact-rename": _rec(
            "wf-exact-rename",
            "alpha-workflow-renamed",
            SEED_DOES,
            ["token-jaccard"],
        ),
        "one-parameter-fork": _rec(
            "wf-one-parameter-fork",
            "alpha-workflow",
            SEED_DOES + " with similarity threshold high",
            ["token-jaccard", "threshold-high"],
            ir={
                **SEED_IR,
                "tools": ["token-jaccard", "threshold-gate"],
            },
        ),
        "reworded-paraphrase": _rec(
            "wf-reworded-paraphrase",
            "alpha-workflow",
            "scan candidate workflows for lexical near-duplicates using "
            "token jaccard over name, does and mechanisms",
            ["token-jaccard"],
        ),
        "full-rewrite": _rec(
            "wf-full-rewrite",
            "beta-rewrite",
            REWRITE_DOES,
            ["term-overlap"],
        ),
        "structural-clone": _rec(
            "wf-structural-clone",
            "rust-plugin-host",
            "compile rust crates for the marketplace plugin host linker",
            ["rustc-linker"],
        ),
        "decoy-distinct": _rec(
            "wf-decoy-distinct",
            "mermaid-render",
            "render mermaid diagrams from architecture notes for the council briefing",
            ["mermaid-cli"],
            ir={
                "stages": ["parse", "draw"],
                "roles": ["docs-engineer"],
                "gates": ["diagram-lint"],
                "tools": ["mermaid-cli"],
                "stop_rules": ["stop-on-syntax-error"],
            },
        ),
        "decoy-distinct-2": _rec(
            "wf-decoy-distinct-2",
            "yaml-frontmatter",
            "format yaml frontmatter on harvested skill files",
            ["yaml-fmt"],
            ir={
                "stages": ["harvest", "format"],
                "roles": ["librarian"],
                "gates": ["schema-present"],
                "tools": ["yaml-fmt"],
                "stop_rules": ["stop-on-missing-key"],
            },
        ),
        "behavioral-isomorph-divergent-ir": _rec(
            "wf-isomorph",
            "clone-hunt-orchestrator",
            "orchestrate clone hunt via bag across caption intent apparatus",
            ["bag-of-terms"],
            ir={
                "stages": ["collect", "evaluate", "emit"],
                "roles": ["operator"],
                "gates": ["none-listed"],
                "tools": ["bag-of-terms"],
                "stop_rules": ["halt-on-empty"],
            },
        ),
        "cross-language-divergent-ir": _rec(
            "wf-es",
            "flujo-alfa",
            "escanear flujos candidatos en busca de duplicados lexicos "
            "mediante jaccard de tokens sobre nombre proposito y mecanismos",
            ["jaccard-de-tokens"],
            ir={
                "stages": ["ingestar", "puntuar", "reportar"],
                "roles": ["ingeniero-differ"],
                "gates": ["mutante-plantado-antes-del-veredicto"],
                "tools": ["jaccard-de-tokens"],
                "stop_rules": ["parar-despues-de-la-matriz"],
            },
        ),
        "ciphertext-opaque-payload": _rec(
            "wf-cipher",
            "opaque-blob",
            "opaque payload stored as ciphertext",
            ["none"],
            ir={
                "stages": ["store"],
                "roles": ["vault"],
                "gates": ["sealed"],
                "tools": ["base64"],
                "stop_rules": ["do-not-decode"],
            },
            encoding="base64",
            payload_b64=payload,
        ),
    }


def pairs() -> list[dict[str, Any]]:
    """Each row: shape, left id, right id, semantic_duplicate, settling_experiment|None."""
    return [
        {
            "shape": "exact-rename",
            "left": "seed",
            "right": "exact-rename",
            "semantic_duplicate": True,
            "settling_experiment": None,
        },
        {
            "shape": "one-parameter-fork",
            "left": "seed",
            "right": "one-parameter-fork",
            "semantic_duplicate": True,
            "settling_experiment": None,
        },
        {
            "shape": "reworded-paraphrase",
            "left": "seed",
            "right": "reworded-paraphrase",
            "semantic_duplicate": True,
            "settling_experiment": None,
        },
        {
            "shape": "full-rewrite",
            "left": "seed",
            "right": "full-rewrite",
            "semantic_duplicate": True,
            "settling_experiment": None,
        },
        {
            "shape": "structural-clone",
            "left": "seed",
            "right": "structural-clone",
            "semantic_duplicate": True,
            "settling_experiment": None,
        },
        {
            "shape": "decoy-distinct",
            "left": "seed",
            "right": "decoy-distinct",
            "semantic_duplicate": False,
            "settling_experiment": None,
        },
        {
            "shape": "decoy-vs-decoy",
            "left": "decoy-distinct",
            "right": "decoy-distinct-2",
            "semantic_duplicate": False,
            "settling_experiment": None,
        },
        {
            "shape": "behavioral-isomorph-divergent-ir",
            "left": "seed",
            "right": "behavioral-isomorph-divergent-ir",
            "semantic_duplicate": True,
            "settling_experiment": SETTLING["behavioral-isomorph-divergent-ir"],
        },
        {
            "shape": "cross-language-divergent-ir",
            "left": "seed",
            "right": "cross-language-divergent-ir",
            "semantic_duplicate": True,
            "settling_experiment": SETTLING["cross-language-divergent-ir"],
        },
        {
            "shape": "ciphertext-opaque-payload",
            "left": "seed",
            "right": "ciphertext-opaque-payload",
            "semantic_duplicate": True,
            "settling_experiment": SETTLING["ciphertext-opaque-payload"],
        },
    ]
