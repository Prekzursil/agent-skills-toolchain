"""SCRATCH: replace literal invisible characters in the test matrix with visible \\u escapes.

An invisible U+200B in source can be deleted by any later edit WITHOUT changing how the file
reads, and the test would keep passing while silently testing something weaker. The escape form
is the same string to Python and a visible token to a reviewer.
"""

from __future__ import annotations

import pathlib

TARGET = pathlib.Path(
    "C:/Users/Prekzursil/source/ast-integrate/platform/lib/test_vendor_identity.py"
)
MAP = {
    "\u200b": "\\u200b",
    "\u00ad": "\\u00ad",
    "\u200e": "\\u200e",
    "\ufeff": "\\ufeff",
    "\u00a0": "\\u00a0",
}


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    before = {ch: text.count(ch) for ch in MAP}
    for ch, esc in MAP.items():
        text = text.replace(ch, esc)
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    after = TARGET.read_text(encoding="utf-8")
    residual = {ch: after.count(ch) for ch in MAP}
    print(f"replaced={before}")
    print(f"residual={residual}")
    ok = sum(residual.values()) == 0 and sum(before.values()) > 0
    print("SUCCESS:d1-escape" if ok else "FAILED:d1-escape")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
