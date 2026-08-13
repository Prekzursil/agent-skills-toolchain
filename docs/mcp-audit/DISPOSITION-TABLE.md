| disposition | server | S1 config | S2 host | S3 mounted | S4 real call | tools | name B | schema B | evidence |
|---|---|---|---|---|---|---|---|---|---|
| **DISABLE** | `searxng` | disabled | Connected | yes | PASS | 4 | 77 | 5640 | exact set arithmetic: all 4 tool names are a strict subset of search-hub's surface, 0 unique -- nothing becomes unreachable |
| **INVESTIGATE** | `brightdata` | pending-approval | FAILED | yes | -- | -- | -- | -- | HTTP transport: no stdio command to spawn, and no real call was made (metered third-party API -- a real call bills the owner's account) |
| **INVESTIGATE** | `deepwiki` | enabled | Connected | yes | -- | -- | -- | -- | HTTP transport: no stdio command to spawn, and no real call was made (live network call against a third-party AI service) |
| **KEEP** | `cloud-hub` | enabled | Connected | yes | PASS | 424 | 6998 | 321053 | real initialize+tools/list returned 424 tools in 230ms |
| **KEEP** | `search-hub` | enabled | Connected | yes | PASS | 68 | 1276 | 105831 | real initialize+tools/list returned 68 tools in 241ms |
| **KEEP** | `paper-search` | enabled | Connected | yes | PASS | 57 | 866 | 43457 | real initialize+tools/list returned 57 tools in 5315ms |
| **KEEP** | `chrome-devtools` | disabled | Connected | yes | PASS | 29 | 378 | 21971 | real initialize+tools/list returned 29 tools in 2953ms |
| **KEEP** | `playwright` | enabled | Connected | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 4470ms |
| **KEEP** | `playwright-cdp` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 5443ms |
| **KEEP** | `playwright-extension` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 4418ms |
| **KEEP** | `angr` | disabled | Connected | yes | PASS | 14 | 189 | 8196 | real initialize+tools/list returned 14 tools in 7768ms |
| **KEEP** | `frida-mcp` | enabled | Connected | yes | PASS | 13 | 211 | 6091 | real initialize+tools/list returned 13 tools in 4550ms |
| **KEEP** | `repomix` | enabled | Connected | yes | PASS | 8 | 154 | 18150 | real initialize+tools/list returned 8 tools in 3047ms |
| **KEEP** | `scholarly-access` | enabled | Connected | yes | PASS | 8 | 144 | 4707 | real initialize+tools/list returned 8 tools in 2846ms |
| **KEEP** | `qlty` | enabled | Connected | yes | PASS | 5 | 67 | 3013 | real initialize+tools/list returned 5 tools in 657ms |
| **KEEP** | `codex` | enabled | Connected | yes | PASS | 2 | 16 | 2340 | real initialize+tools/list returned 2 tools in 945ms |
| **KEEP** | `context7` | disabled | Connected | yes | PASS | 2 | 28 | 4867 | real initialize+tools/list returned 2 tools in 5698ms |
| **KEEP** | `claude-code-mcp` | disabled | Connected | yes | PASS | 1 | 11 | 2594 | real initialize+tools/list returned 1 tools in 3273ms |
| **KEEP** | `agent-mail` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'health_check' -> status=ok |
| **KEEP** | `basic-memory` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'list_memory_projects' -> 2 projects, default=main |
| **KEEP** | `figma` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'whoami' -> handle + Full seat returned |
| **KEEP** | `github` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'get_me' -> authenticated login returned |
| **KEEP** | `huggingface` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'hf_whoami' -> status=anonymous (server answered) |

`S4 PASS` = stdio initialize+tools/list handshake.  `S4 PASS*` = a real in-session tool call instead (HTTP transport cannot be spawned).  Both count as S4 `call_verified`, which is their union: 21/23 rows.  Counts: {'DISABLE': 1, 'INVESTIGATE': 2, 'KEEP': 20}.
