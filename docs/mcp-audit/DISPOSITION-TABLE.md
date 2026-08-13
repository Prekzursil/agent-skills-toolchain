| disposition | server | S1 config | S2 host | S3 mounted | S4 real call | tools | name B | schema B | evidence |
|---|---|---|---|---|---|---|---|---|---|
| **DISABLE** | `searxng` | disabled | Connected | yes | PASS | 4 | 77 | 5640 | exact set arithmetic: all 4 tool names are a strict subset of search-hub's surface, 0 unique -- so disabling removes no REACHABLE capability. The duplicated tools are non-functional on BOTH sides: each was measured against the same unreachable http://127.0.0.1:8890, so this is deduplication of a DEAD capability, not a failover to a live one -- SCOPE: the call succeeded, the capability did not. backend measured non-functional: searxng-instance |
| **INVESTIGATE** | `brightdata` | pending-approval | FAILED | yes | -- | -- | -- | -- | HTTP transport: no stdio command to spawn, and no real call was made (metered third-party API -- a real call bills the owner's account) |
| **INVESTIGATE** | `deepwiki` | enabled | Connected | yes | -- | -- | -- | -- | HTTP transport: no stdio command to spawn, and no real call was made (live network call against a third-party AI service) |
| **KEEP** | `cloud-hub` | enabled | Connected | yes | PASS | 424 | 6998 | 321053 | real initialize+tools/list returned 424 tools in 230ms -- SCOPE: the call succeeded, the capability did not. backend measured non-functional: biomni, databricks, modal, rclone, runpod, 267/424 advertised tools (63.0%); 7 further backend(s) UNMEASURED |
| **KEEP** | `search-hub` | enabled | Connected | yes | PASS | 68 | 1276 | 105831 | real initialize+tools/list returned 68 tools in 241ms -- SCOPE: the call succeeded, the capability did not. backend measured non-functional: searxng-instance |
| **KEEP** | `paper-search` | enabled | Connected | yes | PASS | 57 | 866 | 43457 | real initialize+tools/list returned 57 tools in 5315ms |
| **KEEP** | `chrome-devtools` | disabled | Connected | yes | PASS | 29 | 378 | 21971 | real initialize+tools/list returned 29 tools in 2953ms |
| **KEEP** | `playwright` | enabled | Connected | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 4470ms |
| **KEEP** | `playwright-cdp` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 5443ms |
| **KEEP** | `playwright-extension` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 4418ms |
| **KEEP** | `angr` | disabled | Connected | yes | PASS | 14 | 189 | 8196 | real initialize+tools/list returned 14 tools in 7768ms; and a real in-session call 'list_projects' -> count=0 -- the server executed the tool and returned a valid empty project list; this proves tool execution, NOT that a binary can be loaded and analysed |
| **KEEP** | `frida-mcp` | enabled | Connected | yes | PASS | 13 | 211 | 6091 | real initialize+tools/list returned 13 tools in 4550ms; and a real in-session call 'enumerate_devices' -> 3 devices returned (local, socket, barebone) -- the server executed the tool and enumerated real host state; this proves tool execution and device enumeration, NOT that a process can be attached and instrumented |
| **KEEP** | `repomix` | enabled | Connected | yes | PASS | 8 | 154 | 18150 | real initialize+tools/list returned 8 tools in 3047ms |
| **KEEP** | `scholarly-access` | enabled | Connected | yes | PASS | 8 | 144 | 4707 | real initialize+tools/list returned 8 tools in 2846ms |
| **KEEP** | `qlty` | enabled | Connected | yes | PASS | 5 | 67 | 3013 | real initialize+tools/list returned 5 tools in 657ms; and a real in-session call 'qlty' -> returned PASS -- the round-1 lane recorded no detail beyond the verdict, so this proves the call completed and nothing about which check ran |
| **KEEP** | `codex` | enabled | Connected | yes | PASS | 2 | 16 | 2340 | real initialize+tools/list returned 2 tools in 945ms; and a real in-session call 'codex' -> returned PONG with a threadId |
| **KEEP** | `context7` | disabled | Connected | yes | PASS | 2 | 28 | 4867 | real initialize+tools/list returned 2 tools in 5698ms |
| **KEEP** | `claude-code-mcp` | disabled | Connected | yes | PASS | 1 | 11 | 2594 | real initialize+tools/list returned 1 tools in 3273ms |
| **KEEP** | `agent-mail` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'health_check' -> health_check returned status=ok -- the server answered; this proves the mailbox process is up, not that message delivery works |
| **KEEP** | `basic-memory` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'list_memory_projects' -> 2 projects, default=main |
| **KEEP** | `figma` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'whoami' -> handle + Full seat returned |
| **KEEP** | `github` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'get_me' -> authenticated login returned |
| **KEEP** | `huggingface` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'hf_whoami' -> status=anonymous (server answered) |

`S4 PASS` = stdio initialize+tools/list handshake.  `S4 PASS*` = a real in-session tool call instead (HTTP transport cannot be spawned).  Both count as S4 `call_verified`, which is their union: 21/23 rows.  Counts: {'DISABLE': 1, 'INVESTIGATE': 2, 'KEEP': 20}.

A `--` in the cost columns is **not measured**, never zero: cost comes from a stdio child and 7 of 23 rows have none to sample. Each such row states why in its own `liveness_basis`, and `assert_liveness_consistency()` refuses to write a null without one.
