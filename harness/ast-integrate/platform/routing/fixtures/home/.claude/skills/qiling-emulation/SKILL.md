---
name: qiling-emulation
description: Use when you need to emulate or sandbox a native ARM/ARM64 shared object off-device — running the Battle Cats Android .so (or any Android/Linux ELF native library) inside the Qiling framework on the PC instead of on a rooted phone. This is the dynamic-OFF-device complement to the frida skill (dynamic-ON-device) and to the static ghidra/radare2/ida skills — reach for it to call a single exported native function with controlled inputs, brute-force or trace an algorithm (save crypto, PRNG, checksum, offset math) without the game engine or a device, hook native calls in a scriptable sandbox, or diff native behavior across app versions. Do NOT use for Java/Smali (use jadx), for live on-device instrumentation (use frida), or for pure static disassembly (use ghidra/radare2).
---

# Qiling Emulation (off-device native sandbox)

## Overview

Qiling is a Python binary-emulation framework built on Unicorn (the CPU emulator behind
QEMU) plus Capstone/Keystone. It loads a native ELF (`.so`/executable) for a *different*
architecture — e.g. Android `arm64-v8a` — and runs it on your x86-64 Windows PC with **no
device and no game process**. You script it in Python: set registers/memory, call one
exported function, read the result, hook any address.

Use it as the **dynamic-off-device** leg of the RE stack:

| Need | Tool |
|------|------|
| Live truth from the running app on a phone | `frida` (dynamic on-device) |
| Static structure / decompilation | `ghidra-mcp` / `radare2` / `ida-pro-mcp` |
| **Run one native function in a PC sandbox, no device** | **this skill (Qiling)** |
| Solve for an input that reaches a branch | `angr` |

Sweet spot for Battle Cats (`jp.co.ponos.battlecatsen`, custom PONOS C++/GLES engine): the
native code lives in `lib/arm64-v8a/*.so` inside the APK. When you have already located a
self-contained routine in Ghidra (save encrypt/decrypt, a checksum, an offset/schedule
computation, a PRNG) and want to **exercise it with many inputs** or confirm your
understanding, emulate just that function off-device instead of standing up a rooted device
+ frida session.

## Setup (venv — REQUIRED, do not use the base interpreter)

Qiling/Unicorn wheels do **not** build on the machine's default **Python 3.14** (bleeding
edge — same class of incompatibility that deferred AiZynthFinder). Create a dedicated venv on

### from any working dir; keep this venv out of git
### sanity
### Smallest proof (this actually runs — verified)
### Workflow: call one exported function of the BC `.so`
### rootfs must match the .so's ABI (arm64 android). Point argv at the .so so Qiling maps it.
### put args in x0..x7 (AArch64 AAPCS), allocate scratch memory for pointers as needed
### Common mistakes
### Relationship to the RE harness
### Reference
