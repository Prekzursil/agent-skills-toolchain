---
title: DISPOSITION-TABLE
type: note
permalink: dqverify-repo-20261013/docs/mcp-audit/disposition-table
---

| disposition | server | S1 config | S2 host | S3 mounted | S4 real call | tools | name B | schema B | evidence |
|---|---|---|---|---|---|---|---|---|---|
| **DISABLE** | `searxng` | disabled | Connected | yes | PASS | 4 | 77 | 5640 | exact set arithmetic: all 4 tool names are a strict subset of search-hub's surface, 0 unique -- so disabling removes no REACHABLE capability. The duplicated tools are non-functional on BOTH sides: each was measured against the same unreachable http://127.0.0.1:8890, so this is deduplication of a DEAD capability, not a failover to a live one -- SCOPE: the call succeeded, the capability did not. backend measured non-functional: searxng-instance |
| **INVESTIGATE** | `brightdata` | pending-approval | FAILED | yes | -- | 5* | 86* | -- | HTTP transport: no stdio command to spawn, and no real call was made (metered third-party API -- a real call bills the owner's account) |
| **INVESTIGATE** | `deepwiki` | enabled | Connected | yes | -- | 3* | 49* | -- | HTTP transport: no stdio command to spawn, and no real call was made (live network call against a third-party AI service) |
| **KEEP** | `cloud-hub` | enabled | Connected | yes | PASS | 424 | 6998 | 321053 | real initialize+tools/list returned 424 tools in 230ms -- SCOPE: the call succeeded, the capability did not. backend measured non-functional: aws, azure, biomni, databricks, kaggle, modal, rclone, runpod, 311/424 advertised tools (73.3%) |
| **KEEP** | `search-hub` | enabled | Connected | yes | PASS | 68 | 1276 | 105831 | real initialize+tools/list returned 68 tools in 241ms -- SCOPE: the call succeeded, the capability did not. backend measured non-functional: firecrawl, searxng-instance, tavily |
| **KEEP** | `paper-search` | enabled | Connected | yes | PASS | 57 | 866 | 43457 | real initialize+tools/list returned 57 tools in 5315ms |
| **KEEP** | `github` | enabled | Connected | yes | PASS* | 47* | 781* | -- | real in-session call 'get_me' -> authenticated login returned |
| **KEEP** | `agent-mail` | enabled | Connected | yes | PASS* | 40* | 684* | -- | real in-session call 'health_check' -> health_check returned status=ok -- the server answered; this proves the mailbox process is up, not that message delivery works |
| **KEEP** | `figma` | enabled | Connected | yes | PASS* | 32* | 571* | -- | real in-session call 'whoami' -> handle + Full seat returned |
| **KEEP** | `chrome-devtools` | disabled | Connected | yes | PASS | 29 | 378 | 21971 | real initialize+tools/list returned 29 tools in 2953ms |
| **KEEP** | `playwright` | enabled | Connected | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 4470ms |
| **KEEP** | `playwright-cdp` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 5443ms |
| **KEEP** | `playwright-extension` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 4418ms |
| **KEEP** | `basic-memory` | enabled | Connected | yes | PASS* | 23* | 271* | -- | real in-session call 'list_memory_projects' -> 2 projects, default=main |
| **KEEP** | `angr` | disabled | Connected | yes | PASS | 14 | 189 | 8196 | real initialize+tools/list returned 14 tools in 7768ms; and a real in-session call 'list_projects' -> count=0 -- the server executed the tool and returned a valid empty project list; this proves tool execution, NOT that a binary can be loaded and analysed |
| **KEEP** | `frida-mcp` | enabled | Connected | yes | PASS | 13 | 211 | 6091 | real initialize+tools/list returned 13 tools in 4550ms; and a real in-session call 'enumerate_devices' -> 3 devices returned (local, socket, barebone) -- the server executed the tool and enumerated real host state; this proves tool execution and device enumeration, NOT that a process can be attached and instrumented |
| **KEEP** | `repomix` | enabled | Connected | yes | PASS | 8 | 154 | 18150 | real initialize+tools/list returned 8 tools in 3047ms |
| **KEEP** | `scholarly-access` | enabled | Connected | yes | PASS | 8 | 144 | 4707 | real initialize+tools/list returned 8 tools in 2846ms |
| **KEEP** | `qlty` | enabled | Connected | yes | PASS | 5 | 67 | 3013 | real initialize+tools/list returned 5 tools in 657ms; and a real in-session call 'qlty' -> returned PASS -- the round-1 lane recorded no detail beyond the verdict, so this proves the call completed and nothing about which check ran |
| **KEEP** | `huggingface` | enabled | Connected | yes | PASS* | 4* | 45* | -- | real in-session call 'hf_whoami' -> status=anonymous (server answered) |
| **KEEP** | `codex` | enabled | Connected | yes | PASS | 2 | 16 | 2340 | real initialize+tools/list returned 2 tools in 945ms; and a real in-session call 'codex' -> returned PONG with a threadId |
| **KEEP** | `context7` | disabled | Connected | yes | PASS | 2 | 28 | 4867 | real initialize+tools/list returned 2 tools in 5698ms |
| **KEEP** | `claude-code-mcp` | disabled | Connected | yes | PASS | 1 | 11 | 2594 | real initialize+tools/list returned 1 tools in 3273ms |

*Generated by `command-center/mcp-audit/render_table.py` from `disposition.json` (generated 2026-08-12). Do not hand-edit: `ci_gate.py` compares the regenerated bytes against this file.*

`S4 PASS` = stdio initialize+tools/list handshake.  `S4 PASS*` = a real in-session tool call instead (HTTP transport cannot be spawned).  Both count as S4 `call_verified`, which is their union: 21/23 rows.  Counts: {'DISABLE': 1, 'INVESTIGATE': 2, 'KEEP': 20}.  Throughout this table `*` means the same thing in every column: **measured by the client, not by a stdio child** -- so it marks a real measurement's instrument, never a weaker one.

RESIDENT cost -- the `tools` and `name B` columns, what every request carries for a mounted server -- is measured on 23/23 rows: 16 sampled from a stdio child, 7 marked `*` and joined from the client's own tool listing (`unsampled-surface.json`), which reaches the HTTP transports no stdio sweep can spawn. `assert_resident_completeness()` fails the producer if a mounted row carries no resident cost, or if a joined value drifts from that source.

CONTINGENT cost -- the `schema B` column -- is measured on 16/23 rows. A `--` there is **not measured**, never zero: this client defers schemas and never materialises them for the `*` rows, so no honest figure exists and the fleet contingent total remains a LOWER BOUND. The asymmetry between the two paragraphs is the measurement, not an omission.