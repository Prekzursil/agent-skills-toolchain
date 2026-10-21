# Deep-dive: x746b/sliver-mcp

Lane: c2-agentic · Verified 2026-09-29 on the estate VM (win32, Git Bash, uv 0.12.20, Python 3.12/3.14).
Local clone used for all code citations: `out/research/sliver-mcp/` (cloned from https://github.com/x746b/sliver-mcp, default branch `main`).

## 1. Repo metadata (ran: `gh api repos/x746b/sliver-mcp`)

| Field | Value |
|---|---|
| created_at | 2026-04-22T19:57:42Z |
| pushed_at | **2026-04-23T22:54:50Z** (dormant ~5 months) |
| stars / forks | 5 / 0 |
| open_issues | 0 — and `gh api repos/x746b/sliver-mcp/issues?state=all` → **0 issues ever filed** |
| releases | **0** (`gh api .../releases` → length 0) |
| license | **null via API — no LICENSE file in the repo** (README §License claims "MIT" — mismatch, see §6) |
| language | Python |
| size / branch | 35 KB / `main` |
| archived | false |

Commit history (`gh api repos/x746b/sliver-mcp/commits`): **9 commits, all 2026-04-22 → 2026-04-23** by the author, from `init: sliver-mcp v0.1 - 61 tools` (6aa4f00b) through `v0.2.4: sharpen armory tool docstrings` (079e0d28/9bb4e053) and two README fixups (65feca12). This is a one-week, single-author project. The author account is real and active: `gh api users/x746b` → "xtk", 171 public repos, 48 followers, account since 2023-03, pushes elsewhere through 2026-08 (e.g. x746b/shellcodes, pushed 2026-04-23 — the "related project" EDR-resilient loader linked in the README).

## 2. Files / packaging (ran: `gh api repos/.../git/trees/main?recursive=1`)

```
.gitignore 64b · README.md 10092b · pyproject.toml 447b
src/sliver_mcp/__init__.py (0b) · __main__.py (43b)
  server.py 43989b (1161 lines) · client.py 2674b · armory.py 10510b · serializers.py 2111b
```

No setup.py, no package.json, no Dockerfile, no tests, no CI workflows, no LICENSE file, no uv.lock. Packaging is pyproject + hatchling only.

`pyproject.toml` (read in full):
- `requires-python = ">=3.11"`, deps: `mcp>=1.2.0`, `sliver-py>=0.0.19`
- console script: `sliver-mcp = "sliver_mcp.server:main"`
- version 0.2.4 (README version table stops at 0.2.3 — trivial drift)

## 3. Claim verification

**"~74-tool Python MCP server" — EXACT.** Ran `grep -c "@mcp.tool" src/sliver_mcp/server.py` → **74**. Runtime count after import (this VM): `len(srv.mcp._tool_manager._tools)` → **74**. Tool names cover exactly the README scope table: 4 exec, 4 shellcode/assembly/sideload/DLL, 2 binary upload/download, 6 listeners (mtls/http/https/dns/wg + http stager), 7 implant generate/regenerate/builds/profiles/shellcode-from-implant, 11 session/beacon lifecycle, 5 identity (get_system/impersonate/revert_to_self/run_as/make_token), 6 recon, 6 env+registry, 10 armory (alias/extension list+info+run+register+call), 4 intel (hosts/loot/loot_content/canaries), 4 websites, plus server_version/pivot-listeners.

**"Complements the official fs-only native MCP" — VERIFIED.** `gh api search/code repo:BishopFox/sliver mcp in:path` → `client/mcp/filesystem.go` (30,750 bytes at tag v1.7.0, fetched directly), `client/mcp/{auth,config,server,log}.go`, `client/command/mcp/{mcp,start,stop}.go`, and `docs/sliver-docs/pages/docs/md/MCP.md`. Latest Sliver tag is v1.7.7, so README's "ships with Sliver v1.7+" holds. The official native MCP is filesystem-scoped; this repo's scope table claiming exec/listeners/implants/armory as its differentiator is accurate.

**"BOFs via coff-loader" — code-level VERIFIED, not runtime-verified.** `src/sliver_mcp/armory.py` is a real port: `pack_bof_args` (armory.py:211-271) implements the BOFArgsBuffer encoding (int LE32/short LE16 raw, string/wstring length-prefixed with NUL, per Sliver `client/core/bof.go`); `pack_bof_envelope` (armory.py:274-286) builds the `[u32 len][AddString(entrypoint)][AddData(bof)][AddData(args)]` envelope; `sha256_hex` (armory.py:289) is the RegisterExtension/CallExtension name, matching Sliver's `client/command/extensions/load.go` flow. `server.py:868,939,967,1053` make raw `_stub.RegisterExtension/_stub.CallExtension` gRPC calls because sliver-py 0.0.19 doesn't wrap extensions — as the README states. I did NOT execute any of this against a live Sliver server (none available on this VM); the mechanics are consistent with the referenced Sliver sources but runtime behavior is unverified.

**Code quality**: genuinely literate, not AI-slop. Honest "Known limitations" section in the README (BOFs not re-entrant per implant; no armory install — this MCP only consumes `~/.sliver-client/{aliases,extensions}/`; no event-stream consumer; **no audit log / allowlist / read-only mode — "planned"**). Beacon task polling at `client.py:37-48`; text-field auto-decoding at `serializers.py:36-60`.

## 4. REAL install command + Windows-native feasibility (RAN IT on this VM)

README install = `git clone` + `uv venv` + `uv pip install -e .`. **Not on PyPI under its own name**: `curl https://pypi.org/pypi/sliver-mcp/json` → package `sliver-mcp` 1.0.1 is a **different project** by `hi-unc1e` ("AI agent automation for post-exploitation", 17 tools, bilingual docs, no public GitHub repo — `gh api repos/hi-unc1e/sliver-mcp` → 404), uploaded 2026-05-26. So `pip install sliver-mcp` does NOT install this repo.

**BREAKAGE — reproduced here 2026-09-29**: pyproject's unbounded `mcp>=1.2.0` now resolves to MCP SDK 2.x, which removed `mcp.server.fastmcp`. Exact sequence run in `out/research/sliver-mcp`:

1. `uv venv --python 3.12` + `uv pip install -e .` → installs sliver-mcp 0.2.4, sliver-py 0.0.19, **mcp 2.2.0**, grpcio 1.84.0, protobuf 7.36.2 — all wheels, no compiler needed.
2. `uv run sliver-mcp` → **crashes on startup**: `ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x, where FastMCP was renamed to MCPServer ...` (`server.py:13` imports `from mcp.server.fastmcp import Context, FastMCP`). The README's own install instructions produce a broken server today.
3. `uv pip install "mcp<2"` → mcp 1.30.0; rerun with `./.venv/Scripts/python.exe -c "import sliver_mcp.server as srv; ..."` → **imports clean; 74 tools registered**; `./.venv/Scripts/sliver-mcp.exe` → correct argparse behavior: `error: --operator-config required (or set SLIVER_OPERATOR_CONFIG)`.

(Note: `uv run` re-syncs project deps and re-upgrades mcp to 2.x — use the venv interpreter directly, or `uv run --no-sync`, after pinning.)

**Windows-native: YES, verified at install/import level.** Everything resolves to wheels on Windows (grpcio `~=1.47` → 1.84.0 with win_amd64 wheels; sliver-py's 2022 gencode still imports under protobuf 7.36.2). The server is a pure gRPC *client* to a remote Sliver server over mTLS; the operator config path comes from `--operator-config` or `SLIVER_OPERATOR_CONFIG` (`server.py:1147-1155`), and the armory root is `Path.home()/".sliver-client"` (`armory.py:21`) — OS-agnostic. README examples are Linux-styled (`/opt`, `~/.sliver-client`) but nothing is Linux-locked. Not tested: a live MCP session against a Sliver server (no Sliver server on this box) — runtime behavior beyond import/registration is **not verified**.

## 5. Issues / discussions / community

- 0 issues, 0 PRs, 0 discussions, 0 forks, 0 releases — **zero community validation**. No breakage reports because there are no reports of anything.
- Relevant ecosystem finding (exa search): **CVE-2026-34227 / GHSA-6fpf-248c-m7wm** (published 2026-03-31, medium, CWE-306 missing-auth + CWE-942 permissive-CORS): "Sliver One-Click Remote Access: Insecure CORS & Unauthenticated MCP Interface" — against **Sliver's own** MCP interface, no patched version listed at fetch time. Directly relevant to the estate gateway: the "official native MCP" this project complements has a known unauthenticated-interface CVE, so gateway policy must cover both.

## 6. License discrepancy

README §License says "MIT" but `gh api repos/x746b/sliver-mcp` returns `license: null` and there is no LICENSE file anywhere in the tree. As-shipped the code is **all-rights-reserved-by-default**; usable, but the stated license is not backed by a file. Trivial to patch if adopted internally.

## 7. Independent mentions & alternatives (exa; firecrawl unusable)

Ran 2 exa searches (10 results each). **No independent mention of x746b/sliver-mcp anywhere** — every hit for it is the repo itself. No blog posts, no MCP directories, no advisories. Firecrawl `/v1/search` returned an empty body from this VM (unusable), so exa was the sole external search instrument — reported as such.

Alternative Sliver MCPs found:
- **schwarztim/sec-sliver-c2-mcp** — 6 stars, JavaScript, pushed 2026-09-09 (the only actively-maintained one, and more stars)
- **hi-unc1e sliver-mcp** (PyPI 1.0.1) — 17 tools, no public repo, Python ≥3.10
- **d4vydm/sliverc2_mcp** — 3 stars, Python, stale since 2025-05
- **xsxz/sliver-mcp** / **amenbroke/sliver-mcp** — Go, 1 star each (identical pushed_at → fork pair), stale since 2026-02
- **v0idravl/sliver-mcp** — listed on glama.ai but 404 on the GitHub API now (renamed/deleted; likely became the amenbroke repo)

x746b's remains the **largest and only armory/BOF-capable** Sliver MCP surface of the set.

## 8. Verdict

Real, technically sound, exactly as advertised — and effectively dead since 2026-04-23 with zero community validation and a **currently-broken fresh install** (one-line `mcp<2` pin fixes it; verified: imports + 74 tools registered + CLI runs on Windows-native Python 3.12). The claim's every checkable element held up: 74 tools exact, complement-to-official-fs-MCP verified in BishopFox/sliver, coff-loader BOF machinery present and faithful to Sliver's loader format. It closes a real gap for the c2-agentic estate lane (the official native MCP is fs-only), and nothing comparable with more maintenance exists. Scored **high** for value with explicit caveats: single-week authorship, no runtime verification against a live Sliver server, no LICENSE file despite README claiming MIT, and if adopted, pin `mcp<2` and expect to own the code from there.

Checks NOT run (stated plainly): no live Sliver server available, so no end-to-end tool execution (exec/armory BOF against a real implant) was performed; firecrawl search unusable.
