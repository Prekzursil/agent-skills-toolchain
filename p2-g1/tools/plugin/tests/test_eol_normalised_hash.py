#!/usr/bin/env python3
"""IMP-0035 EOL-normalised hash tests (standalone, self-passing script).

Prints one PASS line per case plus a terminal SUCCESS marker. Both negative
controls are two-sided: the one-character change still diverges after
normalisation, and the naive CRLF rewrite corrupts the PNG that the primitive
leaves intact.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.eol_hash import (  # noqa: E402
    CONTENT_DIVERGED,
    IDENTICAL,
    IDENTICAL_MODULO_EOL,
    bytes_for_hash,
    classify_pair,
    looks_binary,
    sha256_normalised,
    sha256_raw,
)

PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


def case(name: str, ok: bool) -> None:
    if not ok:
        print(f"FAIL {name}")
        raise SystemExit(1)
    print(f"PASS {name}")


def main() -> int:
    lf = b"alpha\nbeta\ngamma\n"
    crlf = b"alpha\r\nbeta\r\ngamma\r\n"
    cr = b"alpha\rbeta\rgamma\r"

    case("crlf-lf-raw-differ", sha256_raw(lf) != sha256_raw(crlf))
    case("crlf-lf-normalised-match", sha256_normalised(lf) == sha256_normalised(crlf))
    case("crlf-lf-class-modulo-eol", classify_pair(lf, crlf) == IDENTICAL_MODULO_EOL)
    case("crlf-arithmetic-identity",
         len(crlf) - len(lf) == lf.count(b"\n") == crlf.count(b"\r\n") == 3)
    case("cr-only-raw-differ", sha256_raw(lf) != sha256_raw(cr))
    case("cr-only-normalised-match", sha256_normalised(lf) == sha256_normalised(cr))
    case("cr-only-class-modulo-eol", classify_pair(lf, cr) == IDENTICAL_MODULO_EOL)

    # EOL arithmetic without hashing (fixture authors use this identity).
    delta = len(crlf) - len(lf)
    case("arithmetic-identity", delta == 3 and lf.count(b"\n") == 3 and crlf.count(b"\r\n") == 3)

    # Identical bytes classify IDENTICAL; diverged content stays diverged.
    case("identical-class", classify_pair(lf, lf) == IDENTICAL)
    changed = b"alpha\nbetaX\ngamma\n"
    case("one-char-change-diverges", classify_pair(lf, changed) == CONTENT_DIVERGED)
    changed_crlf = b"alpha\r\nbetaX\r\ngamma\r\n"
    case("one-char-change-crlf-diverges", classify_pair(lf, changed_crlf) == CONTENT_DIVERGED)

    # Binary detection precedes normalisation (both-states control).
    case("png-looks-binary", looks_binary(PNG_1X1) is True)
    case("png-raw-eq-policy", sha256_raw(PNG_1X1) == sha256_normalised(PNG_1X1))
    case("png-class-identical", classify_pair(PNG_1X1, PNG_1X1) == IDENTICAL)
    naive = PNG_1X1.replace(b"\r\n", b"\n")
    case("png-naive-rewrite-corrupts", sha256_raw(PNG_1X1) != sha256_raw(naive))
    case("png-naive-not-normalised", sha256_normalised(PNG_1X1) != sha256_normalised(naive))

    # Mixed line endings still fold to one normal form.
    mixed = b"alpha\r\nbeta\ngamma\r"
    case("mixed-folds-to-lf", sha256_normalised(mixed) == sha256_normalised(lf))

    print("SUCCESS:IMP-0035 tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
