---
title: crypto-ctf skill built (security gem adopted)
type: note
permalink: main/reference/crypto-ctf-skill-built-security-gem-adopted
tags:
- security-kb
- crypto-ctf
- skills
- gem-adopted
---

# crypto-ctf skill built

TIER-0 security gem from SECURITY-GEMS-QUEUE (`cryptostego.md` §1.4.2/§4.1) is now ADOPTED. Closes the "no crypto math in-fleet" gap (HexStrike only had john/hashcat cracking, zero RSA/ECDSA/lattice/oracle math).

## Location
`C:/Users/Prekzursil/.claude/skills/crypto-ctf/`
- `.venv/` (Python 3.12.10) — was previously EMPTY (pip/wheel only); now fully provisioned.
- `SKILL.md` — written, registered (appears in harness skill list = parsed clean, no angle-brackets in description).
- `RsaCtfTool/` — cloned + `pip install --no-deps -e` (editable).

## Installed in venv (verified importable)
pycryptodome 3.23.0, gmpy2 2.3.1, sympy 1.14.0, pwntools 4.15.0, z3-solver 4.16.0.0, + RsaCtfTool deps (tqdm, bitarray, factordb-pycli, cryptography 49, requests).

## Key install gotchas
- **RsaCtfTool is NOT on PyPI for py3.12** (only py3.8 wheels) → must `git clone` from github.com/RsaCtfTool/RsaCtfTool.
- New RsaCtfTool layout = `src/` package, entry `RsaCtfTool.main:main`; run `python -m RsaCtfTool.main --help` (no top-level RsaCtfTool.py anymore).
- Its requirements.txt PINS old versions (cryptography==39, gmpy2==2.2.1, pycryptodome==3.10.4) that would downgrade/break the good stack → install editable with `--no-deps` and add only missing extras (tqdm, bitarray, factordb-pycli) unpinned.

## Verified working
End-to-end Fermat close-prime factorization + RSA decrypt round-trip returned `CTF{stack_works}`. RsaCtfTool exposes full attack suite (fermat, wiener, boneh_durfee, hastads, common_modulus, roca, partial_d/q, ecm, qs/siqs, lattice, z3_solver, factordb).

## Scope
Authorized pentest / blue-team / CTF / RE / education only. No cyber-safeguard flag hit (crypto-CTF math is exempt; not RE/malware or network-pentest).

## Sibling gems also surfaced this pass
security-kb-lookup + malware-analysis-triage skills are now registered too.
