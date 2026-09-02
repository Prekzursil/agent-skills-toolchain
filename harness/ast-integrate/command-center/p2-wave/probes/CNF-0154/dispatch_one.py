"""Run one blinded P0 claim through the Codex MCP rail."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from blinding import assemble, attestation_of  # noqa: E402
from claims import claim_by_id  # noqa: E402
from rail import dispatch  # noqa: E402


def write_prompt(assembled: dict[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    envelope = {
        "payload": assembled["payload"],
        "attestation": assembled["attestation"],
    }
    dest.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    recomputed = attestation_of(assembled["payload"])
    if recomputed != assembled["attestation"]:
        raise RuntimeError("attestation not recomputable from payload")
    return dest


def run_claim(
    claim_id: str,
    work: Path,
    *,
    backend: str = "confirm",
    extra_candidates: dict[str, str] | None = None,
    exclusion_enabled: bool = True,
) -> dict[str, Any]:
    claim = claim_by_id(claim_id)
    assembled = assemble(
        claim,
        extra_candidates=extra_candidates,
        exclusion_enabled=exclusion_enabled,
    )
    slot = work / claim_id
    prompt = write_prompt(assembled, slot / "prompt.json")
    out = slot / "output-last-message.json"
    result = dispatch(
        prompt_file=prompt,
        output_last_message=out,
        backend=backend,
        claim_id=claim_id,
    )
    result["blinding_attestation"] = assembled["attestation"]
    result["excluded"] = assembled["excluded"]
    result["payload_keys"] = sorted(assembled["payload"].keys())
    result["source_file_rels"] = sorted(assembled["payload"]["source_files"].keys())
    result["test_file_rels"] = sorted(assembled["payload"]["test_files"].keys())
    return result
