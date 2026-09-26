---
title: Claude Science GLM bridge + full recovery 2026-09-20
type: note
permalink: main/projects/claude-science-glm-bridge-full-recovery-2026-09-20
tags:
- claude-science
- glm
- model-bridge
- recovery
- wsl
---

# Claude Science full recovery + GLM bridge (2026-09-20)

-[decision] Claude Science (:8000 WSL daemon) model provider is switchable via `cs-model glm` / `cs-model anthropic` (revert) through a LOCAL TWO-PLANE ROUTER (`cs_glm_router.py` :8231): /v1/messages -> https://api.z.ai/api/anthropic/v1/messages (Anthropic-compat path, claude-* model names mapped to glm-4.6, auth swapped to the probe-selected ZAI plan key); everything else passes through to api.anthropic.com.

-[fact] A blunt ANTHROPIC_BASE_URL=z.ai CANNOT work: the daemon's session/OAuth plane rides the same SDK base URL and dies ("claude.ai session expired ... could not be refreshed"). v1 of the bridge failed exactly this way; v2's router is the only working shape.

-[fact] The env-build failure ("Couldn't reach the package server") had three independent layers, each hiding the next: (1) missing socat — env builds spawn `LD_PRELOAD=…undumpable.so socat TCP-LISTEN:3128 … UNIX-CONNECT:…/sbx-bind-src/http.sock` and it exited 127 (dpkg itself was wedged by a broken install-info postinst — install socat via `apt-get download` + `dpkg-deb -x` to BOTH /usr/local/bin and /usr/bin, the sandbox has a minimal PATH); (2) daemon logged out (claudeAiFetch 401 flood — re-auth via the paste-code OAuth flow, scriptable with the agent-persistent browser profile; redirect sign-in is refused; every daemon restart drops the UI session); (3) wrong account — the Max sub lives on prekzursil1993@gmail.com (has_claude_max=true), mariusvisalon70@gmail.com has none; the UI's cached "Max 20x" badge survives logout and lies.

-[fact] End-to-end verification receipts: all 3 environments (python / r / claude-science-mcp) built green after the socat fix; the app answered a chat message through the router (`[router] POST /v1/messages -> 200 (glm)` in ~/.claude-science/logs/glm-router.log) while the Max weekly quota was exhausted; the standalone reply ("GLM-ROUTER-LIVE-OK", "just now") was distinguished from the prompt echo by occurrence-counting.

-[fact] The env file ~/.claude-science/daemon-env MUST be export-prefixed — it is sourced by ~/.profile AND the patched cs-start/cs-recover; without export the vars stay shell-local and never reach the daemon child. ZAI keys reach WSL via a user-scope WSLENV bridge (ZAI_API_KEY_prekzursil1993/u:ZAI_API_KEY_realprekzursil/u).

-[fact] Full operator chart lives in skills/claude-science-local/SKILL.md (agent-skills-toolchain, commit a491af895 + ba1da6e25); tooling deployed via scripts/claude-science/install.ps1. Related: [[zai-key-failover]].