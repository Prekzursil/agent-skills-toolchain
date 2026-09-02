"""Probe 2: mutate one byte of a registered artifact; digest check must fire.

Also runs the independent contract reviewer against the frozen draft.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixturelib import install  # noqa: E402
from predicate import evaluate  # noqa: E402
from reviewer import review  # noqa: E402
from validate_schema import load_contract  # noqa: E402

REPO = HERE.parents[3]
CONTRACT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0084.json"


def _clean(env: dict) -> dict:
    return {k: v for k, v in env.items() if not k.startswith("_")}


def main() -> int:
    if not CONTRACT.is_file():
        print("FAILED:ARC-0084-probe2 contract missing")
        return 1
    contract = load_contract()
    floor = int(contract["size_floors"]["receipt"])
    size = max(2048, floor)

    with tempfile.TemporaryDirectory(prefix="arc0084-p2-") as tmp:
        root = Path(tmp)
        env = install(root, register=True, size=size)
        envelope = _clean(env)
        control = evaluate(root, envelope)
        print(f"control_ok={control.ok} code={control.code}")
        if not control.ok:
            print(f"FAILED:ARC-0084-probe2 control {control.as_dict()}")
            return 1

        payload = root / envelope["path"]
        original = payload.read_bytes()
        mutated = bytearray(original)
        mutated[len(mutated) // 2] ^= 0x01
        payload.write_bytes(bytes(mutated))
        mutant = evaluate(root, envelope)
        print(
            f"mutant code={mutant.code} ok={mutant.ok} failed={mutant.failed_checks}"
        )
        if mutant.ok:
            print("FAILED:ARC-0084-probe2 one-byte mutation stayed green")
            return 1
        if "digest_envelope" not in mutant.failed_checks:
            print("FAILED:ARC-0084-probe2 envelope digest did not fire")
            return 1
        if "digest_manifest" not in mutant.failed_checks:
            print("FAILED:ARC-0084-probe2 manifest digest did not fire")
            return 1
        if mutant.code != "DIGEST_MISMATCH":
            print(f"FAILED:ARC-0084-probe2 expected DIGEST_MISMATCH got {mutant.code}")
            return 1
        if "UNREGISTERED" == mutant.code or "registered_row" in mutant.failed_checks:
            print("FAILED:ARC-0084-probe2 mutation misclassified as unregistered")
            return 1

        payload.write_bytes(original)
        restored = evaluate(root, envelope)
        print(f"restored_ok={restored.ok} code={restored.code}")
        if not restored.ok:
            print(f"FAILED:ARC-0084-probe2 restore {restored.as_dict()}")
            return 1

    rec = review()
    print(
        f"reviewer verdict={rec.get('verdict')} failed={rec.get('failed')} "
        f"one_byte_rejected={rec.get('one_byte_receipt_rejected')}"
    )
    if rec.get("verdict") != "PASS":
        print("FAILED:ARC-0084-probe2 independent reviewer")
        return 1

    print("SUCCESS:ARC-0084-probe2 digest control and independent review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
