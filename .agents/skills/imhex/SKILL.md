---
name: imhex
description: Use when hex editing, binary analysis, pattern language parsing, file identification, hash computation, or hex dump generation is needed. ImHex provides a powerful CLI and pattern language for structured binary data inspection.
---

# ImHex

## Overview

ImHex is a hex editor for reverse engineers with a rich CLI and a custom pattern language for defining binary structures. Use it for file format analysis, binary template application, hash verification, and structured hex dumps.

## Quick Workflow

1. Confirm `imhex` is in PATH; run `imhex --version` to verify.
2. For file identification, use `imhex --magic desc <file>` (description) or `imhex --magic mime <file>` (MIME type).
3. For hex dumps, use `imhex --hexdump <file> <offset> <size>`.
4. For hash verification, use `imhex --hash <algo> <file>` (md5, sha1, sha256, sha384, sha512).
5. For structured parsing, write a `.hexpat` pattern file and run `imhex --pl format --input <file> --pattern <pattern.hexpat> --format json`.
6. For encoding/decoding, use `imhex --encode <format> <input>` or `imhex --decode <format> <input>`.
7. For demangling symbols, use `imhex --demangle <symbol>`.

## CLI Reference

| Command | Purpose |
|---|---|
| `imhex --magic desc <file>` | Identify file type (description) |
| `imhex --magic mime <file>` | Identify file type (MIME) |
| `imhex --hexdump <file> <offset> <size>` | Hex dump a region |
| `imhex --hash <algo> <file>` | Compute hash (md5/sha1/sha256/sha384/sha512) |
| `imhex --pl format --input <file> --pattern <pat> --format json` | Parse binary with pattern, output JSON |
| `imhex --pl run <script.hexpat>` | Execute a pattern language script |
| `imhex --pl docs <pattern.hexpat>` | Show pattern documentation |
| `imhex --pl info <pattern.hexpat>` | Print pattern metadata |
| `imhex --encode <format> <input>` | Encode a string |
| `imhex --decode <format> <input>` | Decode a string |
| `imhex --demangle <symbol>` | Demangle a C++/Rust symbol |
| `imhex -i <file>` | Display file information |
| `imhex --calc "<expr>"` | Evaluate a math expression |
| `imhex --plugins` | List installed plugins |

## Pattern Language

ImHex patterns (`.hexpat` files) define binary structures declaratively:

```cpp
struct Header {
    char magic[4];
    u32 version;
    u32 fileSize;
    u32 entryCount;
};

struct Entry {
    u16 id;
    u16 type;
    u32 offset;
    u32 size;
};

Header header @ 0x00;
Entry entries[header.entryCount] @ 0x10;
```

Run with: `imhex --pl format --input file.bin --pattern structure.hexpat --format json`

Output formats: `json`, `yaml`, `console`

## Common Mistakes

- Forgetting to specify `--format` when using `--pl format` (defaults to console).
- Using wrong offset/size units in `--hexdump` (bytes, not hex).
- Not checking `--magic` output before writing patterns for unknown formats.
- Pattern language uses C-like syntax but is NOT C -- `u8`, `u16`, `u32`, `u64`, `s8`, `s16`, etc. are the native types.

## Integration with Other Tools

- Export ImHex pattern output as JSON, pipe to `jq` for field extraction.
- Use `--hash` to verify file integrity before/after patching.
- Combine with Ghidra/IDA: identify structure in ImHex, apply types in decompiler.
- Write `.hexpat` patterns for game file formats (DAT, MEG, ALA, etc.) for SWFOC modding.

## Patterns Repository

ImHex has a built-in pattern store. Community patterns are at:
`https://github.com/WerWolv/ImHex-Patterns`

Install path: `%APPDATA%/imhex/patterns/`
