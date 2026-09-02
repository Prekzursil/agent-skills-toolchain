#!/usr/bin/env python3
"""Probe 1: scan of checkpoint bytes (catalog evidence signal a).

Canary: planted fake credential is absent from the honest checkpoint.
Both-states: the same canary IS present in a naive dump; a non-secret
parameter DOES persist in the honest checkpoint.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools" / "agentspec"))

from agentspec.checkpoint import (  # noqa: E402
    load_checkpoint_bytes,
    plaintext_hits,
    write_checkpoint,
)
from harness import (  # noqa: E402
    CANARY,
    PLAIN_VALUE,
    SECRET_PARAM,
    honest_checkpoint_bytes,
    naive_checkpoint_bytes,
)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAILED:TST-0211-probe1 {msg}")


def main() -> int:
    honest = honest_checkpoint_bytes()
    naive = naive_checkpoint_bytes()

    with tempfile.TemporaryDirectory(prefix="tst0211-p1-") as tmp:
        path = Path(tmp) / "run.checkpoint.json"
        write_checkpoint(path, honest)
        on_disk = load_checkpoint_bytes(path)
        _need(on_disk == honest, "round-trip bytes drifted")
        _need(path.is_file() and path.stat().st_size > 0, "checkpoint file missing")

        honest_hits = plaintext_hits(on_disk, {SECRET_PARAM: CANARY})
        naive_hits = plaintext_hits(naive, {SECRET_PARAM: CANARY})

        _need(not honest_hits, f"canary present in honest checkpoint hits={honest_hits}")
        _need(CANARY.encode("utf-8") not in on_disk, "utf-8 canary in honest bytes")
        _need(PLAIN_VALUE.encode("utf-8") in on_disk, "non-secret param did not persist")
        _need(naive_hits == [SECRET_PARAM], f"naive control missed canary hits={naive_hits}")
        _need(CANARY.encode("utf-8") in naive, "both-states: naive dump lacks plaintext canary")

        doc = json.loads(on_disk.decode("utf-8"))
        secret_rec = doc["param_bindings"][SECRET_PARAM]
        plain_rec = doc["param_bindings"]["deploy_region"]
        _need(secret_rec.get("kind") == "secret_ref", "secret stored as something other than secret_ref")
        _need("value" not in secret_rec, "secret record still has a value field")
        _need(plain_rec.get("kind") == "plain", "non-secret kind")
        _need(plain_rec.get("value") == PLAIN_VALUE, "non-secret value not persisted")

    print(
        json.dumps(
            {
                "probe": "probe1-checkpoint-bytes",
                "unit_id": "TST-0211",
                "pass": True,
                "honest_bytes": len(honest),
                "naive_bytes": len(naive),
                "honest_canary_hits": honest_hits,
                "naive_canary_hits": naive_hits,
                "plain_persisted": True,
                "on_disk_sha16": __import__("hashlib").sha256(on_disk).hexdigest()[:16],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0211-probe1 checkpoint byte scan; canary absent; non-secret persisted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
