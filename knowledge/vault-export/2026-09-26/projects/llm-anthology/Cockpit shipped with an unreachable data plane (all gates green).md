---
title: Cockpit shipped with an unreachable data plane (all gates green)
type: report
permalink: main/projects/llm-anthology/cockpit-shipped-with-an-unreachable-data-plane-all-gates-green
tags:
- llm-anthology
- cockpit
- verification
- green-but-broken
- tauri
---

# Cockpit shipped with an unreachable data plane

Found **2026-08-06** by launching the **installed NSIS build** (not the vite dev server) and
looking at the window. Every gate was green — 137 UI tests, 100% engine coverage, 0 axe
violations, working installer with a bundled CPython 3.12.12 — and the product could not be
used at all.

## The chain (each link grep-verified, not inferred)

- The cockpit needs a SQLite index file, attached via the Rust command
  `open_corpus(index_path)` — `cockpit/src-tauri/src/lib.rs:52`, registered at `:150`.
- **No UI calls it.** `open_corpus` appears in the TS layer only inside a *comment*
  (`cockpit/src/ipc/real.ts:14`, describing it as "a launch/settings concern outside this
  data surface"). `IpcClient` in `src/ipc/types.ts` never declared `openCorpus`. No file
  input, no dialog plugin, no drag-drop handler existed.
- **No RPC builds an index.** The sidecar exposes 28 methods (`sidecar.py:360-387`):
  health / corpus / graph / export / search / thread / conversation / research / metadata /
  dedup / maintenance. There is no `corpus.build` and no `index.*`.
- **No CLI builds one.** `llm-anthology` (`cli.py:20-51`) has only `claude`, `chatgpt`,
  `codex`, `gemini`, `demo` — all src→out_dir renderers.
- `loaders.load_corpus(sessions_root, index_path, codex_home)` (`loaders.py:261`) is the one
  function that builds an index (calls `index.build_index` at `:310`). Its only references
  outside tests are two docstrings (`metadata.py:21`, `sidecar.py:829`). **Zero production
  callers.**

Result on first launch: `no corpus attached: call open_corpus first` — an internal RPC
method name shown to an end user — with no way out of that state.

## Observations

- [root-cause] Work was decomposed per-surface (Rust commands, Python RPC, TS data
  adapters, UI panes) and each surface was independently gated to green. Nothing in that
  decomposition owned the seam BETWEEN surfaces, so the one path a real user takes was the
  only path never exercised. #decomposition-gap
- [method] The defect was invisible to every automated gate and took ~30 seconds to find by
  running the installed artifact and reading the screen. #run-the-artifact
- [detector-failure] A raw-byte scan of the NSIS installer for `python.exe` found nothing —
  but it also failed to find `LLM Anthology.exe`, which is definitely present (LZMA
  compression). Broken detector, not a finding; the engine's presence was instead confirmed
  from the installed directory (2010 files / 50.5 MB). #both-states
- [detector-failure] The ui-audit skill's own `wcag-contrast` rule
  (`layout_lint.mjs:247`) only evaluates an element whose OWN `background-color` has
  alpha > 0.1 and never walks the ancestor chain. Since transparent is the CSS default it
  skipped **22 of 30** text-bearing elements — its "0 contrast findings" measured a quarter
  of the UI. #single-signal
- [fix-in-progress] Added `tauri-plugin-dialog` + `dialog:default` capability,
  `openCorpus` on `IpcClient`/`realIpc`, and a native file picker, so an existing index can
  be opened. Whether corpus *ingest* belongs in the GUI (a `corpus.build` RPC) or in the
  CLI is a genuine product fork still open. #open-question

## Relations

- relates_to [[Agentic repair reliability]]
- exemplifies [[Single-signal verification]]
- part_of [[ai-sessions-render unification with codex-session-manager]]
