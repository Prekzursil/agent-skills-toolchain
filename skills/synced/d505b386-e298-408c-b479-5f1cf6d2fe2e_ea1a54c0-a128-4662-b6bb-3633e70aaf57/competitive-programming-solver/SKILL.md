---
name: competitive-programming-solver
description: Solves algorithmic and competitive programming problems by producing fast, correct solutions in C, C++, and Python. Use this skill whenever the user mentions a problem from Codeforces, AtCoder, LeetCode, Infoarena, pbinfo, Kattis, SPOJ, USACO, ICPC, IOI, or any online judge / olympiad / contest. Also use for any problem statement with input/output specs, time/memory limits, or wording like "given N elements... output the answer", "TLE", "AC", "passes the time limit", "1-indexed array", or "competitive programming". Trigger even if the user only shares an input file, a buggy submission, or asks "why is my solution slow / wrong / failing test X". Default to producing all three languages unless the user specifies one.
---

# Competitive Programming Solver

A skill for producing **correct and fast** solutions to algorithmic problems, in **C, C++, and Python**, across all major online judges.

The goal is not just to write code — it's to write code that **passes within the time limit on the judge's machine**, which is the only success criterion that actually matters in competitive programming.

## When to use this skill

Use whenever the user is solving a problem from an online judge or competition. Concrete triggers:

- Names a judge: Codeforces, AtCoder, LeetCode, Infoarena, pbinfo, Kattis, SPOJ, USACO, HackerEarth, HackerRank, CSES, oj.uz, ICPC, IOI, etc.
- Pastes a problem statement (input format, output format, constraints, time/memory limits)
- Shares an existing solution that gets TLE, WA, MLE, RE, or partial score
- Asks for "the fastest way to compute X" with constraints like N ≤ 10^6
- Talks about contests, olympiads, ranked rounds, or training

If the user is on **pbinfo.ro specifically and needs Python to pass within tight limits**, also load the companion skill `pbinfo-python-jit` — it adds shellcode JIT techniques specific to the pbinfo sandbox.

## The five-phase workflow

Every problem follows the same phases. Do them in order, but don't skip ahead.

### Phase 1: Understand the problem

Read the statement carefully. Identify:

- **What is asked**: one output, multiple queries, optimization, counting, decision?
- **Input/output format**: stdin/stdout, named files, special separators, multiple test cases?
- **Constraints**: N, Q, values, time limit, memory limit, stack limit
- **Edge cases**: N=1, all same, all distinct, max values, empty inputs

For pbinfo problems specifically: the I/O is always named files (e.g. `problema.in` / `problema.out`), not stdin/stdout.

If anything is unclear (especially the formula for "type 2 queries", the exact pairing convention "ordered vs unordered", or whether indices are 0- or 1-based), **ask the user** before writing code. Wrong formula = WA on all hard tests.

### Phase 2: Pick the algorithm

Match the constraints to the algorithm class. This is the most important step.

| N (or operations) | Allowed complexity (per second, C++) |
|---|---|
| ≤ 12 | O(N!) brute force / bitmask |
| ≤ 25 | O(2^N) meet in middle |
| ≤ 500 | O(N^3) Floyd-Warshall, matrix DP |
| ≤ 5000 | O(N^2) DP, edit distance |
| ≤ 10^5 | O(N log N) sort, segment tree |
| ≤ 10^6 | O(N) or O(N log log N) sieves, BFS, two pointers |
| ≤ 10^7 | O(N) with low constant, mostly arithmetic |
| ≤ 10^9 | O(log N) or O(√N) per query |

Python is **5–20× slower** than C/C++ depending on the workload. For Python plan for a constant of ~10×; if the C++ solution barely fits the time limit, Python likely needs an algorithmic shortcut or low-level tricks. See `references/python-speed.md`.

Document the chosen algorithm briefly in a comment at the top of each source file, especially for Python. It helps debugging and helps the user understand.

### Phase 3: Implement (C++ first)

**Write C++ first**, even if the user wants Python. Reasons:
1. Catches algorithm bugs quickly — C++ runs fast enough that you don't conflate "slow" with "wrong"
2. Establishes the reference behavior against which Python / C can be verified
3. Most online judges run C++ at full speed, so this is the safest path to AC

The C++ template lives in `references/templates/template.cpp`. Key features:
- `FastScanner` class with `1 << 20` byte buffer and inlined `readChar`/`readInt`
- `freopen` for named-file I/O if the judge requires it
- String-buffered output (`string out; out.reserve(Q*16); ... fwrite(...)`) — `printf` is too slow when Q is large
- Avoid `std::endl` (flushes); use `'\n'`
- `using namespace std;` is fine for competitive programming

### Phase 4: Implement C (if needed)

Some judges accept only C (no C++). Some users want C for educational purposes. C is essentially C++ minus STL — port the C++ solution by replacing `vector` with raw `malloc`/`free`, `string` with manual `char buf[]`, and `deque` with circular buffer arrays.

Template: `references/templates/template.c`.

### Phase 5: Implement Python

Python has two failure modes: **TLE** (algorithm is fine but pure Python overhead kills it) and **MLE** (allocating millions of Python int objects). Defenses:

1. **Read in bulk** as bytes: `data = sys.stdin.buffer.read()`, parse with custom scanner over `bytes` (each byte is already an int 0–255, no decode needed)
2. **Use `array.array`** (or `bytearray` for byte arrays) instead of lists for million-element numeric storage
3. **Hoist locals**: in hot loops, `data = self.data; n = self.n; i = self.i` before the loop, write back at the end
4. **Batch I/O**: collect outputs in a list and `"\n".join(out)` at the end; never `print(...)` in a loop with millions of iterations
5. **Algorithmic shortcuts**: linear sieves, monotonic deques, sum-of-digit-parity via `sum(bytes(str(x), 'ascii')) & 1` (3× faster than `while x%10`)

Python template: `references/templates/template.py`. For deeper performance techniques and tricks specific to interpreted Python, see `references/python-speed.md`.

If pure Python can't make the time limit and the user is on **pbinfo**, escalate to the companion skill `pbinfo-python-jit`, which uses shellcode-via-ctypes-mmap to run native x86-64 code from inside Python. It has consistently turned 35–65p Python solutions into 100p across a dozen problems.

## Verification before submission

For every solution, before handing it to the user:

1. **Test on the provided example**(s) — copy the sample input from the statement, run, compare output byte-for-byte
2. **Test on extreme inputs** — generate worst-case inputs locally (max N, max values, all same, alternating, etc.) and verify timing and answer
3. **Verify Python matches C++** — if you wrote both, run both on the same random inputs and `diff` the outputs. If they disagree, one is wrong (usually Python — overflow, edge case, off-by-one)
4. **Check memory** — for N=10^6 with several long arrays, you can easily blow 64MB. Each `int` in Python is ~28 bytes; use `array('i', ...)` to get 4 bytes/element

If you can't get the original test data, **generate your own stress tests**. A correct slow brute-force compared against the fast solution catches most algorithmic bugs. See `references/stress-testing.md`.

## Common pitfalls

- **Integer overflow**: `N * (N-1) / 2` overflows `int` for N ≥ ~65536. Use `long long` in C/C++; in Python int is unbounded so no issue
- **Off-by-one**: many problems use 1-indexing in the statement. Match it in the code or convert consistently
- **freopen for named files**: pbinfo and Infoarena require `problema.in` / `problema.out`. Codeforces uses stdin/stdout. LeetCode has no I/O at all (function signature). Check before submitting
- **printf vs cout speed**: for very large output, neither is fast enough. Use string buffer + fwrite
- **Recursion stack**: most judges limit stack to 8MB; deep recursion (DFS on N=10^6) needs iterative rewrite or explicit stack
- **Endianness/word size**: judges are 64-bit Linux. Hardcoded shellcode in Python (see pbinfo skill) assumes this
- **PyPy vs CPython**: some judges offer both. PyPy is often 10× faster but has slower startup and different gotchas

## Output expectations

When the user asks for help, deliver:

1. **One source file per requested language**, named after the problem (`problem.cpp`, `problem.c`, `problem.py`)
2. A **brief explanation** of the algorithm — one or two paragraphs, not a wall of text
3. **Local benchmark numbers** if you could test (e.g. "N=10^6 in 140ms locally; should be ~300ms on the judge")
4. **Honest assessment** of expected score. If Python can only realistically score 65p instead of 100p without exotic tricks, say so. Don't promise AC if you're not sure.

Always use `present_files` to deliver the source files at the end so the user can download them.

## References

Load these as needed (don't load them all upfront — they're substantial):

- `references/templates/template.cpp` — Production C++ template with FastScanner
- `references/templates/template.c` — Same in pure C (no STL)
- `references/templates/template.py` — Python template with FastScanner and array storage
- `references/python-speed.md` — Detailed Python performance techniques (digit-parity tricks, linear sieves, numpy when available, etc.)
- `references/algorithm-cheatsheet.md` — Quick reference: what algorithm fits which constraint
- `references/stress-testing.md` — How to verify correctness without judge test data
- `references/judges.md` — Quirks per judge (pbinfo, Codeforces, AtCoder, LeetCode, etc.)
