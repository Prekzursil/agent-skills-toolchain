---
title: dive-RustHound-CE
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-rust-hound-ce
---

# Deep-dive: RustHound-CE (ad-entra-paths lane)

Date: 2026-09-29. Verifier: subagent on the estate VM. All checks below were executed in this session unless marked "not run".

## Claim under test
"597-star single-exe BloodHound CE collector (no .NET) with Windows release zips — the collection side of the dockerless stack: RustHound-CE → ArtBlood/Neo4j-MCP."

## Repo metadata (gh api, run 2026-09-29)
Command: `gh api repos/g0h4n/RustHound-CE`
- full_name g0h4n/RustHound-CE, created 2024-09-27, **not archived, not disabled**
- **stars 598** (claim said 597 — trivially stale, matches), forks 56, **open_issues 2** (one is feature request #69)
- **pushed_at 2026-09-17** — 12 days before this dive
- license MIT, language Rust, default branch main

## Verdict on the claim — CONFIRMED, with evidence
1. **Single exe, no .NET, runs Windows-native — VERIFIED BY EXECUTION.**
   Downloaded `rusthound-ce-Windows-msvc-x86_64.zip` from release v2.5.14 (3,511,203 bytes, published 2026-09-17T13:28:55Z), extracted `rusthound-ce.exe` (8,128,000 bytes) into out/research/ and ran it on this VM:
   - `./rusthound-ce.exe --version` → banner + `rusthound-ce 2.5.14`
   - `./rusthound-ce.exe` (no args) → banner + clap error "required arguments were not provided: --domain <domain>" — i.e. full CLI works, no DLL/loader errors.
   - Parsed the PE headers with Python (struct, manual import-table walk): PE32+ x64, subsystem 3 (console), **.NET CLR data-dir RVA = 0 → pure native, no .NET**. Imported DLLs are ONLY OS system DLLs: `bcryptprimitives.dll, kernel32.dll, secur32.dll, ntdll.dll, advapi32.dll, oleaut32.dll, api-ms-win-core-synch-l1-2-0.dll, ADVAPI32.dll, bcrypt.dll, ws2_32.dll, crypt32.dll`. No gssapi64/kfw, no libcrypto/libssl, no vcruntime140 (static CRT, matches `RUSTFLAGS=-C target-feature=+crt-static` for msvc in build.yml). GSSAPI path binds to SSPI (`secur32.dll`) on Windows at runtime.
2. **Windows release zips — CONFIRMED.** v2.5.14 assets include `rusthound-ce-Windows-msvc-x86_64.zip` (43 downloads) and `rusthound-ce-Windows-gnu-x86_64.zip` (25), plus Linux x86_64/arm64/armv7 and macOS x86_64/arm64 tarballs, each with .sha256. Release pipeline: `.github/workflows/build.yml` (tag `v*` triggered), 7-target matrix, windows-latest runners.
3. **"Collection side of the dockerless stack" — plausible and documented.** It emits BloodHound-CE-compatible JSON (`-z` zips them), which is the standard ingest format for BH CE and BH-JSON consumers (ArtBlood side not re-verified here; separate candidate). Bonus: v2.5.13 exposed a **Rust library API** (`ldap_auth()` + `run_collection()` return output path, no process::exit) per CHANGELOG — embeddable, not just a CLI.

## Real install command(s)
- **Easiest (verified here):** download `rusthound-ce-Windows-msvc-x86_64.zip` from GitHub Releases v2.5.14, extract, run. Works on a clean Windows box with zero prerequisites.
- **cargo:** `cargo install rusthound-ce` (README "Installation"; crates.io confirmed: `rusthound-ce` max/newest version **2.5.14**, updated 2026-09-17, **23,582 total downloads, 2,591 recent** — checked via `curl -A "research-agent" https://crates.io/api/v1/crates/rusthound-ce`).
  - Caveat for building from source: default features include `ldap3/gssapi`, and build.yml installs LLVM + **MIT Kerberos for Windows** (kfw-4.1 msi, sets INCLUDE/LIB) on the Windows runner; HELP.md:84 likewise requires clang/libclang + krb5 dev libs. So `cargo install` with default features on Windows needs those; `--no-default-features --features nogssapi` exists for gssapi-free builds (used for macOS/Linux-gnu/armv7 targets in CI). The release zips sidestep all of this.
- **Docker:** `docker build -t rusthound-ce .` (Dockerfile: rust:1.91.1-slim-bullseye + krb5/mingw toolchains) — irrelevant to the dockerless goal but works.

## Dependencies & Windows support (Cargo.toml, read at tag v2.5.14)
All-Rust TLS stack: `reqwest` with `rustls-tls` (no native-tls), `rustls` (ring), `ldap3 0.12.1` (tls-rustls-ring), `picky`/`picky-krb`/`ms-pac-forge` (Kerberos/PAC forging in pure Rust), `smb2-client 0.2.4`, `dcerpc 0.2.7` (HasSession/GPO sessions), `p12-keystore` (PFX), `winreg` optional behind `noargs` (Windows-only feature: pull domain from registry). rust-version 1.85. Release profile: lto, strip, codegen-units=1, panic=abort → small static exe. Nothing in the tree requires OpenSSL or .NET at runtime (confirmed by PE imports above).

## Activity / breakage check
- Commits: `gh api repos/.../commits` head shows 2.5.14 release + SharpHound-parity attribute work all on 2026-09-17. Issue/PR feed Aug–Sep 2026 is dense and **closed fast** (#50–#68 all closed; ESC8 fix #66, pass-the-cert #65, SMB PTT #64, HasSession #57, GPO parsing #55/#59/#60, SharpHound gap 75%→84% #68). No unresolved breakage; the 2 open items are feature request #69 (SAMR LocalGroups) + one more.
- CHANGELOG 2.5.14 documents its own ROADMAP coverage honestly: **84.3% of SharpHound v2.16.0.0 attributes (495/587)** — the remaining gap is the main functional deficit vs SharpHound.
- STATS.md self-benchmark (not independently re-run): ~3,500-object GOAD/BadBlood DC — RustHound Windows ~5.3s vs SharpHound.exe ~51.6s; BloodHound.py ~9.7s.

## Independent mentions (exa REST search, EXA_API_KEY, this session)
- https://www.hack2harden.com/the-osscp-toolkit-bloodhound-rusthound-ce — "The OSCP Toolkit: BloodHound + RustHound-CE"
- https://p3ta-tricks.com/page/bloodhound/collectors/RustHound — collectors page entry
- https://meterpreter.org/rusthound-cross-platform-bloodhound-collector-tool-written-in-rust/ (2025-09)
- https://undercodetesting.com/rusthound-ce-optimizing-active-directory-data-ingestion-for-bloodhound/ (2025-07)
- Ecosystem alternatives surfaced in the same searches: SharpHound (official, .NET-dependent — the thing this replaces), BloodHound.py (Python), ShadowHound (PowerShell, fndsec blog 2024-11).

## Honest caveats
- Stats benchmark and 84.3% coverage are the author's own numbers; I did not re-run a domain collection (no AD/LDAP target named by the ask).
- Release download counts are modest (68 Windows downloads of v2.5.14) — real but niche audience.
- Star claim off by one (597 vs 598 today) — immaterial.
- The gssapi default feature makes `cargo install` on Windows heavier than the zips; recommend zips or `nogssapi`.

## Scoring
- **windows: native** (proven by running the release exe on this VM).
- **value: high** — closes the real gap of collecting BH-CE graph data on Windows without .NET/SharpHound; MIT; very alive (12-day-old release); distributes as a verified self-contained exe; now also a Rust library for tighter stack integration.

## Artifacts left on disk
- `out/research/dive-RustHound-CE.md` (this file)
- `out/research/rh-msvc.zip`, `out/research/rusthound-ce.exe`, `out/research/_rh_readme.md`, `out/research/_rh_help.md`