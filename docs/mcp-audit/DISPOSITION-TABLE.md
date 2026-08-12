| disposition | server | S1 config | S2 host | S3 mounted | S4 real call | tools | name B | schema B | evidence |
|---|---|---|---|---|---|---|---|---|---|
| **DISABLE** | `searxng` | disabled | Connected | yes | PASS | 4 | 77 | 5640 | exact set arithmetic: all 4 tool names are a strict subset of search-hub's surface, 0 unique -- nothing becomes unreachable |
| **INVESTIGATE** | `brightdata` | pending-approval | FAILED | yes | -- | -- | -- | -- | HTTP transport: no stdio command to spawn, and no real call was made (metered third-party API -- a real call bills the owner's account) |
| **INVESTIGATE** | `deepwiki` | enabled | Connected | yes | -- | -- | -- | -- | HTTP transport: no stdio command to spawn, and no real call was made (live network call against a third-party AI service) |
| **KEEP** | `cloud-hub` | enabled | Connected | yes | PASS | 424 | 6998 | 321053 | real initialize+tools/list returned 424 tools in 1806ms |
| **KEEP** | `search-hub` | enabled | Connected | yes | PASS | 68 | 1276 | 105831 | real initialize+tools/list returned 68 tools in 1075ms |
| **KEEP** | `paper-search` | enabled | Connected | yes | PASS | 57 | 866 | 43457 | real initialize+tools/list returned 57 tools in 15195ms |
| **KEEP** | `chrome-devtools` | disabled | Connected | yes | PASS | 29 | 378 | 21971 | real initialize+tools/list returned 29 tools in 42345ms |
| **KEEP** | `playwright` | enabled | Connected | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 37325ms |
| **KEEP** | `playwright-cdp` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 29409ms |
| **KEEP** | `playwright-extension` | pending-approval | FAILED | yes | PASS | 24 | 410 | 18441 | real initialize+tools/list returned 24 tools in 19207ms |
| **KEEP** | `angr` | disabled | Connected | yes | PASS | 14 | 189 | 8196 | real initialize+tools/list returned 14 tools in 91343ms |
| **KEEP** | `frida-mcp` | enabled | Connected | yes | PASS | 13 | 211 | 6091 | real initialize+tools/list returned 13 tools in 6767ms |
| **KEEP** | `repomix` | enabled | Connected | yes | PASS | 8 | 154 | 18150 | real initialize+tools/list returned 8 tools in 19328ms |
| **KEEP** | `scholarly-access` | enabled | Connected | yes | PASS | 8 | 144 | 4707 | real initialize+tools/list returned 8 tools in 7326ms |
| **KEEP** | `qlty` | enabled | Connected | yes | PASS | 5 | 67 | 3013 | real initialize+tools/list returned 5 tools in 3370ms |
| **KEEP** | `codex` | enabled | Connected | yes | PASS | 2 | 16 | 2340 | real initialize+tools/list returned 2 tools in 15165ms |
| **KEEP** | `context7` | disabled | Connected | yes | PASS | 2 | 28 | 4867 | real initialize+tools/list returned 2 tools in 39044ms |
| **KEEP** | `claude-code-mcp` | disabled | Connected | yes | PASS | 1 | 11 | 2594 | real initialize+tools/list returned 1 tools in 54938ms |
| **KEEP** | `agent-mail` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'health_check' -> status=ok |
| **KEEP** | `basic-memory` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'list_memory_projects' -> 2 projects, default=main |
| **KEEP** | `figma` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'whoami' -> handle + Full seat returned |
| **KEEP** | `github` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'get_me' -> authenticated login returned |
| **KEEP** | `huggingface` | enabled | Connected | yes | PASS* | -- | -- | -- | real in-session call 'hf_whoami' -> status=anonymous (server answered) |

`S4 PASS*` = verified by a real in-session tool call rather than a stdio handshake (HTTP transport cannot be spawned).  Counts: {'DISABLE': 1, 'INVESTIGATE': 2, 'KEEP': 20}.
