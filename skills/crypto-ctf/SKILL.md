---
name: crypto-ctf
description: Use for cryptography CTF challenges, crypto homework, and education when
  you need to actually COMPUTE an attack rather than just describe one - RSA factoring
  and weak-key attacks (Fermat close-primes, Wiener small-d, common-modulus, Hastad
  broadcast, ROCA, lattice/Coppersmith), symmetric mode.
permalink: dqverify-repo-20261013/skills/crypto-ctf/skill
---

# crypto-ctf

A self-contained Python toolbox for solving cryptography CTF / educational challenges by actually running the attack math, not just explaining it.

**Scope / ethics:** authorized pentest, blue-team/detection, CTF, reverse-engineering, and education only. Do not use against systems or data you are not authorized to test. The recovered material (keys, plaintext) is for the engagement that authorized it.

## The venv

Everything runs in the dedicated venv next to this skill — do not pollute the global interpreter:

```
C:/Users/Prekzursil/.claude/skills/crypto-ctf/.venv/Scripts/python.exe
```

Installed (verified importable): `pycryptodome` (Crypto.*), `gmpy2`, `sympy`, `pwntools` (pwn/pwnlib), `z3-solver` (z3), plus RsaCtfTool's deps (`tqdm`, `bitarray`, `factordb-pycli`, `cryptography`, `requests`).

Run a one-off script:
```bash
"C:/Users/Prekzursil/.claude/skills/crypto-ctf/.venv/Scripts/python.exe" solve.py
```

Add a package if a challenge needs it (e.g. `pip install pycryptodomex`):
```bash
"C:/Users/Prekzursil/.claude/skills/crypto-ctf/.venv/Scripts/python.exe" -m pip install <pkg>
```

## RsaCtfTool (RSA multi-attack engine)

Cloned at `crypto-ctf/RsaCtfTool/`, installed editable. Run it as a module from the venv:

```bash
PY="C:/Users/Prekzursil/.claude/skills/crypto-ctf/.venv/Scripts/python.exe"

# Crack from a public key file, try every attack, dump the recovered private key
"$PY" -m RsaCtfTool.main --publickey key.pub --private --attack all

# Crack from raw parameters and decrypt a ciphertext
"$PY" -m RsaCtfTool.main -n <N> -e <E> --decrypt <C>

# Targeted attack (faster than 'all' when you know the weakness)
"$PY" -m RsaCtfTool.main -n <N> -e <E> --attack wiener      # small d
"$PY" -m RsaCtfTool.main -n <N> -e <E> --attack fermat      # close primes
"$PY" -m RsaCtfTool.main -n <N> -e <E> --attack factordb    # known/online factorization
"$PY" -m RsaCtfTool.main --publickey key.pub --attack roca  # CVE-2017-15361 (Infineon)
```

Available attacks include: `fermat`, `wiener`, `boneh_durfee`, `hastads`, `common_modulus_related_message`, `common_factors`, `factordb`, `roca`, `partial_d`, `partial_q`, `smallfraction`, `pollard_p_1`, `pollard_rho`, `ecm`, `qs`/`siqs` (quadratic sieve), `lattice`, `z3_solver`. List the full set with `--help`.

## When to reach for what (crypto triage)

1. **Identify**: encoding vs encryption vs hash vs signature/MAC. A hash is not authentication.
2. **Determine what you control**: plaintext/ciphertext, IV/nonce, an oracle (padding/error/timing), partial leakage.
3. **Highest-probability checks first**: peel encoding layers, known-plaintext XOR, nonce reuse, mode misuse.
4. **Escalate to heavy math only when forced**: lattices (LLL/Coppersmith), Z3/SMT, side channels.

### RSA
- Collect `n, e, c` and any extra ciphertexts / relations / leaks.
- First try `factordb` and `fermat` (close primes), then `wiener` (small d), `roca` (Infineon keys).
- **Shared prime across moduli:** `gmpy2.gcd(n1, n2) != 1` factors both instantly (bad RNG).
- **Common modulus:** same `m`, same `n`, coprime `e1,e2` -> `m = c1^a * c2^b mod n` via extended GCD.
- **Hastad broadcast:** same `m` to `e` recipients, small `e`, no padding -> CRT then integer e-th root.
- **Partial key / structured plaintext:** `partial_d`/`partial_q` or a Coppersmith lattice (sympy/z3 or RsaCtfTool `lattice`).

### Symmetric (pycryptodome `Crypto.Cipher`)
- **ECB**: repeated plaintext blocks -> repeated ciphertext blocks; cut-and-paste / block-splice to forge tokens.
- **CBC bit-flip**: flipping a byte in `C[i-1]` flips the same byte in `P[i]` (garbles `P[i-1]`) — privilege-escalation when no MAC.
- **CTR/GCM/stream nonce reuse**: `C1 ^ C2 = P1 ^ P2` (two-time pad); known plaintext recovers keystream. GCM nonce reuse also enables tag forgery.
- **Padding oracle (CBC/PKCS#7)**: decrypt and forge without the key, byte-by-byte via `P[i] = D(C[i]) ^ C[i-1]`.

### Hash / MAC
- **Length-extension** on `HASH(secret||msg)` with any Merkle–Damgard hash (MD5/SHA-1/SHA-256). Does NOT apply to HMAC. Use `hashpumpy`/`hlextend` (install on demand) or hand-roll with the known/brute-forced `len(secret)`.
- Password hashes at scale -> route to hashcat/john (HexStrike), not this venv.

### ECDSA / ECC
- **Nonce reuse** (`r` repeats across two signatures) -> recover `k`, then private `d`. Solve directly with `Crypto.Util.number.inverse` over the curve order.
- **Nonce bias/leakage** across many signatures -> lattice (HNP) recovery (z3/sympy or a SageMath box if available).

### Classical / encodings
- Peel layered transforms (base-encoding -> substitution -> compression). Recognize by tells (Base64 `A-Za-z0-9+/=`, gzip `1f 8b`, zlib `78 9c`). CyberChef "Magic" / `codext` auto-detect; sympy/pycryptodome for the math once decoded.

## Quick self-test (proves the stack)

```bash
"C:/Users/Prekzursil/.claude/skills/crypto-ctf/.venv/Scripts/python.exe" -c "import Crypto, gmpy2, sympy, z3, pwnlib; from Crypto.Util.number import inverse; print('crypto-ctf venv OK', Crypto.__version__, gmpy2.version(), sympy.__version__)"
```

A worked example (Fermat factorization of close primes + RSA decrypt round-trip) is the fastest sanity check — generate `n=p*q` with `q` near `p`, then `a=ceil(isqrt(n))`, increment until `a^2-n` is a perfect square, and `p,q = a+b, a-b`.

## Zero-install web batteries (first-pass, no setup)

FactorDB (factor a modulus), CyberChef (Magic / Raw-Inflate for encoding layers), quipqiup / dCode (classical ciphers), libc-database/libc.blukat.me (pwn side). Use these before spinning up heavy local computation.