---
name: crypto-ctf
description: "Use for cryptography CTF challenges, crypto homework, and education when you need to actually COMPUTE an attack rather than just describe one - RSA factoring and weak-key attacks (Fermat close-primes, Wiener small-d, common-modulus, Hastad broadcast, ROCA, lattice/Coppersmith), symmetric mode."
---

# crypto-ctf

A self-contained Python toolbox for solving cryptography CTF / educational challenges by actually running the attack math, not just explaining it.

**Scope / ethics:** authorized pentest, blue-team/detection, CTF, reverse-engineering, and education only. Do not use against systems or data you are not authorized to test. The recovered material (keys, plaintext) is for the engagement that authorized it.

## The venv

Everything runs in the dedicated venv next to this skill — do not pollute the global interpreter:

```
C:/Users/agentuser/.claude/skills/crypto-ctf/.venv/Scripts/python.exe
```

Installed (verified importable): `pycryptodome` (Crypto.*), `gmpy2`, `sympy`, `pwntools` (pwn/pwnlib), `z3-solver` (z3), plus RsaCtfTool's deps (`tqdm`, `bitarray`, `factordb-pycli`, `cryptography`, `requests`).

Run a one-off script:
```bash
"C:/Users/agentuser/.claude/skills/crypto-ctf/.venv/Scripts/python.exe" solve.py
```

Add a package if a challenge needs it (e.g. `pip install pycryptodomex`):
```bash
"C:/Users/agentuser/.claude/skills/crypto-ctf/.venv/Scripts/python.exe" -m pip install <pkg>
```

## RsaCtfTool (RSA multi-attack engine)

Cloned at `crypto-ctf/RsaCtfTool/`, installed editable. Run it as a module from the venv:

```bash
PY="C:/Users/agentuser/.claude/skills/crypto-ctf/.venv/Scripts/python.exe"

# Crack from a public key file, try every attack, dump the recovered private key
"$PY" -m RsaCtfTool.main --publickey key.pub --private --attack all

# Crack from raw parameters and decrypt a ciphertext

### Targeted attack (faster than 'all' when you know the weakness)
### When to reach for what (crypto triage)
### RSA
### Symmetric (pycryptodome `Crypto.Cipher`)
### Hash / MAC
### ECDSA / ECC
### Classical / encodings
### Quick self-test (proves the stack)
### Zero-install web batteries (first-pass, no setup)
