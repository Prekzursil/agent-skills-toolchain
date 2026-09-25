# MCP classification — the 47 unreachable servers (A-11 Track A2)

**Method:** `scripts/mcp_triage.py` + `scripts/mcp_probe.py` + a filesystem/listener pass, run as a
script rather than as 47 agents. Rung 1 — *does the entrypoint exist on disk* — is a filesystem
check, and it is what separates `package-gone` from `backend-on-demand`. No agent needed.

**Doctrine applied** (`rules/common/mcp-process-hygiene.md` DOCTRINE LOCK): reachability is a
SNAPSHOT, not a verdict. The burden of proof is on DELETION, never on keeping.

## Result

| action | count |
|---|---|
| KEEP | 22 |
| QUARANTINE | 16 |
| DELETE | 9 |

| label | count |
|---|---|
| backend-on-demand | 22 |
| unknown | 14 |
| package-gone | 11 |

## DELETE (9) — independently re-derived, 0 disputed

`verify9.py` re-derived these **without reusing** `classify47.py`'s helper, because a destructive
recommendation must not rest on one unvalidated function. All 9 confirmed, none disputed.

| server | configured command | check |
|---|---|---|
| `codex` | — | entrypoint absent |
| `github_cli` | `gh-cli-mcp` | `which` → None |
| `ocr-suite` | `D:/mcp-servers/abbyy-finereader-ocr-mcp/.venv/Scripts/python.exe` | absent |
| `openmm-md` | `D:/micromamba/envs/openmm-md/python.exe` | absent |
| `paper-search` | `D:/ReverseTools/mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe` | absent |
| `perplexity` | `D:/ReverseTools/mcp/perplexity-web-mcp/.venv/Scripts/pwm-mcp.exe` | absent |
| `postgres` | `docker run …` | `which(docker)` → None |
| `rdkit` | `C:/Users/Prekzursil/source/repos/rdkit-mcp-server/…` | absent |
| `sonarqube` | `docker run …` | `which(docker)` → None |

### These are not dead servers — they are HOME's config in the VM's file

The paths give it away: `D:/ReverseTools/`, `D:/mcp-servers/`, and
`C:/Users/**Prekzursil**/source/repos` — **capital P**, which is home's profile name; the VM is
lowercase `prekzursil`. Plus two `docker run` entries on a host with no Docker.

So this is the SAME root cause as the rest of the 2026-09-25 audit: **config copied between
machines without path reconciliation**. Deleting these removes entries that could never have run
here — it is not a capability loss. It also predicts the mirror-image problem on home, which is
untested.

⚠ **`codex` is in this list and that is a FINDING, not a deletion.** `~/CLAUDE.md` documents
`codex mcp-server` as the Layer-1 cross-vendor rail. Its configured entrypoint is absent, so that
integration is **broken**, not idle. Fix the rail; do not quietly delete the evidence.

## KEEP (22) — backend-on-demand

RE stack (`angr`, `apktool-mcp`, `cheatengine`, `frida-mcp`, `ghidra-mcp`, `hexstrike-ai`,
`ida-pro-mcp`, `jadx-mcp`) plus the loopback-hub and remote-URL entries (`McpHub` :24680,
`agent-mail` :18812, `biomni` :7870, `cloud-audit` :31118, `cve-mcp` :31111, `firecrawl` :31114,
`github-security` :31110, `nuclei` :31117, `osint` :31112, and the z.ai / GitHub / HuggingFace
HTTPS endpoints).

⚠ **HONEST GAP — the RE labels are weaker than they look.** `~/.local/opt/re-harness` **does not
exist on this VM** (`0 files`). The RE servers were labelled `backend-on-demand` from the owner's
memory note (`re_harness.md`), **not** from evidence on this machine. On this host there is
currently nothing to start them. They stay KEEP — the doctrine puts the burden on deletion — but
the justification is a remembered fact, not a local measurement. Resolving this is a prerequisite
before anyone prunes the RE set.

## QUARANTINE (16) — do NOT delete on a snapshot

`biomcp`, `breach-intel`, `claude-code-mcp`, `codacy`, `cursor-bridge`, `dbx-ai`, `docker`,
`elevenlabs`, `gitlab`, `mitmproxy`, `open-coscientist-lit-review`, `qdx-rush`,
`scholarly-access`, `semgrep`, `serena`, `zai-lane-a`.

Two sub-cases:
- **entrypoint EXISTS but exposed no tools** → by definition NOT `package-gone`. Something else is
  wrong (crash on start, bad credential, missing backend). Diagnose, do not delete.
- **package-manager launch, rung 1 indeterminate from path** (`npx`/`uvx` forms) → cannot be judged
  from the path alone.

`breach-intel` and `zai-lane-a` read `package-gone` here **but home runs them**, so they are
quarantined rather than deleted.

Note: `serena` also sits in `deniedMcpServers`, and `sci-hub` remains quarantined by the owner's
standing rule (⛔ never call `mcp__sci-hub__*`) — it is reachable, so it is not in this table, but
it is a deletion candidate on policy grounds rather than reachability.

## What is NOT decided here

This is a decision list. **Nothing was deleted and `.claude.json` was not edited** — 5 live
`claude.exe` sessions were measured writing that file three separate times tonight (17:39 → 17:50 →
17:52), so any write races them and MCP curation is load-bearing. The edit is queued, not skipped.

Instruments: `scripts/mcp_triage.py`, `scripts/mcp_probe.py`.
Evidence: run 2026-09-25 on VM OFFLOAD-W2025. Sibling: `knowledge/audits/ESTATE-AUDIT-2026-09-25.md`.
