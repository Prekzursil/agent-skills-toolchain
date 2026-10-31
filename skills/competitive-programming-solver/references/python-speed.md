---
title: python-speed
type: note
permalink: dqverify-repo-20261013/skills/competitive-programming-solver/references/python-speed
---

# Python Speed Techniques

Acest document e o colectie de trucuri pentru a face Python sa ruleze mai repede in competitive programming, **fara** sa apeleze la C extern.

## Tabel de orientare: ce e fezabil?

| Operatie | Python pur stdlib (CPython 3.4) | Cu numpy disponibil | Shellcode JIT (vezi pbinfo skill) |
|---|---|---|---|
| Sieve primi N=10^6 | ~0.4s (bytearray slice trick) | ~0.05s | ~0.02s |
| Sieve σ_2 N=10^6 | ~3s (TLE pe orice judge serios) | ~0.06s | ~0.07s |
| Sliding window N=10^6 | ~2-3s (TLE) | partial (nu sliding) | ~0.07s |
| BFS pe grila 10^6 noduri | ~2-3s (TLE) | nu se aplica direct | ~0.07s |
| Parsare 10^6 inturi | ~0.3s | `np.fromstring` ~0.05s | ~0.05s |

Daca pure Python nu trece si numpy nu e disponibil pe judce, fie alegi alt limbaj, fie folosesti tehnici shellcode (pbinfo skill).

## Trucul #1: Bulk read + custom parser

Nu folosi `input()` sau `sys.stdin.readline()` in bucla:
```python
# LENT
n = int(input())
a = [int(input()) for _ in range(n)]
```

Foloseste bulk read:
```python
import sys
data = sys.stdin.buffer.read().split()
# Sau pentru fisier numit:
# data = open("problema.in", "rb").read().split()
n = int(data[0])
a = list(map(int, data[1:n+1]))
```

Pentru ~10^7 numere, custom parser cu offset (FastScanner din template) e si mai rapid pentru ca evita crearea de list de tokens.

## Trucul #2: array.array pentru date numerice

Listele Python ocupa ~28 bytes per int. Pentru N=10^6 e ~28MB, peste limita uzuala de 64MB.

```python
from array import array
a = array('i', [0]) * N      # 4 bytes/element (int32)
b = array('q', [0]) * N      # 8 bytes/element (int64)
c = array('I', [0]) * N      # 4 bytes (uint32)
mask = bytearray(N)          # 1 byte/element (bool sau 0..255)
```

Bonus: `bytearray.__setitem__` e mult mai rapid decat `list.__setitem__` in bucle hot.

## Trucul #3: Hoist locals in bucle hot

Python lookup global / atribut de obiect e lent. In bucla cea mai interioara, copiaza tot ce folosesti in variabile locale:

```python
# LENT
for i in range(n):
    while self.data[self.i] <= 32:
        self.i += 1
    ...

# RAPID
data = self.data
n = self.n
i = self.i
while i < n and data[i] <= 32:
    i += 1
self.i = i
```

Asta poate dubla viteza.

## Trucul #4: Sieve Eratostene cu slice assignment

Stergerea segmentelor cu slice cu step e implementata in C in CPython:
```python
# Eratostene rapid pentru max_a ~ 10^6
prime = bytearray(b'\x01') * (max_a + 1)
prime[0] = 0
prime[1] = 0
i = 2
while i * i <= max_a:
    if prime[i]:
        # Asta sterge prime[i*i], prime[i*i+i], prime[i*i+2i], ... la viteza C
        prime[i * i :: i] = bytes(len(prime[i * i :: i]))
    i += 1
```

Cea mai rapida implementare de Eratostene in Python pur, ~0.3-0.4s pentru N=10^6.

## Trucul #5: Suma cifrelor via ASCII

Pentru a calcula `sum_of_digits(x) % 2` (paritate suma cifrelor):

```python
# LENT (~1.5s pentru 10^6 numere)
def parity(x):
    s = 0
    while x:
        s += x % 10
        x //= 10
    return s & 1

# RAPID (~0.5s) — paritatea sumei cifrelor == paritatea sumei codurilor ASCII
# pentru ca ord('0')=48 (par), '1'=49 (impar), etc. Diferenta e 48 (par), deci se conserva paritatea.
def parity_fast(x):
    return sum(bytes(str(x), 'ascii')) & 1
```

`sum()` pe `bytes` e implementat in C, 3× mai rapid decat bucla while.

## Trucul #6: Linear sieves pentru functii multiplicative

Sieve Eratostene clasic pentru `sigma_2(n)` (suma patratelor divizorilor) este O(N log N) si dureaza ~3s in Python pentru N=10^6.

Linear sieve construieste in O(N):

```python
spf = [0] * (N + 1)      # smallest prime factor
lpp = [0] * (N + 1)      # largest prime power: p^k where p=spf[n]
primes = []
for i in range(2, N + 1):
    if spf[i] == 0:
        spf[i] = i
        lpp[i] = i
        primes.append(i)
    spf_i = spf[i]
    lpp_i = lpp[i]
    for p in primes:
        ip = i * p
        if p > spf_i or ip > N:
            break
        spf[ip] = p
        if p == spf_i:
            lpp[ip] = lpp_i * p
            break
        else:
            lpp[ip] = p
```

Apoi pentru `sigma_2(n)`:
```python
sigma = [0] * (N + 1); sigma[1] = 1
for i in range(2, N + 1):
    p = spf[i]; lpp_i = lpp[i]; rest = i // lpp_i
    if rest == 1:
        prev = lpp_i // p
        sigma[i] = (1 + p*p) if prev == 1 else sigma[prev] + lpp_i * lpp_i
    else:
        sigma[i] = sigma[lpp_i] * sigma[rest]
```

In Python pur ~1.4s, jumatate fata de naive. Insa pentru a trece TLE de 0.4s pe pbinfo cu N=10^6 inca nu e suficient — trebuie tehnici de nivel shellcode.

## Trucul #7: I/O output buffered

Multiple `print()` apeluri sunt lente. Acumuleaza in lista si join la final:

```python
out = []
for _ in range(Q):
    out.append(str(answer))
sys.stdout.write("\n".join(out) + "\n")
# sau pentru fisier:
open("problema.out", "w").write("\n".join(out) + "\n")
```

Pentru `Q = 10^6` raspunsuri, asta e diferenta intre 5s si 0.2s.

## Trucul #8: Numpy daca e disponibil

Pe Codeforces, AtCoder si LeetCode, **numpy e instalat**. Pe pbinfo si Infoarena, **nu**. Verifica intai!

Daca e disponibil:
```python
import numpy as np

# Parsare rapida (10× mai rapida decat list(map(int, ...)))
nums = np.fromstring(raw_bytes, dtype=np.int64, sep=' ')

# Sieve Eratostene vectorizat
prime = np.ones(max_a + 1, dtype=bool)
prime[:2] = False
i = 2
while i * i <= max_a:
    if prime[i]:
        prime[i*i::i] = False
    i += 1
```

## Trucul #9: Caracter ord-uri ca tabela

In loc de `if c in '0123456789'`, foloseste tabele bytearray:

```python
DIGIT = bytearray(256)
for c in b'0123456789': DIGIT[c] = 1
# In hot loop: if DIGIT[data[i]]:
```

## Trucul #10: Cand totul esueaza

Daca toate trucurile de mai sus nu sunt suficiente pentru a trece TLE:

1. **Verifica daca PyPy e o optiune** pe judece — adesea e 10× mai rapid decat CPython si suporta acelasi cod (cu mici exceptii)
2. **Submit in C++** in loc de Python — pentru contest acceptat sa amesteci limbaje
3. **Pe pbinfo specific**, foloseste skill-ul `pbinfo-python-jit` care permite executie de cod x86-64 nativ din Python prin shellcode + ctypes + mmap

## Profilare rapida

Foloseste `time.perf_counter()` pe sectiuni:
```python
import time
t = time.perf_counter()
# ... cod ...
print(f"section: {(time.perf_counter()-t)*1000:.1f}ms", file=sys.stderr)
```

Pentru profile mai detaliat: `python -m cProfile script.py` (dar overhead mare).