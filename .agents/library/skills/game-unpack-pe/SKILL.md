---
name: game-unpack-pe
description: Use when asked to unpack, unprotect, or extract real code from a protected or obfuscated Windows executable. Applies when a binary shows a stub entry point, packed sections, few imports, or signs of VMProtect, Themida, UPX, or custom packers.
---

# PE Unpacking

## Overview
Identify the packer → find the Original Entry Point (OEP) → dump at OEP → fix IAT.
The dump is worthless without a fixed IAT; the IAT is unfixable without the correct OEP.

## Packer Detection

### Static Signals (check first via Binary Ninja)
```python
list_sections()     # .UPX0/.UPX1 = UPX; .vmp0/.vmp1 = VMProtect; .themida = Themida
list_imports()      # Only LoadLibrary + GetProcAddress = unpacking stub
get_entry_points()  # Entry point outside .text section = packer stub
```

### Packer Identification Table

| Packer | Static signature | Fast path |
|---|---|---|
| UPX | `.UPX0`, `.UPX1` sections | `upx -d target.exe` (CLI, done) |
| MPRESS | `.MPRESS1` section | mpress unpacker tool |
| VMProtect | `.vmp0`/`.vmp1`, VM interpreter loop at EP | `C:\GameSecTools\Packing\NoVmpy` or manual |
| Themida | Complex EP + anti-debug at start | `C:\GameSecTools\Packing\themida-unmutate` |
| Custom | One giant section, no real imports | Dynamic dump approach below |

## UPX (Trivial Case)
```powershell
upx -d target.exe   # produces unpacked target.exe immediately
```
Verify: `list_imports()` on result should show real API names.

## Dynamic Unpacking (Universal Approach)

### Step 1 — Find Where Unpacking Ends
**Using Frida** (set breakpoint on memory-write to .text):
```javascript
// Get .text section base + size from list_sections() output first
const textBase = ptr("0x401000");   // replace with actual .text base
const textSize = 0x50000;           // replace with actual size

MemoryAccessMonitor.enable({base: textBase, size: textSize}, {
    onAccess(details) {
        if (details.operation === 'write') {
            console.log("[WRITE TO .TEXT]", details.address, "from", details.from);
            // Single-step from here to find OEP
        }
    }
});
```

**Using Cheat Engine MCP:**
```python
# Set hardware BP on the .text section start address
set_data_breakpoint(address=0x401000, size=4, break_on="write")
# Run until BP fires (unpacker writing decompressed code)
# Then step until you see `jmp <original_entry>`
```

### Step 2 — Dump at OEP
Once at OEP, use KsDumper:
```
C:\GameSecTools\Memory\KsDumper
→ select target process → dump → save
```
Or via Frida (raw memory dump):
```javascript
const mod = Process.getModuleByName("target.exe");
const dump = mod.base.readByteArray(mod.size);
// Save dump via File.writeAllBytes or send() to host
```

### Step 3 — Fix Import Table
The dumped binary has invalid IAT pointers. Fix with **Scylla** (x64dbg plugin) or manually:

```javascript
// Frida: collect resolved API addresses during unpacking
// Hook GetProcAddress while unpacker resolves APIs
const gpa = Module.getExportByName("kernel32.dll", "GetProcAddress");
Interceptor.attach(gpa, {
    onEnter(args) { this.name = args[1].readAnsiString(); },
    onLeave(retval) {
        console.log("[IAT]", this.name, "=", retval);
        // Use this map to patch IAT in the dump
    }
});
```

### Step 4 — Verify Dump
```python
select_binary(dumped_path)
list_imports()      # Should show real API names, not just LoadLibrary
list_functions()    # Should show many functions, not just packer stub
get_entry_points()  # Should be inside .text section
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Dumping before OEP reached | Code still compressed — BP hits too early |
| Not fixing IAT | Dump crashes or shows no imports in Binary Ninja |
| Wrong dump base/size | Use `module.base` and exact `module.size` from Frida/Cheat Engine |
| Missing PE overlay | Some packers store data after PE headers — append overlay |
| VMProtect: treating as regular packer | VM bytecode needs devirtualization (NoVmpy/Titan), not OEP dump |
