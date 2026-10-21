# Deep-dive: Sliver (native MCP server) — BishopFox/sliver

Date: 2026-09-29. All findings below were gathered this session via `gh api`, raw file fetches, GitHub issue/discussion search, and Exa REST search (`curl https://api.exa.ai/search`).

## Verdict

**Claim is REAL and essentially accurate as stated.** Sliver's mainline (release v1.7.7, 2026-09-03) ships a native, in-tree MCP server under `client/mcp/*` with stdio and HTTP/SSE transports and auto-generated token auth, plus a doc (`docs/sliver-ai-agentic-loop.md`) that explicitly ports the Codex (`examples/codex/codex-rs`) agentic loop into Sliver's AI chat. No Docker needed — official Windows-native binaries for both client AND server. Repo is very much alive.

## Repo metadata (ran: `gh api repos/BishopFox/sliver`)

```json
{"archived":false,"default_branch":"master","description":"Adversary Emulation Framework",
 "full_name":"BishopFox/sliver","language":"Go","license":"GPL-3.0","open_issues":227,
 "pushed_at":"2026-09-26T18:19:43Z","stars":11929}
```

- 11,929 stars, last push 3 days before today (2026-09-26), 227 open issues, not archived.
- Latest release: **v1.7.7, published 2026-09-03** (`gh api repos/BishopFox/sliver/releases/latest`).

## MCP claim verification (code read this session)

### 1. `client/mcp/*` exists in tree — CONFIRMED at both master HEAD and tag v1.7.7

Ran `gh api repos/BishopFox/sliver/git/trees/v1.7.7?recursive=1` — all 7 files present in the release tag:
`client/mcp/{auth.go, auth_test.go, config.go, filesystem.go, log.go, mcp.go, server.go}`.

Commit history (`gh api repos/BishopFox/sliver/commits?path=client/mcp`): MCP stdio landed **2026-01-02** ("Implement mcp stdio option", "Add basic file operations to mcp", "Add mcp logging"), HTTP auth added **2026-03-26** ("Implement http auth for mcp"). ~9 months in mainline.

### 2. EXPERIMENTAL — CONFIRMED

`docs/sliver-docs/pages/docs/md/MCP.md` (official docs page, also at sliver.sh/docs/?name=MCP) opens with:
> "__IMPORTANT:__ MCP (Model Context Protocol) support is _experimental_ and NOT ALL FUNCTIONALITY IS SUPPORTED YET."

### 3. stdio via sliver-client — CONFIRMED

`client/cli/mcp.go`: `sliver-client mcp` cobra subcommand → `transport.MTLSConnect(config)` (multiplayer config) → `clientmcp.ServeStdio(cfg, con.Rpc)`; `client/mcp/mcp.go` `ServeStdio()` wraps `mcpserver.ServeStdio` from **`github.com/mark3labs/mcp-go v0.45.0`** (go.mod). Docs page shows ready-made configs for OpenAI Codex (`[mcp_servers.sliver] command = "/path/to/sliver-client"`) and Claude Code (`claude mcp add sliver -- /path/to/sliver-client mcp ...`).

### 4. HTTP/SSE from client or server console with auto-generated token auth — CONFIRMED

- `client/mcp/mcp.go` `start()`: `TransportHTTP → mcpserver.NewStreamableHTTPServer`, `TransportSSE → mcpserver.NewSSEServer`, both wrapped in `newAuthenticatedTransport(cfg, handler, authInfo.Token)`.
- `client/mcp/auth.go`: `ResolveAuthInfo()` generates a **16-byte crypto/rand hex token on first use**, persists to `<rootAppDir>/mcp.yaml` (mode 0600), enforces min length 8, and authenticates via `Authorization` header with `subtle.ConstantTimeCompare`. SSE routes `/sse` + `/message`; streamable HTTP route `/mcp`.
- `client/command/mcp/start.go`: console `mcp start --transport http|sse --listen <addr> --yes`; `mcp` prints status incl. endpoint/token; `client/command/mcp/stop.go` for `mcp stop`.
- Docs page confirms verbatim: "The MCP HTTP/SSE server can be started from either the `sliver-client` or `sliver-server`" and shows a server-console session: `mcp start --transport http` → `Endpoint: http://127.0.0.1:8080/mcp` + `Auth Token: <hex>`.
- Notable: `McpStartCmd` gates startup behind `settings.IsUserAnAdultWithPrompt(con, "Do you know what prompt injection is and are you an adult?")` — an intentional operator-acknowledgement for an AI-facing exploit surface. `--yes` or `settings autoadult` skips it.
- Default listen is **`127.0.0.1:8080`** (`client/mcp/config.go` `DefaultConfig`), not 31100 — but `--listen` accepts any address, so binding to whatever the estate gateway (127.0.0.1:31100) proxies is supported config, not a code change. "Gateway can consume the HTTP/SSE endpoint directly, no Docker" is consistent: plain `net/http` + token header, native binaries.

### 5. MCP tool surface

`client/mcp/server.go:160-170` registers 11 tools: list sessions/beacons, ls, cd, cat, pwd, rm, mv, cp, mkdir, chmod, chown — remote filesystem ops scoped to the connected session/beacon via the Sliver RPC (`protobuf/rpcpb.SliverRPCClient`). No exec/process tools in mainline.

### 6. Codex agentic-loop doc — CONFIRMED

`docs/sliver-ai-agentic-loop.md` states the goal verbatim: "Port the example agentic loop from `examples/codex/codex-rs` into Sliver's AI chat" — turn/item lifecycle events, persisted reasoning + tool-call items, context-window separation, TUI rendering. Backed by real code: `server/ai/agentic_loop.go` (+_test), `server/ai/{ai,completion,context_window,driver,openai_driver}.go`, `server/rpc/rpc-ai-events.go`, dep `github.com/openai/openai-go/v2 v2.7.1` (go.mod). server/ai commits active through 2026-03-30.

## Install (REAL, not pip/npm)

Go project; no pyproject/setup.py/package.json. Packaging = GitHub release binaries + Makefile + Dockerfile (`docker build --target production -t sliver .` exists but is optional).

- Windows (this VM, native): download from https://github.com/BishopFox/sliver/releases/latest → `sliver-server_windows-amd64.exe` and/or `sliver-client_windows-amd64.exe` (each with a `.minisig`). That's the whole install; no Docker, no CGO needed for the MCP path.
- Linux: `curl https://sliver.sh/install|sudo bash` (README.md:21) or release binaries.

## Windows-native feasibility — HIGH CONFIDENCE YES

- README.md:9: "The Sliver server and client run on macOS, Windows, and Linux."
- Release assets include `sliver-server_windows-amd64.exe`, `sliver-server_windows-arm64.exe`, `sliver-client_windows-{amd64,arm64,386}.exe`.
- Deps relevant to the MCP server are pure Go: `mark3labs/mcp-go`, `net/http`, `gopkg.in/yaml.v3`; server storage via `gorm.io` + `glebarez/sqlite`/`modernc.org/sqlite` (pure-Go SQLite, no CGO). README:7 also documents Windows implant support; this box only needs the server/client, which are first-class Windows targets.

## Breakage check (issues/discussions)

- `gh api search/issues repo:BishopFox/sliver is:issue mcp` → exactly **1** hit: **#2294 "MCP server does not return auth token"** (opened 2026-07-22, Kali, latest release: `mcp start` printed no token and wrote no `mcp.yaml`). **Closed 2026-08-19**; comment 2026-08-25: "After recompiling the new patch the problem is now fixed." So the single reported MCP breakage is fixed in current release.
- 107 discussions total (recently active). None of the top-10 recent concern MCP/AI.
- No issues found matching "AI chat" query.

## Independent mentions (Exa REST, 2 queries)

- Official docs live: https://sliver.sh/docs/?name=MCP
- DeepWiki index page "AI Integration and MCP" for BishopFox/sliver (2026-03-27).
- **Alternatives / pre-native wrappers** (evidence people wired Sliver to MCP before/alongside native): `v0idravl/sliver-mcp` (also on Glama), `x746b/sliver-mcp`, `schwarztim/sec-sliver-c2-mcp`, PyPI `sliver-mcp` v1.0.1. These wrap the Sliver gRPC/client; mainline native MCP makes them largely redundant for this stack.
- PR **#2282** "feat: add AI Agent integration with MCP Server and CLI structured output" (community, 2026-07-07) proposed 20+ MCP tools — **closed, NOT merged**; mainline intentionally ships the smaller fs/session toolset.
- Practitioner signal: LinkedIn post (2026-03-20) "Built a Telegram-controlled C2 server using Sliver + AI".
- Unrelated known vuln surfaced: OSV GHSA-6fpf-248c-m7wm (not MCP-related; not examined in depth this session).

## Caveats

- "Experimental" is upstream's own label; tool surface is filesystem + session listing only (no process/exec tools), and issue #2294 shows rough edges as recently as August 2026 (now fixed).
- The claim's "127.0.0.1:31100" is estate-gateway infrastructure, not a repo value; repo default bind is 8080, configurable via `mcp start --listen`.
- Did not build or run the binaries on this VM this session; Windows feasibility rests on release assets, README platform statement, and pure-Go dependency set.

## Score

Value: **high** — closes a real capability gap: a first-class adversary-emulation C2 (11.9k stars, pushed 2026-09-26, v1.7.7 three weeks ago) exposing its RPC over native MCP (stdio for local agent hosts, token-authed HTTP/SSE for the estate gateway) with zero wrappers, plus a server-side AI agentic loop modeled on Codex. Windows-native via official release exes; no Docker required.
