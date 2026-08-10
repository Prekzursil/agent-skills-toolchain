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

### Pattern Language
### Common Mistakes
### Integration with Other Tools
### Patterns Repository
