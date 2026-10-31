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
```

Key differences from C:
- Types: `uchar`, `char`, `uint16`, `int16`, `uint32`, `int32`, `uint64`, `int64`, `float`, `double`, `string`
- Little-endian by default; use `BigEndian();` / `LittleEndian();` to switch
- `FSeek()`, `FTell()`, `FRead()`, `FWrite()` for file navigation
- `Printf()` for output in scripts
- Color annotations: `SetBackColor(cLtGreen);` before struct declaration

## Scripts (.1sc)

Scripts automate binary operations:

```c
// Example: Extract all entries to separate files
local int i;
local HEADER h;
ReadBytes(h, 0, sizeof(HEADER));

for (i = 0; i < h.numEntries; i++) {
    local ENTRY e;
    ReadBytes(e, sizeof(HEADER) + i * sizeof(ENTRY), sizeof(ENTRY));
    local int outFile = FileNew();
    local uchar buf[e.length];
    FileSelect(0);
    ReadBytes(buf, e.offset, e.length);
    FileSelect(outFile);
    WriteBytes(buf, 0, e.length);
    FileSave(SPrintf("entry_%04d.bin", i));
    FileClose();
}
```

## Template Repository

010 Editor has a built-in template repository accessible via:
- Menu: Templates > Template Repository
- Online: `https://www.sweetscape.com/010editor/repository/templates/`

Categories include: Archives, Audio, CAD, Database, Drives, Executables, Game files, Images, etc.

## Common Mistakes

- Forgetting `LittleEndian()` or `BigEndian()` at the top of templates for non-native byte order.
- Using `local` keyword for script variables but not for template-only variables.
- Not calling `FileSelect()` when working with multiple open files in scripts.
- Template variables are positioned sequentially -- use `FSeek()` to jump to specific offsets.
- Scripts run top-to-bottom; templates parse sequentially from current position.

## Integration with Other Tools

- Write `.bt` templates for game formats discovered via Ghidra/IDA RE.
- Use 010 Editor scripts to batch-patch binary files after identifying offsets.
- Export parsed template results for comparison with ImHex pattern output.
- Combine with CheatEngine: find runtime values, write 010 scripts to patch on-disk files.
- For SWFOC modding: create templates for DAT, MEG, MTD, TED, ALO file formats.

## Key Functions Reference

| Function | Purpose |
|---|---|
| `FSeek(pos)` | Seek to position |
| `FTell()` | Get current position |
| `FileSize()` | Get file size |
| `ReadByte(pos)` | Read byte at position |
| `ReadInt(pos)` | Read 32-bit int at position |
| `ReadString(pos)` | Read null-terminated string |
| `WriteByte(pos, val)` | Write byte |
| `Memcpy(dest, src, size)` | Memory copy |
| `SPrintf(fmt, ...)` | Format string |
| `Printf(fmt, ...)` | Print to output |
| `FileNew()` | Create new file |
| `FileOpen(name)` | Open existing file |
| `FileSave(name)` | Save current file |
| `FileClose()` | Close current file |
| `FileSelect(index)` | Switch active file |
