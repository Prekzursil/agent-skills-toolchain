#!/usr/bin/env python3
"""Probe 2: detector control — removing a hook file must drop the live count.

Also pins the regression seed: a deny-unknown silent client loads ZERO hooks
when `$schema` is present, while this client does not. A declared-only counter
that cannot see a missing file is the vacuous mutant this probe must reject.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from hooks_client import LoadError, load  # noqa: E402
from scenario import expected_hook_ids, seed_tree  # noqa: E402

ART = REPO / "command-center/receipts/TST-0181.json"
DROP_ID = "post-tool"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0181-probe2 {msg}")
    return 1


def main() -> int:
    want = expected_hook_ids()
    with tempfile.TemporaryDirectory(prefix="tst0181-p2-") as tmp:
        base = Path(tmp)
        man = seed_tree(base / "plugin", schema=True)
        healthy = load(man)
        if healthy.errors or healthy.hook_ids != want:
            return _fail(f"healthy {healthy.as_dict()}")
        baseline = healthy.hook_count
        silent_schema = load(man, mode="deny-unknown-silent")

        dropped = base / "plugin" / "hooks" / f"{DROP_ID}.py"
        saved_bytes = dropped.read_bytes()
        dropped.unlink()
        broken = load(man)
        declared_only = load(man, mode="count-declared-only")

        dropped.write_bytes(saved_bytes)
        restored = load(man)

        unknown_man = seed_tree(
            base / "unknown", schema=True, extra={"notARealField": True}
        )
        unknown_err = None
        try:
            load(unknown_man)
        except LoadError as exc:
            unknown_err = str(exc)

        payload = {
            "probe": "probe2-detector-drop",
            "baseline_count": baseline,
            "after_unlink_count": broken.hook_count,
            "after_unlink_errors": broken.errors,
            "declared_only_count": declared_only.hook_count,
            "deny_unknown_silent_with_schema": silent_schema.as_dict(),
            "restored_count": restored.hook_count,
            "unknown_field_error": unknown_err,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))

        if broken.hook_count >= baseline:
            return _fail(
                f"count-did-not-drop baseline={baseline} after={broken.hook_count}"
            )
        if broken.hook_count != baseline - 1:
            return _fail(
                f"count-drop-not-one baseline={baseline} after={broken.hook_count}"
            )
        if DROP_ID in broken.hook_ids:
            return _fail(f"removed hook still loaded {broken.hook_ids}")
        if not broken.errors:
            return _fail("missing-file produced silent empty/partial load")
        named = any(DROP_ID in e and "missing file" in e for e in broken.errors)
        if not named:
            return _fail(f"errors did not name {DROP_ID}: {broken.errors}")
        if broken.hook_count == 0 and not broken.errors:
            return _fail("silent-zero on missing file")

        if declared_only.hook_count != baseline:
            return _fail("declared-only mutant did not stay at baseline")
        if declared_only.hook_count == broken.hook_count:
            return _fail("live count indistinguishable from declared-only mutant")

        if silent_schema.hook_count != 0:
            return _fail(
                f"deny-unknown-silent should be zero, got {silent_schema.hook_count}"
            )
        if silent_schema.errors:
            return _fail("deny-unknown-silent was loud; the Codex seed is silent")
        if silent_schema.hook_count == healthy.hook_count:
            return _fail("silent Codex mutant matched the healthy count")

        if restored.hook_count != baseline or restored.errors:
            return _fail(f"restore did not recover {restored.as_dict()}")

        if unknown_err is None:
            return _fail("unknown top-level field was accepted")
        if "notARealField" not in unknown_err:
            return _fail(f"unknown-field error omitted the name: {unknown_err}")

        print(
            "detector "
            f"baseline={baseline} after_unlink={broken.hook_count} "
            f"declared_only={declared_only.hook_count} "
            f"codex_silent_zero={silent_schema.hook_count} "
            f"loud_missing=true"
        )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0181" not in text:
            return _fail("receipt-sentinel-absent")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"receipt-self-declared {doc.get('state')}")
        if not doc.get("detector_count_drops_when_hook_file_removed"):
            return _fail("receipt-flag-detector-absent")

    print("SUCCESS:TST-0181-probe2 count drops on missing hook; $schema is not silent-zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
