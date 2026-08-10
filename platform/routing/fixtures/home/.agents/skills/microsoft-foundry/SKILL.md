---
name: microsoft-foundry
description: "Deploy, evaluate, fine-tune, and manage Foundry agents end-to-end with azd: hosted agent scaffold/run/deploy, prompt agent create, batch eval, continuous eval, prompt optimizer, Agent Optimizer scaffold, agent.yaml, dataset curation from traces, model fine-tuning (SFT/DPO/RFT). USE FOR: azd ai agent, azd provision/deploy, deploy agent, hosted agent, create agent, add tool to agent, invoke agent, evaluate agent, continuous eval, continuous monitoring, agent CI/CD, optimize prompt, improve prompt, optimize agent instructions, agent optimizer, deploy model, Foundry project, RBAC, role assignment, permissions, quota, capacity, region, troubleshoot agent, deployment failure, AI Services, create Foundry resource, provision, knowledge index, customize deployment, onboard, availability, fine-tune, SFT, DPO, RFT, training-data, grader, distillation, fine-tuned model, large file upload. DO NOT USE FOR: Azure Functions, App Service, general Azure deploy (use azure-deploy), general Azure prep (use azure-prepare)."
license: MIT
metadata:
  author: Microsoft
  version: "1.2.4"
---

# Microsoft Foundry Skill

This skill helps developers work with Microsoft Foundry resources, covering model discovery and deployment, complete dev lifecycle of AI agent, evaluation workflows, and troubleshooting.

## Pre-Execution Requirements

Follow each applicable subsection below before starting its corresponding action or workflow.

### Dependency Check and Setup

**MANDATORY:** As the first step after this skill loads, run the dependency check and setup script below from this skill's root and wait for it to finish before continuing. The script checks first and installs only missing dependencies; it does not reinstall dependencies that are already available.

**You MUST complete this check before reading or entering any sub-skill, workflow, or workflow-specific reference.**

```bash
./scripts/check-and-setup-dependencies.sh     # macOS / Linux
./scripts/check-and-setup-dependencies.ps1    # Windows (pwsh)
```

Strictly follow the script output for subsequent actions.

### Workflow Guidance

**MANDATORY:** Before executing ANY workflow-specific steps, you MUST read the corresponding sub-skill document. Do not call workflow-specific MCP tools for a workflow without reading its skill document. This applies even if you already know the MCP tool parameters — the skill document contains required workflow steps, pre-checks, and validation logic that must be followed. This rule applies on every new user message that triggers a different workflow, even if the skill is already loaded.

### Foundry MCP
### azd
### Sub-Skills
### Infrastructure Lifecycle
### Agent Development Lifecycle
### Agent: .foundry Workspace Standard
### Agent: Setup References
### Agent: Common Project Context Resolution
### Step 1: Discover Agent Roots and azd Context
### Step 2: Resolve Environment and Deployment Context
