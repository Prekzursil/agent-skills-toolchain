"""Follow-up: move the falsify loop above dump_json so
claude_operational is bound when the payload dict is built.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0084/probe2_ast_adjudication.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a84p2b.pyc")

MARK = "    # Falsify treating a relative glob or a payload/docstring mention as"
DUMP = "    C.dump_json("


def main() -> int:
    lines = P.read_text(encoding="utf-8").splitlines(keepends=True)
    text = "".join(lines)
    start = text.find(MARK)
    assert start >= 0, "falsify block not found"
    # Block ends right before the artifact-existence check.
    end_anchor = '    if not ART.is_file() or ART.stat().st_size <= 0:'
    end = text.find(end_anchor, start)
    assert end > start, "end anchor not found"
    block = text[start:end]
    # Remove from old position.
    text = text[:start] + text[end:]
    # Insert before the dump call.
    d = text.find(DUMP)
    assert d > 0, "dump not found"
    text = text[:d] + block + "\n" + text[d:]
    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("REORDERED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
