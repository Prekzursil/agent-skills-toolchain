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

### Set hardware BP on the .text section start address
### Run until BP fires (unpacker writing decompressed code)
### Then step until you see `jmp <original_entry>`
### Step 2 — Dump at OEP
### Step 3 — Fix Import Table
### Step 4 — Verify Dump
