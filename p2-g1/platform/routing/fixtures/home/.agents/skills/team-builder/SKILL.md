---
name: team-builder
description: Interactive agent picker for composing and dispatching parallel teams
origin: community
---

# Team Builder

Interactive menu for browsing and composing agent teams on demand. Works with flat or domain-subdirectory agent collections.

## When to Use

- You have multiple agent personas (markdown files) and want to pick which ones to use for a task
- You want to compose an ad-hoc team from different domains (e.g., Security + SEO + Architecture)
- You want to browse what agents are available before deciding

## Prerequisites

Agent files must be markdown files containing a persona prompt (identity, rules, workflow, deliverables). The first `# Heading` is used as the agent name and the first paragraph as the description.

Both flat and subdirectory layouts are supported:

**Subdirectory layout** — domain is inferred from the folder name:

```
agents/
├── engineering/
│   ├── security-engineer.md
│   └── software-architect.md
├── marketing/
│   └── seo-specialist.md
└── sales/
    └── discovery-coach.md
```

**Flat layout** — domain inferred from shared filename prefixes. A prefix counts as a domain when 2+ files share it. Files with unique prefixes go to "General". Note: the algorithm splits at the first `-`, so multi-word domains (e.g., `product-management`) should use the subdirectory layout instead:

```
agents/
├── engineering-security-engineer.md
├── engineering-software-architect.md
├── marketing-seo-specialist.md
├── marketing-content-strategist.md
├── sales-discovery-coach.md
└── sales-outbound-strategist.md
```

## Configuration

Agent directories are probed in order and results are merged:

### How It Works
### Step 1: Discover Available Agents
### Step 2: Present Domain Menu
### Step 3: Handle Selection
### Step 4: Spawn Agents in Parallel
### Step 5: Synthesize Results
### Rules
### Examples
### Security Engineer Findings
### SEO Specialist Findings
