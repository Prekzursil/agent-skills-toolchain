#!/usr/bin/env python3
"""Probe 1: [Read, Grep] Write is a typed runtime denial; the file is absent.

Two independent signals:
  (a) ToolPermissionError with code tool-permission-denied
  (b) filesystem check that the target path still does not exist
Negative control: DocumentedOnlySession performs the same write (the defect).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.lib.workspace_permissions import (  # noqa: E402
    DocumentedOnlySession,
    PermissionSession,
    ToolPermissionError,
    documented_only_argv,
    enforcement_argv,
    evaluate,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0222-probe1 {msg}")
    return 1


def main() -> int:
    with TemporaryDirectory(prefix="tst0222-p1-") as tmp:
        root = Path(tmp)
        target_rel = "denied-write.txt"
        target = root / target_rel
        payload = "SHOULD-NOT-LAND\n"
        sess = PermissionSession(["Read", "Grep"], root)
        if evaluate(sess.declared, "Write") != "deny":
            return fail("evaluate() did not deny Write for [Read, Grep]")
        if evaluate(sess.declared, "Read") != "grant":
            return fail("evaluate() denied Read which is declared")
        if target.exists():
            return fail("target existed before invoke")

        err: ToolPermissionError | None = None
        try:
            sess.invoke("Write", path=target_rel, contents=payload)
        except ToolPermissionError as exc:
            err = exc
        if err is None:
            return fail("Write did not raise a typed ToolPermissionError")
        if err.code != "tool-permission-denied":
            return fail(f"error code {err.code!r} is not tool-permission-denied")
        if err.tool != "Write":
            return fail(f"error.tool {err.tool!r} is not Write")
        if "Read" not in err.declared or "Grep" not in err.declared:
            return fail(f"error.declared drifted: {sorted(err.declared)}")
        if "tool-permission-denied" not in str(err):
            return fail("error text omitted the typed code")
        if target.exists():
            return fail("filesystem: denied Write created the target file")
        if sess.spawn_count != 0:
            return fail("denied Write spawned a process")

        readable = root / "readable.txt"
        readable.write_text("probe1-read-ok\n", encoding="utf-8")
        got = sess.invoke("Read", path="readable.txt")
        if got.data != "probe1-read-ok\n":
            return fail(f"declared Read failed: {got!r}")
        hits = sess.invoke("Grep", path="readable.txt", pattern="probe1-read")
        if not hits.data["hits"]:
            return fail("declared Grep failed to see its own fixture")

        decoy_rel = "documented-only.txt"
        decoy_path = root / decoy_rel
        decoy = DocumentedOnlySession(["Read", "Grep"], root)
        decoy.invoke("Write", path=decoy_rel, contents=payload)
        if not decoy_path.is_file():
            return fail("documented-only mutant did not write; detector would be vacuous")
        if decoy_path.read_text(encoding="utf-8") != payload:
            return fail("documented-only mutant wrote unexpected bytes")
        if decoy.argv == sess.argv:
            return fail("enforced argv identical to documented-only argv")
        if "--danger-full-access" not in decoy.argv:
            return fail("documented-only argv missing danger-full-access")
        if "--allowedTools" in decoy.argv:
            return fail("documented-only argv unexpectedly carries allowedTools")
        if "--allowedTools" not in sess.argv:
            return fail("enforced argv omitted allowedTools")

        try:
            sess.invoke("Write", path=target_rel, contents=payload)
        except ToolPermissionError:
            pass
        else:
            return fail("second denied Write succeeded")
        if target.exists():
            return fail("second denied Write created the file")

        payload_out = {
            "probe": "probe1-denied-write",
            "unit_id": "TST-0222",
            "pass": True,
            "declared": sorted(sess.declared),
            "denied_tool": "Write",
            "typed_error": {
                "name": type(err).__name__,
                "code": err.code,
                "tool": err.tool,
                "declared": sorted(err.declared),
            },
            "target_existed_after": target.exists(),
            "spawn_count": sess.spawn_count,
            "read_granted": True,
            "grep_granted": True,
            "documented_only_wrote": True,
            "argv_enforced": enforcement_argv(["Read", "Grep"]),
            "argv_documented_only": documented_only_argv(["Read", "Grep"]),
            "argv_differ": True,
            "evaluation": "deny",
        }
        print(json.dumps(payload_out, sort_keys=True))
        print(
            "typed_error=tool-permission-denied target_exists=False "
            "documented_only_wrote=True argv_differ=True"
        )
        print("SUCCESS:TST-0222-probe1 runtime Write denial; filesystem unchanged")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
