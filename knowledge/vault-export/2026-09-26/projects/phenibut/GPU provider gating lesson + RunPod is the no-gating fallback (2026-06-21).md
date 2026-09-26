---
title: GPU provider gating lesson + RunPod is the no-gating fallback (2026-06-21)
type: note
permalink: main/projects/phenibut/gpu-provider-gating-lesson-run-pod-is-the-no-gating-fallback-2026-06-21
tags:
- gpu
- cloud
- modal
- gcp
- vultr
- runpod
- gating
- fep
- phenibut
- checkpoint
---

# GPU provider gating lesson + RunPod fallback (2026-06-21)

Hunting GPU compute for the phenibut Schrodinger connected-map FEP (needs: free-ish, REAL multi-GPU single node for JobDJ Max:N, root to install the 13GB suite + portable .lic, multi-hour run). Hit a **new-account GPU GATING wall on all three credit-giving providers:**
- **Modal** ($30/mo credit): multi-GPU is FAKED in-container -> Schrodinger JobDJ stuck at `Max:1` despite the `processors:8 + gpgpu:0..7` hosts file. Single-GPU works but ~30h connected map > 24h fn timeout. Dead-end for multi-GPU. (see [[Schrodinger FEP+ on Modal — parallelize PER-EDGE, not in-container multi-GPU]])
- **GCP** ($300 trial): `GPUS_ALL_REGIONS` quota = **0**; trial accounts usually can't get a GPU quota bump. Billing fine, GPUs locked.
- **Vultr** ($250 trial): EVERY GPU plan (even the $0.07 fractional A40) returns `"Server add failed: Please open a support request for access to this product"`. New accounts have no GPU product access at all. (API also needs IP allowlist: Account->API->Access Control.)

**PATTERN:** free-trial credit <-> GPU gating. Self-serve GPU clouds (RunPod, Vast) don't gate but don't give trial credit.

**RunPod = the no-gating fallback (already keyed):** MCP `@runpod/mcp-server`, key in `~/.claude.json` mcpServers.runpod.env.RUNPOD_API_KEY. API auths (GraphQL `https://api.runpod.io/graphql?api_key=`). **Balance ~$0** (pay-as-you-go, no trial). Live prices (secure/community $/hr): L40S 48GB 0.99/0.79 · A100 PCIe 80GB 1.39/1.19 · A100 SXM 80GB 1.49/1.39 · H100 SXM 3.29/2.69. Multi-GPU pods (up to 8x) are REAL hardware -> the Schrodinger multi-GPU hosts file SHOULD give Max:8 (unlike Modal). Both FEP maps ~ $80-100 on 8xA100, or ~$20/map single-GPU. Needs a ~$30-50 top-up. Vultr key in chat -> ROTATE it.

A `gpu-trial-provider-sweep` Workflow (wf_063e1e9f-fe4) is sweeping ~40 providers for any no-gating FREE-trial option (Oracle OCI $300, Beam, Thunder, Nebius, SaladCloud, etc.) + adversarially verifying. Pending. See [[Migration to mariusvisalon70 (3rd Modal account) — in progress 2026-06-21]].
