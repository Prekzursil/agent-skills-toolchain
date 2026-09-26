---
title: research Biomni phylo.bio access + comp-pharm fit 2026-07-07
type: note
permalink: main/research/research-biomni-phylo.bio-access-comp-pharm-fit-2026-07-07
tags:
- research-report
- high-confidence
- biomni
- phylo
- mcp
- firecrawl
- tavily
---

# Biomni for the phenibut program — access modalities + comp-pharm fit (2026-07-07)

**Confidence:** High on architecture/coverage; Medium on exact hosted counts. Providers: firecrawl, tavily, webfetch (exa out of credits). 20 unique sources, mostly tier-A primary.

## TL;DR (the answer)
- **Two Biomnis:** open-source `snap-stanford/Biomni` (Stanford SNAP lab, Apache-2.0) AND hosted commercial **"Biomni Lab"** by **Phylo, Inc.** (Kexin Huang CEO + Jure Leskovec; $13.5M seed a16z/Menlo/Anthropic; launched 2026-02-03).
- **The connected "Biomni Lab" MCP is a thin task-dispatch bridge** — verbatim scope: "starting and managing research tasks, streaming agent output in real time, uploading and managing project files, and retrieving analysis results." Tools: start_new_task, send_message, upload_file, list_result_files, wait_for_next_update, list/switch workspaces+projects, create_project. **NO `call_tool`** for the 150 internal tools.
- **Therefore:** MCP gives full access to what Biomni can DO (agent uses all tools on backend, driven by natural language) but NOT granular per-tool control. You do NOT need a second connector to use Biomni. Granular/private/offline → self-host Python SDK.

## Feature set (OSS Biomni-A1 / E1)
- Agent = CodeAct (LLM plans → retriever LLM selects tools/DBs → generates+executes Python/R/Bash → observe → loop). Default LLM = Claude (ANTHROPIC_API_KEY, default claude-sonnet-4). Also OpenAI/Azure/Gemini/Bedrock/Groq/Ollama.
- Environment E1 = **150 tools / 105 software / 59 databases** (VERIFIED multi-source; built from mining ~2500 bioRxiv papers × 25 subfields). DBs incl PDB, OpenTargets, ClinVar as NL-query functions.
- Version: A1+E1 released (OSS frozen Apr 2025, pip 0.0.8); E2 community build unreleased; no public A2.
- Self-host: setup.sh conda env (biomni_e1) + `pip install biomni`; ~11GB data lake auto-download (single-source [README], UNVERIFIED); Apache-2.0 (component licenses vary); agent runs LLM-generated code with full privileges → sandbox recommended.

## Hosted "Biomni Lab" (Phylo) adds over OSS
- Managed compute: 16 CPU / autoscaled ~1TB RAM / HPC cluster (single-source FAQ, UNVERIFIED).
- Bigger env: hosted claims 190+ tools / 120+ software / 70+ DBs (UNVERIFIED vendor FAQ); extra proprietary DBs: Consensus, COSMIC, Addgene.
- Workspace UI, reasoning traces, cross-session memory, "review" anti-hallucination agent, inline citations, export.
- Tiers: free research preview (rate-limited) + Enterprise (dedicated infra, custom agents, SSO/RBAC/SOC2 in progress). **Free tier data MAY train Phylo models unless opt out (Settings > Privacy).**

## Access-route coverage
| Route | Exposes | All features? |
|---|---|---|
| MCP (connected) | hosted agent task lifecycle only | No (agent uses everything though) |
| Web app biomni.phylo.bio | full IBE, traces, HPC/GPU, extra DBs | Yes (hosted) |
| Python SDK self-host | `from biomni.agent import A1; agent.go(...)`; all 150 tools direct; add_mcp; expose-as-MCP | Yes (granular) — only direct per-tool route |
| Hosted REST API | not publicly documented (Enterprise by request) | UNVERIFIED |

## Comp-pharm / phenibut fit (vs existing ToolUniverse+Schrödinger+Boltz-2+RDKit)
- **ADDITIVE:** genomics/variant/GWAS/eQTL (GABBR1/2, CACNA2D1/2) — stack lacks entirely; expression/scRNA-seq (brain-region GABA-B & α2δ subunits); **agentic multi-step hypothesis generation** (the real differentiator); drug repurposing.
- **REDUNDANT/weaker — do NOT route here:** ADMET/PK (have QikProp/ChEMBL/Boltz/RDKit/Inductive Bio); docking/FEP/structure (Biomni is NOT an FEP engine; Schrödinger FEP+ / Boltz-2 win); DB lookups (ChEMBL/OpenTargets/ClinVar already via ToolUniverse — Biomni only adds chaining).

## Recommended use
1. Use the connected MCP as-is; drive with NL tasks in the additive lane (GABBR1/2 + CACNA2D1/2 genetics/expression/eQTL → mechanistic hypotheses). Don't send docking/FEP/ADMET.
2. Self-host OSS if you want granular/private/offline (runs on own Claude key).
3. Opt out of training (or self-host) for unpublished mechanism work.

## Sources (tier A unless noted)
snap-stanford/Biomni README; biomni.stanford.edu; PMC12157518 (Biomni paper); bioRxiv 2025.05.30.656746; phylo.bio home/faq/blog(biomni-everywhere, fundraising); claude.com/connectors/biomni-lab (verbatim MCP scope); PRNewswire+SynBioBeta(B)+hyper.ai(B); AWS Bedrock AgentCore blog(B, DIY per-tool MCP); The Neuron(C, GA/Pro UNVERIFIED); smithery/mcp.directory skill listings(C).

## Open thread
Live Biomni MCP account probe pending — server was flapping during user's /login reconnect. Retry list_workspaces/list_projects + optionally run one test task in the additive lane.


## DECISION (2026-07-07) — Biomni's role + hybrid MCP pipeline
Live-tested the connector end-to-end: created project `Phenibut mechanism (GABA-B / α2δ)` (proj_8133132373), ran genetics task (sess_c40c36a741a1) at max effort → **27-file deliverable**: 32KB cited report `report_phenibut_mechanism.md`, 3 figures (brain heatmap, cell-type heatmap, variant–phenotype map), 15+ tables (GTEx median TPM, HPA, Siletti single-cell, GTEx brain eQTL, OpenTargets assoc, GWAS Catalog SNPs, CNS assoc). Good output → proves connector's 10 tools are NOT the ceiling (you drive the *agent*, it uses all 150 internally).

**Key finding:** ToolUniverse (already connected, 2526 tools) has the ENTIRE genetics layer as direct, individually-callable tools: GTEx_get_single_tissue_eqtls / _median_gene_expression / _multi_tissue_eqtls, gnomad_get_gene_constraints, gwas_get_variants_for_trait, OpenTargets_search_gwas_studies_by_disease, gather_gene_disease_associations (DisGeNET+OMIM+OpenTargets+GenCC+ClinVar), Monarch, HPA, Expression Atlas, eQTL Catalogue. So most of what Biomni's agent did is reproducible transparently via direct MCPs I drive.

**RULING — hybrid, 3 tiers:**
1. Biomni connector = zero-setup agentic, black-box, costs Biomni compute + training-privacy risk.
2. **Direct MCPs you already own (ToolUniverse-led) = the better everyday pipeline** — transparent, composable, in-repo, free. Run lanes 1/3/4 data-pulls here.
3. Self-host OSS + `expose_biomni_server` = all 150 Biomni tools as a real MCP on your own Claude key — the "better Biomni MCP"; only if unique skills become central.

**Go-forward:** STOP routing generic data-pulls (GTEx/HPA/OpenTargets/GWAS) through Biomni. Reserve Biomni ONLY for its ~5 genuinely-unique agentic skills: `gwas-to-function-twas`, `mendelian-randomization-twosamplemr`, LINCS L1000 connectivity, MOFA multi-omics, HPC structure-folding (Boltz-2/AlphaFold at scale). Everything else → direct MCPs. Next Biomni-worthy task = causal genetics (TWAS+MR) on GABBR1/2, CACNA2D1/2, KCTD12/16 — turns "associated" into "causal" for the manuscript pillar.

**Control limits (verified from MCP tool schemas):** effort (standard/fast/max), `@`-resources, and skills are WEB-UI-ONLY — the MCP exposes only tool_visibility/thinking_visibility/plan_mode/file_ids. So user sets effort/skills in UI; assistant dispatches + collects. Free-tier trains on session data unless opted out (Settings→Privacy).