"""Shared cache-key inputs for IMP-0141 probes."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.cachekey import CacheInputs, KEY_FIELDS  # noqa: E402

BROKEN_PKG = b"BROKEN-pkg-v1-stale"
FIXED_PKG = b"FIXED-pkg-v2-after-patch"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def base_inputs() -> CacheInputs:
    return CacheInputs(
        workflow_id="wf.cache-demo",
        spec_version="1.4.1",
        unit_id="IMP-0141",
        resolved_prompt="derive the artifact cache key",
        param_values={"mode": "strict", "retries": 0},
        tool_policy=("Read", "Grep"),
        input_artifact_hashes={"pkg.core": sha(BROKEN_PKG)},
    )


def seven_mutations(base: CacheInputs) -> dict[str, CacheInputs]:
    """One-at-a-time change of each of the seven key inputs."""
    if tuple(KEY_FIELDS) != (
        "workflow_id",
        "spec_version",
        "unit_id",
        "resolved_prompt",
        "param_values",
        "tool_policy",
        "input_artifact_hashes",
    ):
        raise RuntimeError("KEY_FIELDS drifted from the catalog's seven inputs")
    return {
        "workflow_id": base.evolve(workflow_id=base.workflow_id + "-mut"),
        "spec_version": base.evolve(spec_version="1.4.2"),
        "unit_id": base.evolve(unit_id="IMP-0141-mut"),
        "resolved_prompt": base.evolve(resolved_prompt=base.resolved_prompt + "!"),
        "param_values": base.evolve(
            param_values={**dict(base.param_values), "retries": 1}
        ),
        "tool_policy": base.evolve(tool_policy=tuple(base.tool_policy) + ("Write",)),
        "input_artifact_hashes": base.evolve(
            input_artifact_hashes={"pkg.core": sha(FIXED_PKG)}
        ),
    }
