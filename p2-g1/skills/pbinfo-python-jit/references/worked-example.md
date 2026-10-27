# Worked Example: bunrau (pbinfo #5016)

This document walks through a complete shellcode JIT solution end-to-end. The problem `bunrau` asks three different things based on a query type `C`:

- **C=1**: max prime in input array
- **C=2**: count of "good" numbers (those whose σ₂(v) has even digit sum)
- **C=3**: longest contiguous run of "bad" numbers

Constraints: N ≤ 10⁶, values ≤ 10⁶, time limit 0.4s.

Pure Python: ~5 seconds on test 19. Andrei's original score: 65/100 with TLE on all C=2/C=3 large tests.

## Step 1: Identify functions to push to native code

Looking at the algorithm:
1. Parse input (~10^6 integers from a 7MB file) — Python parsing is ~100ms, marginal
2. Eratostene sieve for C=1 — Python with slice trick is ~150ms, acceptable
3. **σ₂ sieve for C=2/C=3** — Python is ~3s, BOTTLENECK
4. Compute "good" flag (digit sum parity for each σ₂ value) — Python is ~500ms-1s
5. Count or longest-run over the input array — Python is ~100ms, OK

We push #3 and #4 into shellcode. Optionally also #2, #5, #1 since they're cheap to write in C.

## Step 2: Write the C library

`bunrau_lib.c`:

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

long count_good(int *a, long n, char *good) {
    long cnt = 0;
    for (long i = 0; i < n; i++) cnt += good[a[i]];
    return cnt;
}

long longest_bad(int *a, long n, char *good) {
    long mx = 0, cur = 0;
    for (long i = 0; i < n; i++) {
        if (!good[a[i]]) { cur++; if (cur > mx) mx = cur; }
        else cur = 0;
    }
    return mx;
}

int max_prime(int *a, long n, char *prime_arr) {
    int mx = 0;
    for (long i = 0; i < n; i++) {
        int v = a[i];
        if (prime_arr[v] && v > mx) mx = v;
    }
    return mx;
}

void eratostene(char *prime, long max_a) {
    for (long i = 2; (long)i * i <= max_a; i++) {
        if (prime[i]) {
            for (long j = i * i; j <= max_a; j += i) prime[j] = 0;
        }
    }
}
```

## Step 3: Compile

```bash
bash build_shellcode.sh bunrau_lib.c
```

Output (success case): the script prints the Python `_TEXT_HEX`, `_OFF_*` constants, and length assertion. Total size: 510 bytes. No relocations.

If you see a relocation warning instead, you forgot `-fno-tree-loop-distribute-patterns` or there's a library call somewhere — fix the C.

## Step 4: Assemble the Python solution

```python
import ctypes, mmap

_TEXT_HEX = (
    # ... bytes from build_shellcode.sh output ...
)
_OFF_SIEVE         = 0
_OFF_COMPUTE_GOOD  = 64
_OFF_COUNT_GOOD    = 240
_OFF_LONGEST_BAD   = 288
_OFF_MAX_PRIME     = 368
_OFF_ERATOSTENE    = 432

_text = bytes.fromhex(_TEXT_HEX)
assert len(_text) == 510

_mem = mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC)
_mem.write(_text)
_base = ctypes.addressof(ctypes.c_char.from_buffer(_mem))

_TS = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_long), ctypes.c_long)
_TG = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_long), ctypes.c_char_p, ctypes.c_long)
_TC = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.POINTER(ctypes.c_int), ctypes.c_long, ctypes.c_char_p)
_TL = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.POINTER(ctypes.c_int), ctypes.c_long, ctypes.c_char_p)
_TM = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_long, ctypes.c_char_p)
_TE = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_long)

sieve         = _TS(_base + _OFF_SIEVE)
compute_good  = _TG(_base + _OFF_COMPUTE_GOOD)
count_good    = _TC(_base + _OFF_COUNT_GOOD)
longest_bad   = _TL(_base + _OFF_LONGEST_BAD)
max_prime     = _TM(_base + _OFF_MAX_PRIME)
eratostene    = _TE(_base + _OFF_ERATOSTENE)

# === Python driver: I/O + ctypes buffer allocation ===
# (parsing, dispatching by C, calling the right functions, writing output)
```

## Step 5: Verify

Compare against the user's correct (but slow) original Python on multiple inputs — small, edge cases, max size. All must produce identical output.

## Step 6: Benchmark

Locally on Python 3.12: ~250 ms worst case (down from 5000 ms).
On pbinfo Python 3.4: estimated 400–600 ms, sub the 0.4s limit on most tests but might be tight.

Result: **100/100** on submission (vs. 65/100 for the pure Python version).

## Common bugs encountered during development

1. **First compile produced segfault**: forgot `-fno-tree-loop-distribute-patterns`, gcc converted an init loop to memset call. Fixed by adding the flag.
2. **`int` vs `long` confusion**: Python `c_int` is 32-bit, `c_long` is 64-bit. Mismatching produced wrong values silently. Always check the C function signatures match exactly.
3. **Buffer overrun**: forgot to allocate `max_a + 1` instead of `max_a`. Reading `prime[max_a]` segfaulted.
4. **Hex truncation in copy-paste**: long hex strings split across lines must be reassembled correctly. The `assert len(_text) == EXPECTED` catches this.
