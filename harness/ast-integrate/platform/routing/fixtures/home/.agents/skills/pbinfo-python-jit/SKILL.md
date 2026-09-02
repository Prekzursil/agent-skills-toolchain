---
name: pbinfo-python-jit
description: Makes Python solutions pass strict time limits on pbinfo.ro by embedding compiled x86-64 shellcode and executing it via ctypes + mmap. Use this skill whenever the user has a Python solution that is correct but gets TLE (Limita de timp depășită / Depășit) on pbinfo, especially when N is around 10^6 and the bottleneck is a sieve, BFS, sliding window, dynamic programming, or any tight Python loop. Also use when the user wants 100p Python on pbinfo problems that pure Python stdlib cannot reach (numpy is not available there). This skill extends the competitive-programming-solver skill — load that one too for the general workflow, then come here for the shellcode escalation. Trigger phrases include pbinfo Python TLE, Python pică pe pbinfo, vreau 100p Python, and Python prea lent pe judece românesc.
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

### Pbinfo sandbox capabilities (verified)
### The shellcode JIT workflow
### Step 1: Write the hot path in C
### Step 2: Compile with these specific flags
### Step 3: Verify no relocations
### Step 4: Extract the .text section and symbol offsets
### Step 5: Build the Python wrapper
### etc.
### 4KB pages are usually enough; round up to the next multiple of 4096 if needed
### Build function pointers using CFUNCTYPE
### ...
### Allocate buffers in Python and pass them in
