# Stress Testing — Verify Correctness Without Judge Test Data

When the user gives you a problem but no example tests (or only the trivial one from the statement), you can still verify your solution. The technique is **stress testing**: generate random inputs, run a brute-force solution, run your fast solution, compare outputs.

## When to stress test

- User reports WA on a hidden test but provided sources work on the sample
- User asks for a Python version of a working C++ — verify they agree
- You've written a new fast algorithm and want to be sure it matches the obvious slow one
- Problem has a tricky formula (counting pairs ordered vs unordered, indices 0- vs 1-based)

## The pattern

1. Write a **brute force** that obviously implements the spec (O(N^2) or worse, but undoubtedly correct)
2. Write the **fast solution**
3. Write a **generator** that produces small random inputs
4. Run both, compare outputs byte-for-byte
5. Loop. If they disagree, you have a counterexample to debug

```python
import random, subprocess, sys

def gen(seed):
    random.seed(seed)
    N = random.randint(1, 20)
    a = [random.randint(1, 100) for _ in range(N)]
    return f"{N}\n" + ' '.join(map(str, a)) + "\n"

for seed in range(1000):
    inp = gen(seed)
    open("problema.in", "w").write(inp)

    subprocess.run(["./brute"], check=True)
    expected = open("problema.out").read()

    subprocess.run(["python3", "solution.py"], check=True)
    got = open("problema.out").read()

    if got != expected:
        print(f"DIFF on seed {seed}")
        print("input:", inp)
        print("expected:", expected)
        print("got:", got)
        sys.exit(1)
    if seed % 100 == 0:
        print(f"ok through seed {seed}")
```

## Tips

- **Start small**: N ≤ 10 catches most bugs and runs in milliseconds
- **Edge inputs**: N=1, all same value, sorted, reverse-sorted, all max-value
- **Increase gradually**: once 1000 small tests pass, try N up to 1000
- **Print the input verbatim** when a diff is found — needed to reproduce

## Brute force tips

- For graph problems: try **all subsets / permutations**
- For DP: try **memoization without optimization** (no rolling array, no monotonic queue)
- For "shortest path with quirky cost": **Dijkstra with all states explored**

If your brute force gives a different answer than your fast one, the bug might be in **either**. Reproduce by hand on the smallest failing case.

## Stress for performance, not just correctness

For TLE concerns, generate **worst-case** inputs (max N, max values, adversarial patterns) and time the fast solution. Don't trust that "it ran fast on the sample" — sample inputs are usually tiny.

Example: for sliding window min/max with deque, the worst case is **strictly decreasing** input (forces deque to grow then shrink completely each step). Test with that.

```python
# Worst case for sliding window
N = 1_000_000
a = list(range(N, 0, -1))  # strictly decreasing
```
