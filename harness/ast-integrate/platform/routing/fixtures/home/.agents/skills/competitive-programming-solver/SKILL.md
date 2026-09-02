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

### Phase 2: Pick the algorithm
### Phase 3: Implement (C++ first)
### Phase 4: Implement C (if needed)
### Phase 5: Implement Python
### Verification before submission
### Common pitfalls
### Output expectations
### References
