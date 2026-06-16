# Modus-operandi upgrades — 2026-06-15

Outcome of an ultracode research scan (5 dimensions × adversarial default-reject)
against the already-SOTA stack. 8 candidates survived; the user chose to
**implement #1–#7** and **defer #8**. This doc records what was wired and where.

## Implemented

### #1 — EvilGenie test-tamper diff-guard  *(hook, live)*
`~/.claude/hooks/test-tamper-guard/guard.py` — PreToolUse(Bash). On a `git commit`,
diffs staged **test** files vs base and WARNS (advisory) if assertions were
deleted/weakened, tests were `skip`/`xfail`/`.only`-disabled, trivial `assert True`
stubs added, or a whole test file deleted. Logs hits to the event-ledger as a
`failure` with the tamper signature as the falsifiable precondition. Fail-open,
non-nagging, warn-mode (does not block). Hardens the mandatory-TDD + 100%-coverage
gate against the reward-hacking class (arXiv:2511.21654).

### #2 — Working local SAST MCP  *(mcp, live)*
`~/.mcp.json` `semgrep` server **repointed** from the dead `semgrep-mcp.exe`
(package 0.9.0 — Semgrep deprecated it; it exposed only `deprecation_notice`) to
`npx -y mcp-server-semgrep`, which shells out to the working local semgrep CLI
(1.165). Real tools again: `scan_directory`, `list_rules`, `create_rule`,
`analyze_results`, `filter_results`, `export_results`, `compare_results`.
Upgrade path if wanted: Opengrep (LGPL fork) for the faster taint engine.

### #3 — Model fallback + safe-mode  *(launch flags, wrapped)*
`scripts/claude-autonomous.ps1` launches CC with `--fallback-model claude-sonnet-4-6`
for long unattended runs (keeps Ralph/autoresearch alive through a primary-model
blip). `--safe-mode` documented as the harness-vs-model bisector. These are
launch flags, not settings keys; ralph-loop replays in-session so the wrapper is
the correct injection point.

### #4 — Server-side context editing (`compact_20260112`)  *(documented, INERT today)*
This is an **Anthropic API / Agent-SDK** `context_management` param. The current
setup has **no raw-API/SDK runs** — everything goes through the `claude` CLI,
which already auto-compacts (autoCompact + harness-trim hook). So there is nothing
to wire it into right now. Ready-to-use snippet for when an SDK run is added:

```python
# claude-agent-sdk / anthropic messages.create(...)
context_management = {
    "edits": [{"type": "context_editing", "config": "compact_20260112"}]
}
# Do NOT enable the bundled Memory tool — basic-memory remains canonical.
```

### #5 — Claim/evidence ledger guard  *(hook, live, warn-mode)*
`~/.claude/hooks/claim-guard/{ledger-write.py,claim-check.py}`. PostToolUse(Bash)
records each command + exit to an NDJSON ledger (`%TEMP%\claude-claim-ledger\`);
Stop hook scans the final response for success-claims ("tests pass", "fixed",
"build green", …) and WARNS if a claim has no supporting ok=true command this
turn. Mechanizes the "NEVER self-certify" rule. `CLAIM_GUARD_MODE=warn` (default)
| `off`. Conservative: hedged/hypothetical claims do not trigger.

### #6 — Inbound tool-output injection guard  *(hook, live)*
`~/.claude/hooks/memory-guard/scan.py` — PostToolUse(`.*`). Scans output of
untrusted content tools (firecrawl/exa/scrapegraph/tavily/claude-in-chrome/
apify/markitdown/pdf-reader/WebFetch/WebSearch) for injection signals
(instruction-override, role-spoof, exfil, hidden/bidi unicode, base64-near-
imperative) BEFORE it enters context / the basic-memory vault. Allowlists
RE/security tools (ghidra/ida/frida/semgrep/sonar/…) so creds-shaped payloads
don't false-positive. Deterministic, fail-open, no LLM/network/vector store.

### #7 — Ensemble Semantic Entropy escalation gate  *(tool, built)*
`tools/ese-gate/ese_gate.py` — standalone CLI. Given N council candidates +
a test command, clusters them on execution-equivalence, computes normalized
entropy, and emits an `escalate` decision (high disagreement → deep lane; low →
apply plurality winner). Fail-safe: any error → escalate=true. Integration point
(council code edit is the user's to apply) documented in `tools/ese-gate/README.md`.
Validate the cost figures on-workload before tuning the threshold.

## Deferred

### #8 — OS-enforced Bash sandbox + Docker microVM
High-value but a real project (FS-access split, patch bubblewrap CVE-2026-25725,
perf). Deferred to its own scoped session. **Do not re-suggest unless asked.**
See basic-memory note `micro-vm-os-sandbox-for-autonomous-loops-deferred-…`.

## Null result
Skills/plugins: nothing net-new cleared the bar — the ~111-skill surface is
already well-curated. (One optional config flip, `--reload-skills`, was not
present as a flag in CC 2.1.177.)
