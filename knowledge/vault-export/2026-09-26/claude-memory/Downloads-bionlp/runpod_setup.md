---
name: RunPod GPU cloud setup for GRACE 2026
description: H100 SXM training infra replacing local RTX 4050 + Kaggle. MCP server
  installed, API key in ~/.claude.json.
type: reference
originSessionId: 7d868df4-f868-4a58-acac-c022173b11b4
permalink: main/claude-memory/downloads-bionlp/runpod-setup
---

**RunPod MCP server:** `@runpod/mcp-server@latest` via npx in `~/.claude.json`
**API key location:** `~/.claude.json` mcpServers.runpod.env.RUNPOD_API_KEY + `.env` (both gitignored)

**Target GPU:** H100 SXM 80GB @ $3.89/hr
- ~3 min per XLM-R-large training run (10 epochs, 350 cases)
- ~1.5 hrs for all 30 runs (ablations + HP sweep + relation classifier + student)
- ~$8 total cost for entire competition

**Fallback GPU:** A100 80GB @ $1.39/hr (if H100 unavailable)
- ~8 min per run, ~4 hrs total, ~$5.50

**How to use (after restart with MCP loaded):**
1. Use RunPod MCP tools to create a pod with PyTorch template
2. Create a network volume for persistent storage (checkpoints + data)
3. Upload grace/ package + downloaded_data/ to the pod
4. SSH into the pod and run training scripts
5. Download checkpoints + metrics.json when done
6. Stop the pod (billing stops at the millisecond)

**Important:**
- RunPod bills by the millisecond — stop pods when not training
- Network volumes persist across pod restarts and are billed separately (~$0.07/GB/month)
- PyTorch 2.x templates come pre-installed with CUDA — no setup needed
- The grace/ package needs to be pip-installed on the pod: `pip install -e /workspace/grace/`