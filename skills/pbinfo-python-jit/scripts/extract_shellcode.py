#!/usr/bin/env python3
"""
extract_shellcode.py — Parse ELF64 .o file and emit Python-friendly hex literal + symbol offsets.

Usage:
    python3 extract_shellcode.py <path/to/lib.o>

Output (to stdout) is ready to paste into a Python file:
  _TEXT_HEX = (
      "4d31..."
      ...
  )
  _OFF_FUNCNAME = 0
  _OFF_OTHER    = 64
  TEXT_LEN = 868

The script also warns if any relocations are present in .text — those indicate
external symbol calls (memset, etc.) that would crash standalone shellcode.
"""

import struct
import sys
import textwrap


def parse_elf64(data):
    """Return dict with .text bytes, function offsets, and any relocations."""
    if data[:4] != b"\x7fELF" or data[4] != 2:
        raise ValueError("Not an ELF64 file")

    e_shoff = struct.unpack("<Q", data[0x28:0x30])[0]
    e_shentsize = struct.unpack("<H", data[0x3A:0x3C])[0]
    e_shnum = struct.unpack("<H", data[0x3C:0x3E])[0]
    e_shstrndx = struct.unpack("<H", data[0x3E:0x40])[0]

    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh = struct.unpack("<IIQQQQIIQQ", data[off : off + 64])
        sections.append(
            {
                "name_off": sh[0],
                "type": sh[1],
                "flags": sh[2],
                "addr": sh[3],
                "offset": sh[4],
                "size": sh[5],
                "link": sh[6],
                "info": sh[7],
                "addralign": sh[8],
                "entsize": sh[9],
            }
        )

    shstr_off = sections[e_shstrndx]["offset"]

    def get_shname(off):
        end = data.index(b"\x00", shstr_off + off)
        return data[shstr_off + off : end].decode()

    text_idx = sym_idx = str_idx = None
    rela_text_idx = None
    for i, s in enumerate(sections):
        n = get_shname(s["name_off"])
        if n == ".text":
            text_idx = i
        elif n == ".symtab":
            sym_idx = i
        elif n == ".strtab":
            str_idx = i
        elif n in (".rela.text", ".rel.text"):
            rela_text_idx = i

    if text_idx is None:
        raise ValueError(".text section not found")
    if sym_idx is None or str_idx is None:
        raise ValueError("symtab/strtab not found")

    text_bytes = data[
        sections[text_idx]["offset"] : sections[text_idx]["offset"]
        + sections[text_idx]["size"]
    ]

    # Symbols
    sym_off = sections[sym_idx]["offset"]
    sym_size = sections[sym_idx]["size"]
    strt_off = sections[str_idx]["offset"]

    def get_str(off):
        end = data.index(b"\x00", strt_off + off)
        return data[strt_off + off : end].decode()

    functions = []
    for i in range(0, sym_size, 24):
        s = struct.unpack("<IBBHQQ", data[sym_off + i : sym_off + i + 24])
        name = get_str(s[0])
        info = s[1]
        sym_type = info & 0xF  # STT_FUNC = 2
        if name and s[5] > 0 and sym_type == 2:
            functions.append({"name": name, "offset": s[4], "size": s[5]})

    functions.sort(key=lambda f: f["offset"])

    # Relocations in .text (would indicate external calls)
    relocations = []
    if rela_text_idx is not None:
        rs = sections[rela_text_idx]
        ent = rs["entsize"] or 24  # RELA = 24 bytes, REL = 16 bytes
        for off in range(rs["offset"], rs["offset"] + rs["size"], ent):
            if ent == 24:
                r_off, r_info, _r_addend = struct.unpack("<QQq", data[off : off + 24])
            else:
                r_off, r_info = struct.unpack("<QQ", data[off : off + 16])
                _r_addend = 0
            sym_idx_in_reloc = r_info >> 32
            sym_entry_off = sym_off + sym_idx_in_reloc * 24
            sym_name_off = struct.unpack("<I", data[sym_entry_off : sym_entry_off + 4])[
                0
            ]
            sym_name = get_str(sym_name_off)
            relocations.append({"offset": r_off, "symbol": sym_name})

    return {"text": text_bytes, "functions": functions, "relocations": relocations}


def main():
    if len(sys.argv) != 2:
        print("usage: extract_shellcode.py <object.o>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "rb") as f:
        data = f.read()

    info = parse_elf64(data)

    print(f"# Extracted from {sys.argv[1]}")
    print(f"# .text length: {len(info['text'])} bytes")
    print(f"# Functions: {len(info['functions'])}")
    print()

    # Relocations warning — must be empty for standalone shellcode
    if info["relocations"]:
        print(
            "# *** WARNING: relocations found in .text — shellcode will NOT work standalone ***"
        )
        print("# These indicate external function calls (memset, etc.).")
        print("# Recompile with: -fno-tree-loop-distribute-patterns -fno-builtin")
        print("# Or rewrite the C to avoid the patterns gcc converts to libc calls.")
        for r in info["relocations"]:
            print(f"#   at .text+0x{r['offset']:x}: needs symbol '{r['symbol']}'")
        print()

    # Hex literal
    hex_str = info["text"].hex()
    chunks = textwrap.wrap(hex_str, 76)
    print("_TEXT_HEX = (")
    for c in chunks:
        print(f'    "{c}"')
    print(")")
    print()

    # Offsets
    max_name_len = max((len(f["name"]) for f in info["functions"]), default=10)
    for f in info["functions"]:
        var_name = f"_OFF_{f['name'].upper()}"
        pad = " " * (max_name_len - len(f["name"]))
        print(f"{var_name}{pad} = {f['offset']}  # size {f['size']}")
    print()

    # Length assertion
    print("# Use this assertion to detect truncation in copy-paste:")
    print(f"# assert len(bytes.fromhex(_TEXT_HEX)) == {len(info['text'])}")


if __name__ == "__main__":
    main()
