---
title: dive-ArtBlood
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-art-blood
---

# Deep-dive: ArtBlood (ad-entra-paths lane)

Date: 2026-09-29. Verifier environment: Windows 11 (win32 10.0.26100 x64), Git Bash, C:\Python314\python.exe.
Everything below was executed during this dive unless marked "not run".

## 1. Candidate (from the ask)

- name: ArtBlood
- repo: https://github.com/art3x/artblood
- claim: "Rust offline BloodHound analyzer + MCP: imports SharpHound JSON/ZIP into a local indexed cache — NO Neo4j, NO BloodHound server — shortest paths, tier-0, Kerberoast/AS-REP/ACL/ADCS-ESC reports, TUI; the best structural fit for a no-Docker estate (gated on adding Rust toolchain)."

## 2. Repo metadata (gh api repos/art3x/artblood)

| field | value |
| --- | --- |
| created_at | 2026-07-30T17:33:11Z |
| pushed_at | **2026-07-30T18:35:52Z** (last push = creation day; no commits in the 2 months since) |
| stargazers | 8 |
| forks | 2 (boboaung1337 — same-day 0★; x746b — 1 commit ahead, see §7) |
| language | Rust |
| license | GPL-3.0 (GPL-3.0-only per Cargo.toml) |
| open_issues | 0 (issues?state=all returns EMPTY — no issues, no PRs, ever) |
| discussions | disabled |
| default branch | main |
| commits | 1 ("Initial commit" 9ce2990) — history squashed to a single shot |
| contributors | 1 (art3x) |
| description | "A fast and smart analyzer for BloodHound data with TUI and MCP." |
| topics/homepage | none / null |

Author art3x: account created 2012-02-26, "InfoSec Expert", 11 followers, 4 public repos
(ascan_sliver 34★ C++, ascan 8★ C++, artweb 3★ C++). A real infosec developer with a
track record, not a throwaway account — but ArtBlood itself is a one-day, one-shot upload.

## 3. Claim verification against README + source

Source read: README.md (fetched via contents API), Cargo.toml, crates/*/Cargo.toml,
full shallow clone at out/research/artblood-src (commit 9ce2990).

| Claim | Verdict | Evidence |
| --- | --- | --- |
| Rust offline analyzer | TRUE | 9-crate workspace (~37k lines Rust; abh-cli/src/main.rs alone 18.5k lines) |
| Imports SharpHound JSON/ZIP | TRUE | README; abh-ingest parses `{"data":[...],"meta":{type,version}}` (crates/abh-ingest/src/lib.rs:259-291); zip crate dep. **Verified live** (§6) |
| Local indexed cache, no Neo4j/BH server | TRUE | Persistent cache at ~/.abh/cache (manifest/nodes/edges/strings/props/adj CSR + roaring bitmaps, blake3-checksummed manifest); zero network dependencies in Cargo.lock |
| Shortest paths | TRUE | `path` cmd, `shortest_paths` MCP tool. Verified live |
| tier-0 | TRUE | `owned-to-tier0`; effective tierzero/highvalue classification (README "Querying" section). Verified live via `path --to tier0` |
| Kerberoast/AS-REP/ACL/ADCS-ESC | TRUE | `kerberoast`, `asrep-roast`, `dangerous-acls`, `cert-esc` commands; all exercised live |
| TUI | TRUE on Unix; **degraded on Windows** | Raw mode is skipped on Windows by design: `fn set_ui_raw_mode(enable: bool) -> bool { if cfg!(windows) { return false; } ... "stty raw -echo" via sh -c }` (crates/abh-cli/src/main.rs:2084-2097). Fallback = line-based `ui>` REPL with full ANSI rendering (main.rs:2028-2056). Verified live (§6) |
| MCP | TRUE | rmcp 2.2.0 server, 8 tools: graph_stats, search_nodes, get_node, get_edge, query_graph, shortest_paths, reload_cache, ingest (crates/abh-mcp/src/lib.rs:175+, tool-catalog test at :771). Verified live (§6) |
| No-Docker fit | TRUE | No Dockerfile in repo; single binary; per-user cache; all deps cross-platform crates |

Extra capabilities beyond claim: native query DSL + Cypher subset (verified live), diff
between caches, Markdown/BloodHound-style reports, exports (json/jsonl/csv/md/dot/graphml/
opengraph), redaction, `--append` merges, `doctor` integrity check.

## 4. Packaging, install, releases

- **Releases**: v1.0.2 only (2026-07-30). Single asset `abh.tar.gz` = 9,172,648-byte
  **ELF 64-bit Linux binary** (magic 7f454c46 verified after download). 4 downloads.
  **No Windows or macOS binaries** — Windows requires a source build.
- **README install**: clone + `cargo build --workspace` (or `cargo build --release`), binary
  at `target/release/abh.exe` **"(not tested)"** per README; or `cargo install --path crates/abh-cli`.
- **CI** (.github/workflows/ci.yml): fmt+clippy+sensitive-files on ubuntu, and a
  build-and-test matrix on **ubuntu-latest AND windows-latest** running
  `cargo test --workspace --locked` + `cargo build --release --workspace --locked`.
  5 runs total (2026-07-30T18:08→18:35), all success. Verified job-level for the final run
  30571108643: "Build and test (windows-latest)" completed success in 5m05s.
- **No pyproject/setup.py/package.json/Dockerfile** — pure Cargo workspace, 170 lockfile packages.

### Real Windows-native install (what I actually did on this VM)

The VM had no Rust, no MSVC, no Windows SDK. Steps that worked:

1. `rustup-init.exe -y --default-host x86_64-pc-windows-gnu --default-toolchain stable --profile minimal`
   (cargo 1.98.1). NOTE: the minimal-profile rustup GNU toolchain alone FAILED — its
   self-contained `dlltool.exe` dies with "CreateProcess" (needs GNU `as.exe`, absent).
2. Downloaded winlibs MinGW-w64 (gcc 16.1.0, ucrt r4, 273MB zip) → extracted to
   out/research/mingw/mingw64, put its bin on PATH, set
   `CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=x86_64-w64-mingw32-gcc`.
3. `cargo build --workspace --locked` → **success in 1m23s** → target/debug/abh.exe.
4. `cargo test --workspace --locked` → **176 tests passed, 0 failed**
   (abh-cli 100 + 5 integration, abh-query 36, abh-ingest 12, abh-graph 9, abh-mcp 6,
   abh-schema 4, abh-cache 2, abh-algorithms 1, abh-output 1).

On a normal Windows dev box with VS Build Tools, plain MSVC rustup + clone + build works
(CI proves it); the MinGW dance was only needed because this VM has no MSVC/SDK.

## 5. Dependencies and Windows support

Workspace deps (Cargo.toml + Cargo.lock): anyhow, blake3 1.8.5, chrono, clap 4.6.1, csv,
libc 0.2.186, memmap2 0.9.10, pest/pest_derive 2.8.6, rayon, regex, rmcp 2.2.0
(server+transport-io+schemars), roaring 0.10.12, schemars, serde/serde_json, thiserror,
tokio 1.53.1, tracing(-subscriber), zip 0.6.6. All are cross-platform crates; none require
a server or service.

Platform-specific code is small and properly cfg-gated:
- `libc` used only for ioctl TIOCGWINSZ terminal size, `#[cfg(unix)]`, with a
  `#[cfg(not(unix))] -> None` fallback (main.rs:4641-4660); Windows size falls back to
  ARTBLOOD_UI_COLUMNS/LINES env, COLUMNS/LINES env, `tput` (absent on Windows), then 160x42.
- stty raw mode via `sh -c` — Unix only; Windows returns false (main.rs:2084-2097) → REPL fallback.
- Unix-only chmod 0600/0700 on cache/report files is a no-op on Windows
  (abh-cache/src/lib.rs:302-345, abh-cli main.rs write_private_output) — **cache/report
  files are NOT permission-restricted on Windows** (minor data-handling nit).
- Home dir prefers USERPROFILE on Windows (main.rs:752-757).

## 6. Live functional smoke test on THIS Windows VM (all run 2026-09-29)

Built debug abh.exe (§4). Synthetic SharpHound v5-format fixture (4 users incl. hasspn
and dontreqpreauth, DOMAIN ADMINS group with Members, DC01 computer with RegistrySessions,
domain with GenericAll ACE) zipped as a BloodHound-style ZIP.

| Command | Result |
| --- | --- |
| `abh --version` | "ArtBlood v1.0.2" |
| `abh ingest <zip> --output testcache --force` | "Wrote testcache with 7 nodes and 4 edges from 1 input(s)" (exactly the fixture count) |
| `abh doctor testcache` | all 12 sections ok (manifest blake3, CSR adjacency, 0 dangling edges) |
| `abh kerberoast testcache` | found ALICE@CORP.LOCAL and SVC-WEB@CORP.LOCAL (both hasspn) |
| `abh asrep-roast testcache` | found BOB@CORP.LOCAL |
| `abh dangerous-acls testcache` | "3 GenericAll ALICE@CORP.LOCAL -> CORP.LOCAL" |
| `abh path --from ALICE@CORP.LOCAL --to tier0 testcache` | 2 paths: MemberOf→DOMAIN ADMINS, GenericAll→CORP.LOCAL |
| `abh query testcache 'nodes(kind=User, hasspn=true, limit=5)'` | returned both hasspn users as JSON |
| `abh query --format table testcache 'MATCH (u:User) WHERE u.enabled = true RETURN u LIMIT 5'` | 4 users (Cypher subset works) |
| `abh search testcache alice` | ALICE@CORP.LOCAL |
| `abh owned-to-tier0 testcache` | "No paths found" (correct: no owned nodes in fixture) |
| `abh cert-esc testcache` | "No certificate ESC findings" (no CA data in fixture) |
| `abh mcp --cache testcache` + JSON-RPC handshake (mcp_smoke.py) | initialize → serverInfo artblood/1.0.2; tools/list → 8 tools; graph_stats → counts+manifest; shortest_paths ALICE→CORP.LOCAL returned the GenericAll path; clean exit |
| `printf 'help\nsearch alice\nquit\n' \| abh ui testcache` | full-screen ANSI UI renders; fallback `ui>` REPL accepted commands; "Search results for alice ... users=1"; exit 0 |

Not run: `cargo build --release` locally (debug build + CI's windows-latest release build
stand in); `abh ui` interactive mouse/single-key mode (impossible non-interactively, and
raw mode is skipped on Windows anyway).

## 7. Community / independent signals

- **Zero independent mentions found.** Exa search ("ArtBlood BloodHound analyzer Rust")
  returns only related tools (RustHound-CE, BloodHoundAnalyzer, pathhound, RustHound) —
  no ArtBlood hits. Web search finds only GitHub profile/repo snippets. No blog/HN/reddit/X.
- FIRECRAWL_API_KEY was **invalid** (POST api.firecrawl.dev/v1/scrape → "Unauthorized:
  Invalid token") — firecrawl scrape not usable this session; exa + WebSearch covered it.
- 8 stars, 4 release downloads, 2 forks. Fork x746b is 1 commit ahead:
  "release: add exact owned-principal marking" (2026-08-20, +180/−13 with tests) — a
  substantive patch = evidence of at least one real user. Other fork is a same-day 0★ copy.
- No issues/PRs/discussions at all: no breakage reports, but also no support trail.

### Alternatives (star counts fetched 2026-09-29 via gh api)
- g0h4n/RustHound-CE 598★ (active, 2026-09-17) — SharpHound-replacement **collector**;
  still needs Neo4j/BloodHound for analysis. Not a structural alternative.
- NH-RED-TEAM/RustHound 1175★ — legacy collector, stale (2024-10-21).
- lefayjey/BloodHoundAnalyzer 23★ (Shell) — JSON-dump report generator, no graph engine/MCP.
- bvtuhan/pathhound 0★.
=> No high-traction equivalent does "offline indexed cache + pathfinding + MCP without
Neo4j"; ArtBlood's niche is real and rare, but its own traction is near-zero.

## 8. Risks / corrections to the claim

1. **Not "the best structural fit" without caveats**: it IS the right shape (single binary,
   no services, no Docker, native MCP), but it's a one-commit, one-maintainer, 2-month-stale
   repo with zero community and zero independent validation. Pin the commit if adopted.
2. **Windows TUI is degraded**: mouse/keyboard-driven full TUI is Unix-only (stty raw via
   `sh -c`); Windows gets a line-based `ui>` REPL with full ANSI rendering. All CLI
   analysis commands + MCP are unaffected.
3. **No prebuilt Windows binary** — releases ship a Linux ELF only. Windows adoption = add
   Rust toolchain + build (verified working, incl. on this MSVC-less VM via MinGW).
4. **Cache/report files are not permission-restricted on Windows** (unix-only chmod).
5. GPL-3.0-only — fine for internal estate use; do not embed in proprietary tooling.
6. Sensitive-data handling is a design concern the author flags (README IMPORTANT box,
   check_sensitive_files.py CI step) — good sign.

## 9. Verdict

REAL, functional, and structurally exactly what the lane wants: offline BloodHound analysis
(shortest paths, tier-0, Kerberoast/AS-REP/ACL/ESC reports, DSL+Cypher queries, reports,
exports) plus a proper 8-tool MCP server, with no Neo4j, no server, no Docker. Proven
end-to-end on this no-Docker Windows VM: build (1m23s debug), 176/176 tests, live
ingest→analyze→MCP-handshake cycle. Value: HIGH for the capability gap (nothing else in the
alternatives set analyzes offline without Neo4j), with the single-maintainer/no-community
maintenance risk stated above. Windows: NATIVE (build from source; TUI degrades to REPL).