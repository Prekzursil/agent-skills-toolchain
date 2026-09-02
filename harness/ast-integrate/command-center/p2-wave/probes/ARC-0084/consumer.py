"""Consumer call site: build an envelope and run the frozen schema + predicate."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fixturelib import install
from predicate import evaluate
from validate_schema import envelope_errors, load_contract


def run_call_site(root: Path) -> dict[str, Any]:
    """One real call against the frozen draft: fixture tree, schema, predicate."""
    contract = load_contract()
    env = install(root, register=True, size=max(2048, int(contract["size_floors"]["receipt"])))
    schema_errs = envelope_errors( {k: v for k, v in env.items() if not k.startswith("_")}, contract)
    verdict = evaluate(root, {k: v for k, v in env.items() if not k.startswith("_")})
    return {
        "consumer": "command-center/p2-wave/probes/ARC-0084/consumer.py",
        "schema_errors": schema_errs,
        "predicate": verdict.as_dict(),
        "ok": not schema_errs and verdict.ok,
        "draft": "command-center/phase4/contracts/ARC-0084.json",
    }
