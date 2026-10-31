---
title: algorithm-cheatsheet
type: note
permalink: dqverify-repo-20261013/skills/competitive-programming-solver/references/algorithm-cheatsheet
---

# Algorithm Cheatsheet

Match constraints → algorithm. C++ at 10^8 simple operations per second guideline.

## By complexity

### O(N!) — N ≤ 12
- Brute force permutations
- TSP exhaustive

### O(2^N · N) — N ≤ 22
- Bitmask DP (TSP held-karp, subset sum DP)
- Meet in the middle goes to N ≤ 40

### O(N^3) — N ≤ 500
- Floyd-Warshall shortest paths
- Matrix chain multiplication
- 3D DP (e.g. edit distance with 3 strings)

### O(N^2) — N ≤ 5000
- DP on 2D (LCS, edit distance, matrix-like)
- Convex hull O(N log N) but O(N^2) brute fits
- All-pairs BFS

### O(N · √N) — N ≤ 10^5
- Mo's algorithm on queries
- Sqrt decomposition
- Block factorization

### O(N log N) — N ≤ 10^6 (tight) or 10^5 (safe)
- Sort + two pointers
- Segment tree / Fenwick tree
- Persistent segment tree (heavier constant)
- Suffix array / suffix automaton
- Mergesort / convex hull / divide & conquer

### O(N log log N) — N ≤ 10^7
- Sieve of Eratostene
- Linear sieve for multiplicative functions

### O(N) — N ≤ 10^7 (C++), 10^6 (Python with luck)
- Two pointers
- KMP / Z-function string matching
- Tarjan SCC / bridges
- DFS / BFS on graph
- Monotonic deque (sliding window min/max)

### O(log N) per query — Q ≤ 10^6
- LCA via binary lifting / Euler tour + RMQ
- Persistent data structures
- Sparse table (O(1) per query after O(N log N) build)

### O(√N) per query
- Mo's algorithm
- Block decomposition

## Common patterns

### Sliding window min/max → monotonic deque
For each i, maintain a deque such that dq.front() is the best (min or max) in window [i-K+1, i]. O(N) total.

### 0-1 BFS → deque
Edges have weight 0 or 1. Use deque: push_front for w=0, push_back for w=1. O(V+E) instead of Dijkstra's O((V+E) log V).

### Kth element → quickselect or partition
Average O(N), worst O(N^2). For guaranteed O(N), use median of medians or heap.

### Counting distinct pairs (i,j) with property → for each j, count valid i's
Use sorted prefix counts, hashmaps, BITs. Don't iterate all pairs.

### Range sum + range update → lazy segment tree or difference array
If only "update one position, query range": Fenwick tree O(log N).
If "update range, query single position": difference array O(1) update.
If "update range, query range": segment tree with lazy propagation, or two BITs trick.

## Number theory shortcuts

### Count pairs (a, b) in [1, N] with gcd(a, b) > 1
Total pairs = N(N-1)/2. Coprime pairs = `sum_{n=1..N} phi(n)` minus 1 (subtract (1,1)). Answer = total - coprime.

### Number of divisors τ(n) up to N
Sieve: for d = 1..N, for j = d, 2d, 3d, ..., N: τ[j] += 1. O(N log N).

### Sum of divisors σ(n), sum of squares of divisors σ_2(n)
Same sieve pattern: for d = 1..N, for j = d, 2d, ..., N: σ_2[j] += d*d.

### Euler totient φ(n) up to N
```
phi[i] = i for all i
for i = 2..N: if phi[i] == i: for j = i, 2i, ..., N: phi[j] -= phi[j] / i
```

## When to switch language

If your C++ solution barely passes at the time limit, **don't port to Python expecting AC**. Python will be 5-20× slower. Either:
- Find an asymptotically faster algorithm (e.g. O(N) instead of O(N log N))
- Use low-level Python tricks (see python-speed.md)
- On pbinfo, escalate to shellcode JIT (see pbinfo-python-jit skill)
- Accept partial score