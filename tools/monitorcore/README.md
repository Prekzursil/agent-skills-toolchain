# monitorcore

Shared monitoring + export core for the unified monitoring platform (the 11-PR
roadmap; PR-A shipped `wfmon export`). This package holds the domain-neutral
building blocks that every monitor adapter reuses, so a new monitor gets
status / notify / export "for free" by implementing one contract.

## What lands here

- **redaction** (`redact`) — fail-closed, strict-by-default secret + home-path masking.
- **text-safety** (`textsafe`) — ANSI-strip, HTML-escape, safe fences, UTF-8-safe truncation.
- **timeline IR** (`timeline`) — schema-agnostic transcript event model + tool-call pairing.
- **PDF ladder** (`pdf`) — feature-detected engine ladder (Typst → Playwright → headless → HTML).
- **generic render layer** (`report_doc`, `render_md`, `render_html`) — a thin
  `ReportDoc{blocks}` document-IR + generic Markdown/HTML renderers every adapter
  can target.
- **the contract** (`contract`) — `MonitorSource`/`Snapshot`: a typed, per-adapter
  `poll → Snapshot` that never throws, plus native render / export / headline / alert.
- **agent primitives** (`agent_tail`, watchdog, discovery, spawn) — vendored from the
  retired `agent-monitor` tool.
- **codex primitives** (`codex_tail`, `codex_source`) — the OpenAI Codex thread domain
  layer (relay-stream + `~/.codex` rollout tailers with MANDATORY redaction at ingest,
  the `mon codexmon` live board) plus `CodexSource`, the first in-package
  `MonitorSource` adapter (`codexmon`).

## Two hard rules

1. **Stdlib-light at runtime.** `dependencies = []`. monitorcore is *vendored*
   (copied) into consuming skills, which run under a plain Python; a mandatory
   third-party import would `ImportError` the skill. Heavy engines (PDF) are
   feature-detected and optional; `monitors.toml` is read with stdlib `tomllib`.
2. **Vendored copy stays in lockstep.** The importable `monitorcore/` package is
   copied into each consuming skill (e.g. `skills/workflow-monitor/monitorcore/`)
   so `import monitorcore` resolves after `sync-skills.ps1` deploys the skill.
   `tools/monitorcore/` is the single CI-gated source of truth; a CI drift check
   fails if the vendored copy diverges. Re-copy the package into the skill in the
   same commit whenever you change it here.

## Dev

```bash
pip install -e ".[dev]"
pytest --cov=monitorcore --cov-branch --cov-report=term-missing --cov-fail-under=100
basedpyright monitorcore
```

100% line + branch coverage is enforced in CI (`gate-tests-coverage monitorcore`),
with reasoned `# pragma: no cover -- <reason>` only for genuinely-untestable
syscall boundaries (mirrors taskwatch_monitor's `omit`).
