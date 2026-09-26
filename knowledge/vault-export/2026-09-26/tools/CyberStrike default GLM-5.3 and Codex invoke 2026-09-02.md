---
title: CyberStrike default GLM-5.3 and Codex invoke 2026-09-02
type: note
permalink: main/tools/cyber-strike-default-glm-5.3-and-codex-invoke-2026-09-02
status: active
valid_as_of: '2026-09-02'
tags:
- cyberstrike
- glm
- codex
---

- [decision] CyberStrike default model is `hf-router/zai-org/GLM-5.3:zai-org`; small_model is `hf-router/zai-org/GLM-5.3-Flash:novita`. This supersedes the Gemini default from [[CyberStrike AI providers 2026-09-02]].
- [fact] Codex has no CyberStrike MCP registered. Codex does not speak CyberStrike ACP. The private `tools/mcp/cyberstrike-harness-bridge` reverse-control gateway is absent.
- [fact] From a Codex session, invoke CyberStrike as a CLI child: `cyberstrike run --format json --dir <dedicated-engagement-dir> "<authorized task>"`. Optional `--attach http://127.0.0.1:4096` if `cyberstrike serve`/`web` is already healthy. Do not use HOME or a source checkout as `--dir`.
- [fact] A live CyberStrike 1.1.15 process was healthy on `http://127.0.0.1:4096/global/health` at config change; that process may still hold the old default until restarted.
- relates_to [[CyberStrike]]
See also [[CyberStrike AI providers 2026-09-02]].

- [fact] Upgrade 04.09.2026: installed package is now **1.1.16** (was 1.1.15); no CyberStrike process was listening on `:4096` at upgrade time, so no stale 1.1.15 server needs restarting.
