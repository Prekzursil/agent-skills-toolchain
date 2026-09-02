---
name: game-re-binary
description: Use when asked to analyze, reverse engineer, or understand an unknown binary, game executable, or DLL. Applies when the goal is mapping the binary structure, finding notable functions, or understanding what a binary does without running it.
---

# Game Binary Static Analysis Pipeline

## Overview
Systematic three-tool static analysis combining Binary Ninja, Ghidra, and Cheat Engine MCP servers. The order matters — orient before decompiling.

**Never start with decompilation.** Strings + imports give 80% of the picture in seconds.

## Tool Map

| Goal | Tool | MCP prefix |
|---|---|---|
| Function list, imports/exports | Binary Ninja | `mcp__binary-ninja-mcp__` |
| Decompilation (pseudocode) | Ghidra | `mcp__ghidra-mcp__` |
| Cross-references, IL | Binary Ninja | `mcp__binary-ninja-mcp__` |
| String search | Binary Ninja | `list_strings` / `list_strings_filter` |
| Module enumeration (live) | Cheat Engine | `enum_modules` |

## Pipeline

### Phase 1 — Orient (do first, always)
```
select_binary(binary_path)          # Binary Ninja
get_binary_status()                 # confirm analysis complete
get_entry_points()                  # where execution starts
list_sections()                     # .text, .rdata, packed/suspicious?
```

### Phase 2 — Map Surface
```
list_imports()                      # external API calls — group by category
list_exports()                      # what it exposes
list_strings()                      # paths, URLs, error msgs, mutex names
list_strings_filter(pattern="anti|cheat|hack|inject|hook|detect")
```

### Phase 3 — Find Targets
```
search_functions_by_name("init")    # initialization routines
search_functions_by_name("scan")    # scanning logic
search_functions_by_name("check")   # validation/detection

### Phase 4 — Decompile Key Functions Only
### Output Format
### Binary Summary
### Notable Imports (grouped)
### Interesting Strings
### Suspicious Functions
### Entry Point Flow
