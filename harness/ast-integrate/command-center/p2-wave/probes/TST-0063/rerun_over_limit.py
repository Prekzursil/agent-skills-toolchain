#!/usr/bin/env python3
"""Second-shell helper: over-limit marshaller must switch to --prompt-file."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import cmdline_guard as cg  # noqa: E402

VENDOR = [sys.executable, "-B", str(HERE / "vendor_cli.py")]


def main() -> int:
    payload = cg.pad_payload_for_inline_chars(
        VENDOR, (), cg.WINDOWS_CREATEPROCESS_CHAR_CEILING
    )
    with tempfile.TemporaryDirectory(prefix="tst0063-shell-") as tmp:
        spawn = cg.spawn_guarded(VENDOR, payload, workdir=Path(tmp))
    print(spawn.marshal.transport)
    print(int(spawn.marshal.switched))
    print(spawn.exit_code)
    if spawn.marshal.transport != "prompt-file" or spawn.exit_code != 0:
        print("FAILED:TST-0063-shell over-limit did not switch", file=sys.stderr)
        return 1
    print("SUCCESS:TST-0063-shell switched to prompt-file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
