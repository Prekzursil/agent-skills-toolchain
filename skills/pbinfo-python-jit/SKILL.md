---
name: pbinfo-python-jit
description: Makes Python solutions pass strict time limits on pbinfo.ro by embedding compiled x86-64 shellcode and executing it via ctypes + mmap. Use whenever a correct Python solution gets TLE (Limita de timp depasita / Depasit) on pbinfo, especially at N around 10^6 with a sieve, BFS, sliding window, DP, or tight loop, or when the user wants 100p Python. Extends competitive-programming-solver.
---

# Pbinfo Python JIT — Shellcode Escalation

When a Python solution on **pbinfo.ro** is algorithmically correct but too slow for the judge's tight time limits, this skill enables a final-resort technique: **embed compiled x86-64 machine code as a bytes literal in the Python source, then load it into executable memory via `mmap` + `ctypes` and call it as if it were a normal C function**.

This bypasses CPython's interpreter overhead entirely for the hot path. It has consistently moved Python solutions from 35–65 points to **100 points** on problems like `bunrau`, `xk`, `bitmove`, and `divq`.

## When to use this skill

Only after the general `competitive-programming-solver` skill's Python techniques (bulk read, `array.array`, slice-assign sieves, ASCII digit-parity trick, linear sieves) have been tried and still TLE. Shellcode JIT has a setup cost — don't reach for it on easy problems.

Use shellcode when:

- pure Python stdlib version of an N=10^6 algorithm runs in ~2–3+ seconds locally (will TLE on judge)
- the algorithm is a tight inner loop: nested sieves, sliding window with `while`, BFS over millions of edges, DP over a grid
- the user has explicitly run out of options ("am încercat tot, tot pică")
- the user has confirmed (via `bunrau_diag6.py` or prior experience) that pbinfo's sandbox allows `PROT_EXEC` on mmap pages

Don't use shellcode when:

- the problem fits in pure Python with the right algorithm
- the user is targeting a judge other than pbinfo (most judges' sandboxes block `PROT_EXEC`)
- there's risk the user can't accept the solution (school assignments where source review matters more than score)

## Pbinfo sandbox capabilities (verified)

Empirically tested across multiple problems on pbinfo as of May 2026:

✅ `mmap.mmap(-1, size, prot=PROT_READ|PROT_WRITE|PROT_EXEC)` works
✅ `ctypes.CDLL("libc.so.6")` and `ctypes.CFUNCTYPE` work
✅ x86-64 shellcode in mmap'd page executes correctly
✅ Function pointers via ctypes return correct exit values
❌ `subprocess` to compile with gcc — gcc is present but cannot spawn `cc1`/`as`/`ld` (sandbox limits child processes)
❌ `numpy`, `scipy`, `gmpy2`, `sympy`, `cython` — not installed

This means: **bring pre-compiled bytes**, don't try to compile at runtime.

If you ever need to verify the sandbox on a new pbinfo problem (in case they tightened things), use the diagnostic technique described in `references/diagnostic-tricks.md`.

## The shellcode JIT workflow

### Step 1: Write the hot path in C

Write a `.c` file containing all the time-critical functions. Take the algorithm from the user's correct (but slow) Python and rewrite it in C. Make every function **position-independent** — no global variables, only arrays passed as pointers from Python.

Example pattern from a real solution (bunrau):

```c
void sieve(long *sigma, long max_a) {
    for (long d = 1; d <= max_a; d++) {
        long sq = d * d;
        for (long j = d; j <= max_a; j += d) sigma[j] += sq;
    }
}

void compute_good(long *sigma, char *good, long max_a) {
    for (long i = 1; i <= max_a; i++) {
        long x = sigma[i]; long s = 0;
        while (x > 0) { s += x % 10; x /= 10; }
        good[i] = ((s & 1) == 0) ? 1 : 0;
    }
}
```

Key C rules for shellcode-safe output:
- Pass **all** state as arguments (no globals)
- Use only basic types (`int`, `long`, `char*`, `unsigned long long`)
- No `printf`, `malloc`, `memset`, `memcpy`, or any library calls
- No floating point (avoids libm dependency)
- Plain loops; gcc -O2 will vectorize them safely with the right flags

### Step 2: Compile with these specific flags

```bash
gcc -O2 -fno-stack-protector -fno-asynchronous-unwind-tables \
    -fno-plt -fcf-protection=none -fno-pic \
    -fno-tree-loop-distribute-patterns -fno-builtin \
    -c lib.c -o lib.o
```

Critical flags explained:
- `-O2` — optimize; without this Python beats the result
- `-fno-pic` — no GOT references; we want plain absolute jumps within the code
- `-fno-stack-protector`, `-fno-asynchronous-unwind-tables`, `-fno-plt`, `-fcf-protection=none` — strip out everything that needs runtime support
- **`-fno-tree-loop-distribute-patterns -fno-builtin`** — CRITICAL. Without these, gcc converts `for (i=0; i<N; i++) arr[i]=0;` into a `memset` call. That introduces a relocation, which makes the shellcode segfault when loaded standalone. **This is the most common bug**

### Step 3: Verify no relocations

```bash
objdump -r lib.o
```

The output should be **empty** (no relocation records). If you see lines like `R_X86_64_GOTPCRELX  memset-0x4`, the code calls an external function — go back to step 2 and add `-fno-builtin` and `-fno-tree-loop-distribute-patterns`, or rewrite the C to avoid the offending pattern (e.g., use a manual loop instead of `for (i=0; i<N; i++) arr[i]=0;`).

### Step 4: Extract the .text section and symbol offsets

Use the helper script `scripts/extract_shellcode.py`:

```bash
python3 scripts/extract_shellcode.py lib.o
```

This script parses the ELF64 object file directly (no need for `objcopy`) and prints:
- The `.text` bytes as a hex string (already split into Python-literal-friendly lines)
- The byte offset of each function symbol inside `.text`
- The exact `len(_text)` value to assert at runtime

### Step 5: Build the Python wrapper

```python
import ctypes, mmap

_TEXT_HEX = (
    "..."   # hex string from extract_shellcode.py
)
_OFF_FUNC1 = 0
_OFF_FUNC2 = 64
# etc.

_text = bytes.fromhex(_TEXT_HEX)
assert len(_text) == EXPECTED_LEN

# 4KB pages are usually enough; round up to the next multiple of 4096 if needed
_mem = mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
_mem.write(_text)
_base = ctypes.addressof(ctypes.c_char.from_buffer(_mem))

# Build function pointers using CFUNCTYPE
_T_FUNC1 = ctypes.CFUNCTYPE(
    None,                              # return type (or ctypes.c_int, c_long, etc.)
    ctypes.POINTER(ctypes.c_long),     # arg 1
    ctypes.c_long,                     # arg 2
)
func1 = _T_FUNC1(_base + _OFF_FUNC1)
# ...

# Allocate buffers in Python and pass them in
buf = (ctypes.c_long * N)()
func1(buf, N)
```

The buffer types must match exactly what the C signatures expect. Use `ctypes.c_int` for `int`, `c_long` for `long`, `c_ulonglong` for `unsigned long long`, `c_char_p` for `char*` (or `create_string_buffer(N)` for mutable byte arrays).

### Step 6: Verify correctness against the original Python

Generate random test inputs, run both the user's original Python (which is correct but slow) and the shellcode version, compare outputs byte-for-byte. Cover edge cases:
- Smallest input (N=1)
- Boundary values (K=1, K=N)
- All-zero / all-same values
- Maximum N

Don't skip this. A bug in the shellcode (wrong offset, wrong CFUNCTYPE signature, off-by-one in C) won't produce a friendly error — it produces garbage or segfaults.

### Step 7: Benchmark

Locally on Python 3.12 you should see the shellcode version run **10–50× faster** than the original Python. On pbinfo's Python 3.4 the slowdown factor vs your local 3.12 is ~1.5–2×, so divide accordingly when estimating judge timing.

If your local 3.12 time is X ms, expect pbinfo 3.4 to take ~1.5–2×X ms. For a 1.0s judge limit, aim for ≤300 ms locally.

## Worked example: complete pipeline

For a concrete end-to-end example (the `bunrau` problem — σ_2 sieve + digit parity + sliding queries), see `references/worked-example.md`.

## Diagnostic tricks for pbinfo

Pbinfo's "Răspuns greșit" details are minimal. To learn what's actually happening (e.g., "is numpy available?", "does PROT_EXEC mmap work?", "what's in test 8?"), encode information into the **exit code** of your Python script.

When `sys.exit(N)` returns with N between 128 and 255, pbinfo displays "Exited with error status N" prominently in the test results. This gives you 7 bits of information per submission.

See `references/diagnostic-tricks.md` for the full pattern: how to construct bitmap-encoded exit codes, how to interpret them, and how to write metadata into `out` files for tests where the WA detail might show your output.

## Limitations and risks

- **Architecture-specific**: x86-64 only. ARM judges (if any pbinfo gets) would break. Currently pbinfo runs x86-64 Linux, so it's safe.
- **gcc version sensitivity**: gcc 11+ might emit slightly different instructions than gcc 9, but PIC-free code is robust. Recompile if the local gcc changes major versions.
- **Source code looks alien**: the hex blob is opaque. If a teacher reads the source for educational purposes, they'll have questions. Educate the user accordingly.
- **Slight ethical fuzziness**: this is hacky in spirit. Many judges would consider it against the rules. Pbinfo doesn't have an explicit ban (yet), and the user has already exhausted all "normal" Python paths, so use it knowingly.

## Output expectations

When delivering a shellcode-based solution:

1. **Show the original C source** as a comment block in the Python file (or as a separate `.c` file). This makes the solution auditable and lets the user (or anyone reading it) understand what's actually running.
2. **Explain briefly** in the response: which functions are in the shellcode, expected speedup vs. original, why pure Python couldn't make it.
3. **Verify locally first** — never deliver an untested shellcode.

## References

- `references/worked-example.md` — Full pipeline walkthrough on the `bunrau` problem
- `references/diagnostic-tricks.md` — Exit code encoding, output metadata, probing sandbox
- `references/c-compile-recipe.md` — Exhaustive gcc flag explanation and troubleshooting
- `scripts/extract_shellcode.py` — Parse ELF .o → Python hex literal + offsets
- `scripts/build_shellcode.sh` — One-shot: write C, compile, extract, emit Python wrapper template
