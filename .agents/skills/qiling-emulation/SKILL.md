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
**Python 3.12** (3.11 also works) and install there:

```powershell
# from any working dir; keep this venv out of git
py -3.12 -m venv C:\Users\Prekzursil\.venvs\qiling
& C:\Users\Prekzursil\.venvs\qiling\Scripts\python.exe -m pip install --upgrade pip
& C:\Users\Prekzursil\.venvs\qiling\Scripts\python.exe -m pip install qiling
# sanity
& C:\Users\Prekzursil\.venvs\qiling\Scripts\python.exe -c "import qiling,unicorn,capstone;print(qiling.__version__)"
```

Verified working combo (2026-07-12): **qiling 1.4.6 · unicorn 2.1.4 · capstone 5.0.7** under
Python 3.12. `pip install qiling` pulls unicorn, capstone, keystone, pyelftools, gevent, etc.

Rootfs: emulating a *full* ELF that makes libc/syscall calls needs a matching rootfs
(Qiling ships `examples/rootfs/arm64_android` and `arm64_linux` in its git repo — clone
`github.com/qilingframework/qiling` if you need it, or use `--recursive` for the rootfs
submodule). Emulating a **single pure function via `code=`** (below) needs **no rootfs**.

## Smallest proof (this actually runs — verified)

Raw ARM64 code, no device, no rootfs — proves the CPU sandbox works:

```python
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN
from qiling import Qiling
from qiling.const import QL_ARCH, QL_OS, QL_VERBOSE

code, _ = Ks(KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN).asm("movz x0, #0x1234; add x0, x0, #0x11")
ql = Qiling(code=bytes(code), archtype=QL_ARCH.ARM64, ostype=QL_OS.LINUX, verbose=QL_VERBOSE.OFF)
ql.run()
assert ql.arch.regs.x0 == 0x1245        # -> passes
```

## Workflow: call one exported function of the BC `.so`

1. **Extract** the native lib: `apktool` / `unzip` the APK, take `lib/arm64-v8a/<lib>.so`.
2. **Locate** the target function's file offset / RVA and prototype in Ghidra/radare2 first
   (this skill executes; it does not find the function for you).
3. **Load & call** with Qiling, driving the ELF's own loader so relocations/GOT are set up:

```python
from qiling import Qiling
from qiling.const import QL_VERBOSE

# rootfs must match the .so's ABI (arm64 android). Point argv at the .so so Qiling maps it.
ql = Qiling([r"path\to\libnative-lib.so"], r"path\to\qiling\examples\rootfs\arm64_android",
            verbose=QL_VERBOSE.OFF)

base = ql.loader.images[0].base            # load base of the .so
func = base + 0x0000ABCD                   # RVA of the target export (from Ghidra)

# put args in x0..x7 (AArch64 AAPCS), allocate scratch memory for pointers as needed
buf = ql.mem.map_anywhere(0x1000)
ql.mem.write(buf, b"\x00" * 0x1000)
ql.arch.regs.x0 = buf
ql.arch.regs.x1 = 42

ql.arch.regs.lr = ql.os.exit_point        # so `ret` cleanly stops the emulator
ql.run(begin=func)                         # run from the function entry
print(hex(ql.arch.regs.x0))                # return value in x0
```

4. **Hook** anything you need — trace, patch, or stub a call:

```python
def trace(ql, address, size):
    print(f"{address:#x}")
ql.hook_code(trace)                        # or ql.hook_address(cb, addr) for one point
```

5. **Iterate**: wrap steps in a loop over many inputs to brute-force / map an algorithm — the
   whole point of going off-device (no per-call device round-trip, fully deterministic).

## Common mistakes

- Installing into base **Python 3.14** — wheels fail to build; always use the 3.12 venv above.
- Forgetting to set `lr`/`ol.os.exit_point` before `ql.run(begin=...)`, so `ret` runs off into
  unmapped memory instead of stopping — set the return address to the exit point.
- Passing pointer args as raw integers without first `mem.map`/`mem.write`-ing a real buffer.
- Emulating a function that calls into the engine/JNI/GLES and expecting it to "just work" —
  Qiling shines on **self-contained** routines; heavy engine coupling belongs on-device with
  `frida`. Pick the leaf function, not the whole subsystem.
- Treating a green emulation as ground truth without cross-checking one case against the real
  device via `frida` — emulation can diverge on missing syscalls/env. Confirm the anchor case.

## Relationship to the RE harness

Qiling is intentionally **not** auto-launched by `re-ensure` / `re_launch.py` (those bring up
IDA/Ghidra/HexStrike GUIs). It is a plain Python library in its own venv — invoke it directly
per the setup above. It is the local, license-free member of the same family as the parked
`Reversecore` bundle (angr + Qiling + Volatility3 + binwalk + CAPA); use this focused skill
rather than that mega-bundle.

## Reference

- Upstream: `https://qilingframework.io/` · repo `github.com/qilingframework/qiling`
- Docs (API, hooks, rootfs): the repo `docs/` and `examples/` directories
- Built on Unicorn (`unicorn-engine.org`), Capstone, Keystone
