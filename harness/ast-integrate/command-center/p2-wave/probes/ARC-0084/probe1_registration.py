"""Probe 1: on-disk unregistered artifact fails; registering it from disk passes.

Also proves the predicate does not trust the writer's in-memory present=true.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from consumer import run_call_site  # noqa: E402
from fixturelib import install, manifest_doc, registration_row  # noqa: E402
from predicate import evaluate, trust_writer  # noqa: E402
from validate_schema import envelope_errors, load_contract  # noqa: E402

REPO = HERE.parents[3]
CONTRACT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0084.json"


def _clean(env: dict) -> dict:
    return {k: v for k, v in env.items() if not k.startswith("_")}


def main() -> int:
    if not CONTRACT.is_file():
        print("FAILED:ARC-0084-probe1 contract missing")
        return 1
    contract = load_contract()
    text = CONTRACT.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0084" not in text:
        print("FAILED:ARC-0084-probe1 sentinel-absent")
        return 1
    if str(contract.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:ARC-0084-probe1 self-declared {contract.get('state')}")
        return 1

    floor = int(contract["size_floors"]["receipt"])
    size = max(2048, floor)

    with tempfile.TemporaryDirectory(prefix="arc0084-p1-") as tmp:
        root = Path(tmp)
        env = install(root, register=False, size=size)
        envelope = _clean(env)
        writer_ok = trust_writer(envelope)
        bad = evaluate(root, envelope)
        print(
            f"unregistered writer_trust={writer_ok} predicate={bad.code} "
            f"failed={bad.failed_checks}"
        )
        if not writer_ok:
            print("FAILED:ARC-0084-probe1 writer-trust control did not accept present=true")
            return 1
        if bad.ok or bad.code != "UNREGISTERED":
            print(f"FAILED:ARC-0084-probe1 expected UNREGISTERED got {bad.as_dict()}")
            return 1
        if "registered_row" not in bad.failed_checks:
            print("FAILED:ARC-0084-probe1 did not fail on registered_row")
            return 1

        row = registration_row(
            rel=envelope["path"],
            sha=envelope["content_hash"]["hex"],
            size=envelope["byte_size"],
            producing_unit=envelope["producing_unit"],
            present=True,
            manifest_path="ARTIFACT-MANIFEST.json",
        )
        (root / "ARTIFACT-MANIFEST.json").write_text(
            json.dumps(manifest_doc([row]), indent=2) + "\n", encoding="utf-8"
        )
        good = evaluate(root, envelope)
        print(f"registered predicate={good.code} ok={good.ok}")
        if not good.ok:
            print(f"FAILED:ARC-0084-probe1 registered state failed {good.as_dict()}")
            return 1

        schema_errs = envelope_errors(envelope, contract)
        if schema_errs:
            print(f"FAILED:ARC-0084-probe1 envelope schema {schema_errs[:3]}")
            return 1

    with tempfile.TemporaryDirectory(prefix="arc0084-consumer-") as tmp:
        call = run_call_site(Path(tmp))
        print(f"consumer_ok={call['ok']} predicate={call['predicate']['code']}")
        if not call["ok"]:
            print(f"FAILED:ARC-0084-probe1 consumer {call}")
            return 1

    print("SUCCESS:ARC-0084-probe1 registration assertion both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
