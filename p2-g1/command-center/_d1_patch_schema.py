"""SCRATCH: surgically re-generate the two vendor $defs blocks in receipt.schema.json.

``vendor_schema_sync.py`` deliberately ships ``--emit`` (print) and NOT a writer, because a
whole-file ``json.dumps`` would reformat ~500 hand-formatted lines and bury a two-field change.
This patcher replaces ONLY the ``vendor_id`` / ``vendor_id_canonical`` blocks, byte-for-byte in
the file's existing style.

BOTH-STATES CONTROL: run with ``--noop-check`` against the UNMODIFIED registry first. If the
patcher does not reproduce the current file byte-identically, its formatting is wrong and any
later diff it produces is noise. Only then run ``--apply``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(REPO / "platform" / "lib"))

import vendor_schema_sync as vss  # noqa: E402

SCHEMA = vss.RECEIPT_SCHEMA_PATH


def render_block(name: str, block: dict) -> str:
    """Serialize one $defs block at the file's indentation (4 spaces for the key)."""
    body = json.dumps({name: block}, indent=2, ensure_ascii=False)
    lines = body.splitlines()[1:-1]  # drop the wrapping { }
    return "\n".join("  " + ln for ln in lines)


def splice(text: str, name: str, rendered: str) -> str:
    """Replace the `"name": { ... }` region, located by brace depth, not by line number."""
    key = f'    "{name}": {{'
    start = text.index(key)
    depth = 0
    i = text.index("{", start)
    while True:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        elif ch == '"':  # skip string contents so a brace inside a description cannot fool us
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        i += 1
    return text[:start] + rendered + text[i + 1 :]


def build(text: str) -> str:
    out = text
    for name, block in vss.build_defs().items():
        rendered = render_block(name, block)
        # rendered starts with '    "name": {' already at 4-space indent
        out = splice(out, name, rendered)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--noop-check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ns = ap.parse_args(argv)
    original = SCHEMA.read_text(encoding="utf-8")
    patched = build(original)
    if ns.noop_check:
        same = patched == original
        print(f"byte_identical={same}")
        if not same:
            import difflib

            for ln in list(
                difflib.unified_diff(
                    original.splitlines(), patched.splitlines(), "live", "patched", n=1
                )
            )[:40]:
                print(ln[:200])
        print("SUCCESS:d1-patch-noop" if same else "FAILED:d1-patch-noop")
        return 0 if same else 1
    if ns.apply:
        json.loads(patched)  # never write a file that does not parse
        SCHEMA.write_text(patched, encoding="utf-8", newline="\n")
        problems = vss.check()
        for p in problems:
            print(f"DRIFT: {p}")
        print(
            "SUCCESS:d1-patch-apply"
            if not problems
            else "FAILED:d1-patch-apply drift remains"
        )
        return 0 if not problems else 1
    ap.error("choose --noop-check or --apply")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
