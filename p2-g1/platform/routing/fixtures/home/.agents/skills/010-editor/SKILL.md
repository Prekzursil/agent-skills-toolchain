---
name: 010-editor
description: Use when applying binary templates (.bt), running 010 Editor scripts (.1sc), or performing hex editing with SweetScape 010 Editor. Supports command-line batch processing of binary files with templates and scripts.
---

# 010 Editor

## Overview

SweetScape 010 Editor is a professional hex editor with a powerful Binary Template system for parsing structured binary data, and a C-like scripting language for automated binary manipulation. Use it for binary format reverse engineering, template-driven parsing, and batch hex editing.

## Quick Workflow

1. Confirm `010Editor.exe` is in PATH or at `C:\Program Files\010 Editor\010Editor.exe`.
2. For GUI analysis, open a file: `010Editor.exe <file>`.
3. For batch template application, use the `-script` flag with a `.1sc` script.
4. For command-line operations, use `-noui` mode with scripts.
5. Write Binary Templates (`.bt`) to define structures and scripts (`.1sc`) for automation.

## CLI Reference

| Command | Purpose |
|---|---|
| `010Editor.exe <file>` | Open file in GUI |
| `010Editor.exe -script:<script.1sc> <file>` | Run script on file |
| `010Editor.exe -template:<template.bt> <file>` | Apply template to file |
| `010Editor.exe -noui -script:<script.1sc> <file>` | Headless script execution |
| `010Editor.exe -compare:<file1> <file2>` | Compare two files |
| `010Editor.exe -import:<format> <file>` | Import hex/text data |

## Binary Templates (.bt)

Binary Templates define how to parse structured binary data:

```c
typedef struct {
    char magic[4];
    uint32 version;
    uint32 fileSize;
    uint32 numEntries;
} HEADER;

typedef struct {
    uint16 id;
    uint16 type;
    uint32 offset;
    uint32 length;
} ENTRY;

HEADER header;
ENTRY entries[header.numEntries];

### Scripts (.1sc)
### Template Repository
### Common Mistakes
### Integration with Other Tools
### Key Functions Reference
