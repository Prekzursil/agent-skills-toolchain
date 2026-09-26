---
title: qwythos-9b modal h100 deployment 2026-09-04
type: report
permalink: main/decisions/qwythos-9b-modal-h100-deployment-2026-09-04
tags:
- modal
- qwythos
- vllm
- h100
- deployment
- inference
---

# Qwythos-9B Modal H100 deployment 2026-09-04

- [fact] `empero-ai/Qwythos-9B-Claude-Mythos-5-1M` (Qwen3.5-9B, native 262,144 ctx; "1M" = YaRN extrapolation, publisher-validated only to ~137k) is served on Modal workspace `florineldanciu4`, app `qwythos-9b-vllm2`, endpoint `https://florineldanciu4--qwythos-9b-vllm2-server.us-east.modal.direct/v1` (Bearer auth via Modal secret `qwythos-vllm-key` → env `VLLM_API_KEY`).
- [fact] Engine: vLLM 0.28.0 on CUDA devel base (NOT the vllm docker image — its entrypoint hijacks Modal bootstrap and wedges `web_server` routing), `@app.server` flash-service pattern with `unauthenticated=True`, flags `--enable-auto-tool-choice --tool-call-parser qwen3_xml --reasoning-parser qwen3 --max-model-len 262144 --gpu-memory-utilization 0.92`. Parser verified empirically: model emits Qwen3-Coder XML tool dialect (hermes failed, qwen3_xml produces structured tool_calls).
- [fact] Verified end-to-end: 150,055-token prompt 200 OK, structured tool_calls with finish_reason=tool_calls, reasoning field separated, 401 without key. Scales to zero 5 min after last request; wake-on-request ~4 min (~$0.26/boot). H100 $3.95/hr warm.
- [fact] Weights cached once in Modal Volume `qwythos-model-cache` (18.8 GB, single copy). Deploy script: `C:\Users\Prekzursil\.agents\scripts\qwythos_modal_serve.py`. ZCode provider entry "Modal Qwythos H100" in `v2/config.json` (context 262144 / output 32768). Fallbacks: Featherless hosted (hard 32,768 cap — proven by probe; root cause of earlier bad_requests: TUI turns serialize ~98K tokens, 75K of which is 227 tool schemas) and local ollama `qwythos-9b` Q6_K at 64K.
- [warning] florineldanciu4 credits were **$29.93** (~7.5 warm hours) with **3 overdue invoices** — Modal suspends unpaid workspaces; endpoint dies if unsettled. Controls: `modal app stop qwythos-9b-vllm2`, `modal app logs qwythos-9b-vllm2`.
- [decision] Modal account selection: deploy initially landed on `florineldanciu4` via machine-wide `MODAL_TOKEN_ID` env var overriding the toml-active `mariusvisalon70`; owner confirmed florineldanciu4 is his account, deployment stayed there. `.modal.toml` holds 9 workspace profiles (prekzursil*, mariusvisalon70, realprekzursil = owner; florineldanciu4/ovido4/darias-grama/andreivisalon2002 = used per owner's word only).
- Related: [[incident-agents-md-policy-inversion-forensic-attribution-2026-09-03]] (the D:\bolt AWS credential campaign, 10 refusals, and why the line holds). Full session report: `C:\Users\Prekzursil\.agents\SESSION-REPORT-AWS-CURSOR-QWYTHOS_2026-09-04.md`.