# C Compile Recipe — gcc Flags Explained

The exact gcc invocation matters enormously for shellcode generation. This document explains each flag, what goes wrong without it, and how to debug.

## The canonical command

```bash
gcc -O2 \
    -fno-stack-protector \
    -fno-asynchronous-unwind-tables \
    -fno-plt \
    -fcf-protection=none \
    -fno-pic \
    -fno-tree-loop-distribute-patterns \
    -fno-builtin \
    -c lib.c -o lib.o
```

## Flag-by-flag

### `-O2`
Optimize. Without this, the compiled code might be 3–10× slower — defeating the whole point of using shellcode. `-O3` works too but can produce larger code with vectorization that doesn't always help.

### `-fno-stack-protector`
Disable stack canaries. Without this, every function emits a call to `__stack_chk_fail` at the start and end → relocation → won't work standalone.

Symptom if missing: `objdump -r` shows `__stack_chk_fail` references.

### `-fno-asynchronous-unwind-tables`
Don't emit `.eh_frame` section. The unwind tables aren't needed unless we throw C++ exceptions or use signal handlers. Stripping them shrinks the object and removes one potential reloc.

### `-fno-plt`
Don't use PLT for function calls. Combined with `-fno-pic`, ensures all calls within our object are direct relative jumps, not indirect PLT lookups.

### `-fcf-protection=none`
Disable control-flow protection (CET / endbranch / shadow stack). Otherwise gcc 11+ emits `endbr64` instructions at the start of every function, which are no-ops on older CPUs but might confuse the runtime in edge cases. Removing them makes the code 4 bytes shorter per function and more portable.

### `-fno-pic`
**The critical flag.** Without it, gcc emits position-independent code that references the Global Offset Table (GOT) for any non-local data. Since we're going to relocate the .text section to a fresh mmap'd page at runtime, GOT references would dereference garbage.

With `-fno-pic`, the compiler uses 32-bit RIP-relative addressing for code-to-code references (which is position-independent in a different sense — they're relative jumps), and absolute addresses for data, but we ensure there's no static data by passing everything as function arguments.

Symptom if missing: `objdump -r` shows `R_X86_64_GOTPCREL` relocations everywhere.

### `-fno-tree-loop-distribute-patterns`
**The non-obvious flag.** gcc has an optimization that recognizes patterns like:
```c
for (int i = 0; i < n; i++) arr[i] = 0;
```
And **converts them to a `memset` call** because libc's memset is hand-tuned. But that introduces a relocation to `memset`. Our shellcode can't call libc — so we need to turn this off.

Symptom if missing: `objdump -r` shows `memset` (or `memcpy`, `memcmp`) references.

### `-fno-builtin`
Belt-and-suspenders for the above. Even without the loop-distribute pass, gcc might see an explicit `memset()` call (or recognize one in `bzero`, `strlen`, etc.) and lower it to libc. `-fno-builtin` says "no, treat these as opaque external calls" — but combined with the lack of `-l` library flags at link time (we don't link), it forces gcc to use its own inline implementation when possible.

If after both flags you STILL see a memset/memcpy reloc, the C code has an explicit call to it somewhere — rewrite that part manually.

### `-c`
Compile only, don't link. We don't want a final executable; we want a .o file we can extract bytes from.

## Verifying the output

After compiling:

```bash
objdump -r lib.o          # Should produce NO relocation records
objdump -h lib.o          # Check .text size and other sections
objdump -t lib.o          # List symbols; functions should have non-zero size
objdump -d lib.o | head   # Disassembly — look for unexpected calls
```

The disassembly should contain only:
- Direct moves between registers and via stack-relative memory operands
- Direct memory operations via the pointers passed in arguments (rdi, rsi, rdx, rcx, r8, r9)
- Conditional jumps with 8- or 32-bit relative offsets to other addresses **within the same .text**
- No `call rel32` instructions referencing names like `memset`, `printf`, etc.
- No GOT references (no `(%rip)` operands that aren't local code refs)

## Calling convention reference (System V AMD64)

Integer arguments: `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` (in order).
Integer return: `rax`.
Floating point (if any): `xmm0`–`xmm7`.
Callee-saved: `rbx`, `rbp`, `r12`, `r13`, `r14`, `r15`.

When you write a Python `CFUNCTYPE`, the argument order in the Python type signature must match the order in the C declaration. Python passes args in the same registers as C does on x86-64 Linux.

## Pages and page sizes

Linux pages are 4096 bytes. `mmap` allocations are page-aligned, so the minimum mapping is 4KB. For shellcode under 4096 bytes, allocate one page; for larger, round up:

```python
page_size = 4096
mmap_size = ((len(_text) + page_size - 1) // page_size) * page_size
_mem = mmap.mmap(-1, mmap_size, prot=PROT_READ|PROT_WRITE|PROT_EXEC)
```

In practice, most competitive-programming shellcodes are ~500–2000 bytes, comfortably fitting in 4096.

## When things go wrong

### Symptom: segfault on first function call

Almost always one of:
1. **Wrong CFUNCTYPE signature** — argument types or return type don't match C declaration
2. **Unhandled relocation** — `objdump -r` reveals it
3. **Buffer too small** in Python; the C function writes past the end
4. **Wrong shellcode offset** — calling the middle of a function instead of its start

Debug by:
- Re-checking signatures against the C source
- Re-running `objdump -r` to verify no relocations
- Calling each function in isolation with a tiny input first

### Symptom: wrong answer but no crash

- Argument type mismatch (passing `c_int` where C expects `long` truncates to 32 bits)
- Off-by-one in C
- Endianness or sign confusion

### Symptom: works locally but fails on pbinfo

- Different glibc/kernel might tighten sandbox; rerun a quick `mmap.PROT_EXEC` probe
- Architecture mismatch (extremely unlikely — pbinfo is x86-64)
- gcc version skew producing slightly different bytes; recompile with the same version where possible
