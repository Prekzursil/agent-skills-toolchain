#!/usr/bin/env python3
"""TST-0069 probe 1: apostrophe payload fails the inline Bash-tool wrap (control).

Reproduces python -c, grep, and heredoc. Each must exit non-zero with the
payload absent from stdout, and the lint must fire on the same command.
A detector that cannot go red is not a detector.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import transport as T  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0069-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0069-p1-") as tmp:
        matrix = T.run_matrix(Path(tmp))
    inline = matrix["inline"]
    missing = [name for name in T.INLINE_SHAPES if name not in inline]
    if missing:
        return fail(f"missing shapes {missing}")
    held = []
    for name in T.INLINE_SHAPES:
        row = inline[name]
        print(
            f"shape={name} rc={row['returncode']} stdout_empty={row['stdout_empty']} "
            f"payload_in_stdout={row['payload_in_stdout']} "
            f"control_holds={row['control_holds']} lint_hits={row['lint']['hits']}"
        )
        print(f"  wrapped={row['wrapped_script']!r}"[:240])
        if not row["control_holds"]:
            return fail(
                f"{name} control did not hold rc={row['returncode']} "
                f"stdout={row['stdout']!r} stderr={row['stderr'][:200]!r}"
            )
        if row["ok"]:
            return fail(f"{name} inline route unexpectedly succeeded")
        held.append(name)
    if not matrix["lint"]["bad_all_fired"]:
        return fail(f"lint silent on planted inline commands {matrix['lint']['bad']}")
    if matrix["select_transport"] != "file":
        return fail("select_transport did not choose file for apostrophe payload")
    print(
        json.dumps(
            {
                "payload_sha256": matrix["payload_sha256"],
                "shapes_held": held,
                "inline_control_holds": True,
                "lint_bad_fired": True,
                "select_transport": matrix["select_transport"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0069-probe1 apostrophe payload fails the inline route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
