#!/bin/bash
# build_shellcode.sh — One-shot helper: compile C to position-independent .o,
# verify no relocations, extract bytes + offsets.
#
# Usage:  ./build_shellcode.sh <source.c>
# Output: prints the Python literal block + offsets to stdout.
#         Also exits non-zero if relocations are detected.

set -e

if [ $# -ne 1 ]; then
    echo "usage: $0 <source.c>" >&2
    exit 1
fi

SRC="$1"
OBJ="${SRC%.c}.o"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# These flags are critical:
#   -fno-pic              : no GOT references
#   -fno-stack-protector  : no __stack_chk_fail
#   -fno-asynchronous-unwind-tables : no .eh_frame
#   -fno-plt              : no PLT entries
#   -fcf-protection=none  : no endbr64 instructions
#   -fno-tree-loop-distribute-patterns : prevents gcc converting init loops to memset
#   -fno-builtin          : no implicit memset/memcpy/etc.
gcc -O2 \
    -fno-stack-protector \
    -fno-asynchronous-unwind-tables \
    -fno-plt \
    -fcf-protection=none \
    -fno-pic \
    -fno-tree-loop-distribute-patterns \
    -fno-builtin \
    -c "$SRC" -o "$OBJ"

# Check for relocations — empty output means we're good
RELOC_OUT=$(objdump -r "$OBJ" | grep -E "memset|memcpy|memcmp|R_X86_64_GOTPCRELX|R_X86_64_PLT32" || true)
if [ -n "$RELOC_OUT" ]; then
    echo "ERROR: relocations detected — shellcode would not work standalone:" >&2
    echo "$RELOC_OUT" >&2
    echo "" >&2
    echo "Hints:" >&2
    echo "  - Rewrite init loops manually (don't use bulk = 0 patterns)" >&2
    echo "  - Avoid printf, malloc, math.h" >&2
    echo "  - Re-check that -fno-builtin and -fno-tree-loop-distribute-patterns are present" >&2
    exit 2
fi

# Extract
python3 "$SCRIPT_DIR/extract_shellcode.py" "$OBJ"
