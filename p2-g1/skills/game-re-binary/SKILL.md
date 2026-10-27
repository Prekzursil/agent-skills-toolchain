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
get_xrefs_to(symbol)                # what calls a suspicious import
```

### Phase 4 — Decompile Key Functions Only
```
decompile_function(name)            # Ghidra pseudocode
get_il(address, il_type="MLIL")    # Binary Ninja MLIL for complex logic
get_function_xrefs(address)         # callers + callees
get_stack_frame_vars(address)       # local variable layout
```

## Output Format

Produce a structured report:
```
## Binary Summary
- Arch, bitness, type (EXE/DLL), entry point address
- Packer detected? (tiny imports + high-entropy section = yes)
- Notable sections

## Notable Imports (grouped)
- Network: WSAConnect, send, recv...
- Process: OpenProcess, VirtualAllocEx, CreateRemoteThread...
- Debug detection: IsDebuggerPresent, CheckRemoteDebuggerPresent...
- Crypto: CryptEncrypt, BCryptHashData...

## Interesting Strings
- Paths, registry keys, mutex names
- Version/build strings
- Error messages

## Suspicious Functions
- Function name/address + 5-10 line pseudocode snippet

## Entry Point Flow
- High-level call chain from entry
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Decompile everything immediately | Orient with imports/strings first — 5 min vs 30 min |
| Using only one tool | Binary Ninja navigates faster; Ghidra decompiles better |
| Ignoring section entropy | High entropy + tiny imports = packer — see game-unpack-pe |
| Missing string cross-references | Use `get_xrefs_to` on the string address, not just search |
| Not checking exports | DLLs expose logic through exports — start there |
