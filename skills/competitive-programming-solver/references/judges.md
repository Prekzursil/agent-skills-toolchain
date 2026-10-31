---
title: judges
type: note
permalink: dqverify-repo-20261013/skills/competitive-programming-solver/references/judges
---

# Judge-Specific Quirks

Each online judge has its own conventions. Get them wrong and you waste submissions.

## pbinfo.ro (Romanian high school + olympiad)

- **I/O**: named files only (`problema.in` / `problema.out`), NEVER stdin/stdout
- **Python version**: 3.4 (very old). No f-strings outside the eval engine, no walrus, no `match/case`, no `:=`
- **No third-party libs**: no numpy, no scipy, no sympy. Stdlib only
- **Time limits are strict**: 0.4–1.2s typical, no Python multiplier
- **Sandbox**: blocks `subprocess` for compiling gcc (so external compile hacks fail)
  - But **allows** `mmap` with `PROT_EXEC` + `ctypes`, enabling shellcode JIT (see `pbinfo-python-jit` skill)
- **Source size limit**: ~64KB, so don't try to embed huge precomputed tables
- **64-bit Linux x86-64** — important if you embed native shellcode
- **Stack limit**: 8MB. Deep recursion will RE
- **WA detail**: usually shows nothing useful besides "Răspuns greșit". No diff. But "Exited with error status X" shows the exit code 1–255, which lets you use sys.exit(N) to encode info (see diag technique in pbinfo skill)

## Infoarena (Romanian university + olympiad)

- **I/O**: named files (`problema.in` / `problema.out`)
- **Python**: usually 3.8+ but check per-problem
- **Time limit**: stated per problem, often 0.1–1.0s
- **No Python multiplier** historically; some problems explicitly accept Python only with specified algorithm

## Codeforces

- **I/O**: stdin/stdout
- **Python versions**: CPython 3.x AND PyPy 3.x available — **use PyPy if your solution is Python-friendly**, 5–10× faster
- **Time limit multiplier for Python**: 3× the C++ limit (so 1s C++ → 3s Python)
- **numpy available**, also a few other libs
- **Stack limit**: 256MB usually. Deep recursion OK
- **Output**: print or stdout.write both fine

## AtCoder

- **I/O**: stdin/stdout
- **PyPy3 and CPython3** both supported
- **Time limit multiplier for Python**: stated as 2.5× sometimes, but check each contest
- **Memory limit**: 1024MB usually — generous

## LeetCode

- **No I/O**: implement a class method with a defined signature
- **Returns**, doesn't print
- **Python 3 (CPython)**, sometimes with numpy
- **Time limits stated qualitatively** ("efficient", "must beat 50%")

## SPOJ / Kattis / CSES

- **I/O**: stdin/stdout
- **Old Python often** (SPOJ has had 2.7 for years)
- **Strict time limits**, often no Python multiplier
- For SPOJ specifically: pypy3 is sometimes available, sometimes not — check problem header

## USACO

- **I/O**: depends on problem; old problems use named files (`probname.in` / `probname.out`), recent ones use stdin/stdout
- **Python 3**, sometimes PyPy3
- **Time multiplier**: 4× for Python typically

## ICPC contests (live)

- **C++** is the standard. Python is allowed but rarely fast enough for full problems
- Use Python for **easy/medium** problems and **string parsing**, C++ for **hard algorithms**

## Generic detection

If the user doesn't say which judge:
- "Citește din N.in / N.out" or "se va citi din fișierul" → pbinfo or Infoarena, use freopen
- "Read from stdin" or "Input format" without filenames → stdin/stdout judge
- "Implement the function" → LeetCode-style, no I/O
- Mentions PyPy as an option → Codeforces / AtCoder

When in doubt, **ask the user** which judge before submitting — wasted submissions cost points in contests.