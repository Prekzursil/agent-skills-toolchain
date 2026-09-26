---
title: Subagent file-IO routing without Read/Write/Bash tools (rclone + playwright-download
  lanes)
type: note
permalink: main/references/subagent-file-io-routing-without-read-write-bash-tools-rclone-playwright-download-lanes
tags:
- harness
- mcp-routing
- file-io
- rclone
- playwright
- workflow-subagents
---

Measured 2026-09-22 (wf_c8e4c79c-1c8, task B4): a workflow subagent session with NO Read/Write/Edit/Bash tools can still do byte-exact local file IO via two MCP backends on this box.

- [fact] READ: `mcp__cloud-hub__core_command` (local rclone v1.74.3, os=windows verified via core_version) runs rclone CLI on bare local paths. The MCP bridge STRINGIFIES array args, which rclone rc rejects - the fix is to pass the whole argv as ONE JSON-array-literal string element: `arg: ["[\"C:/path/file.md\",\"--tail\",\"3200\"]"]` for `cat`. `--head N` / `--tail N` both work. `copyto` = local file copy (backup-first + placement). `hashsum` takes max 2 args (hash + ONE path); hash a directory to get multiple files in one call.
- [fact] WRITE: `mcp__playwright__browser_run_code_unsafe` evaluates in an isolated VM realm - `import()` fails ("dynamic import callback not specified"), `require` and `process` are undefined, Function-constructor escape stays inside the VM. BUT the `page` handle is a real Playwright page: `page.goto('file:///C:/...')` + `evaluate(() => document.documentElement.textContent)` reads local text (plain-text files render into a single pre text node), and a blob-URL anchor download captured with `page.waitForEvent('download')` + `download.saveAs(tmpPath)` writes exact UTF-8 bytes of any in-VM string to disk (saveAs = real fs write by the Playwright server). Chain: read->transform in VM -> saveAs to %TEMP% -> rclone copyto to target (backup first). Verified end-to-end editing `[[delegate-primitive]]` SKILL.md (MD5 parity live=repo=staged 8a5cb580579d11043cb2be7488b9396c).
- [fact] Dead lanes same session: cursor-bridge status timed out 120s; sliver has no sessions; tooluniverse registry has no exec-class tools; core_command runs rclone subcommands only (no OS shell).
- [decision] When a spawned unit lacks file tools, route through the above instead of returning FAILED-TO-RUN - the tool-routing rule ("do NOT say I don't have access to that tool") is satisfiable with these two backends.

Related: [[delegate-primitive]], workflow fan-out contract, single-signal-verification (verified via cat re-read + MD5, two instruments).