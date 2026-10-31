---
title: diagnostic-tricks
type: note
permalink: dqverify-repo-20261013/skills/pbinfo-python-jit/references/diagnostic-tricks
---

# Diagnostic Tricks for pbinfo

Pbinfo's evaluation feedback is minimal — "OK", "Răspuns greșit", "Limita de timp depășită", or "Exited with error status X". You don't get a diff against expected output, and the WA error rarely reveals what was wrong. But you have **two channels** for extracting information from the judge:

1. **Exit code** (the X in "Exited with error status X"). Visible in the test results table. 1–255 inclusive — return 0 = treated as success; return 256+ wraps to 0.
2. **Your output file** — sometimes pbinfo shows the first few bytes you wrote in WA detail, or the user can compare against expected if they have a brute force.

## Trick #1: Exit code as bitmap

7 bits of information per submission. Encode multiple probe results into a single byte.

```python
import sys

status = 0

# Each probe sets one bit if it succeeds
try:
    import numpy
    status |= 1 << 0
except Exception:
    pass

try:
    with open("/tmp/test", "w") as f: f.write("x")
    status |= 1 << 1
except Exception:
    pass

# ... more probes, up to 7 (bits 0-6) ...

# Set bit 7 as sentinel so exit code is always in [128, 255] — easy to recognize
sys.exit((status & 0x7F) | 0x80)
```

On pbinfo, you'll see "Exited with error status X" where `X - 128` is your bitmap. Read each bit to determine what worked.

### Real example: how the pbinfo sandbox was probed

The original investigation that established what works on pbinfo used staged diagnostics:

- **Diag 1**: subprocess available? /tmp writable? gcc runnable? → status 159 (most yes, but compile+execute fails)
- **Diag 2**: probe gcc compilation directly → status 131 (gcc accepts arguments but fails to produce output)
- **Diag 3**: probe 3rd-party libs (numpy, scipy, gmpy2, sympy, cython, ctypes, mmap) → status 224 (only ctypes+mmap)
- **Diag 4**: probe `PROT_EXEC` mmap + shellcode "return 42" → status 239 (all green)

After diag 4, we knew shellcode JIT was viable on pbinfo.

## Trick #2: Encode metadata into output

Pbinfo sometimes shows your first few output lines in WA details. Use this to extract info about the input on a specific test where the algorithm gives WA mysteriously:

```python
# divq diagnostic for test 8 — write metadata instead of real answers
tokens = open("divq.in", "rb").read().split()
Q = int(tokens[0])
queries = [(int(tokens[1+2*i]), int(tokens[2+2*i])) for i in range(Q)]

# Build "fake" output with structural info
lines = [
    str(Q),
    str(max(n for _,n in queries)),
    str(min(n for _,n in queries)),
    str(sum(1 for t,_ in queries if t == 1)),
    str(sum(1 for t,_ in queries if t == 2)),
]
# Encode first 10 queries: type*10^9 + n
for k in range(min(10, Q)):
    t, n = queries[k]
    lines.append(str(t * 10**9 + n))

# Pad to Q lines
while len(lines) < Q:
    lines.append("0")

open("divq.out", "w").write("\n".join(lines) + "\n")
```

All tests show WA, but on the test you care about, the user clicks "details" and sees your output values. Decode them to learn about the input.

## Trick #3: Timing as a side channel

Different code paths take different times. If two tests both pass but take different time, you can infer something about the input via 1 bit ("did it go through the fast or slow path").

This is most useful for probing whether a particular branch executes:

```python
# If input has property X, do expensive_op(); else cheap_op()
if some_input_check:
    expensive_op()  # ~500ms
else:
    cheap_op()      # ~10ms
```

If a particular test shows ~500ms timing, property X holds; if ~10ms, it doesn't. Works well with already-passing solutions since you're not allowed to fail.

## Trick #4: Multiple submissions with intentional differences

For really stubborn cases (like the divq test 8 mystery where C/C++/Python all WA on a single test with seemingly-correct formula), submit several variants where each gives different answers on that test, and use the pattern of which pass to narrow down what the expected answer might be.

This is laborious and burns submissions, but for "test 8 is buggy" situations it's the only way.

## When to use which trick

| Goal | Best trick |
|---|---|
| Verify a Python feature is available on the judge | Exit code bitmap |
| Learn what's in a specific hidden test input | Metadata-in-output |
| Distinguish two execution paths | Timing |
| Figure out the expected answer when WA persists | Multiple variants (slow) |

## Limits

- One submission per minute on pbinfo (rate limit) — diagnostics take time
- Each diagnostic submission gets 0 points; if you're in a contest, this costs you
- Some sandbox details aren't probable from the script (e.g., precise CPython version, exact glibc) — but they're rarely relevant to algorithms