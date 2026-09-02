---
name: tooluniverse
description: Use when routing ToolUniverse life-science questions to the right specialized skill or verifying scientific facts against real databases.
---

# ToolUniverse Router

Route user questions to specialized skills. If no skill matches, use general strategies from [references/general-strategies.md](references/general-strategies.md).

## General Reasoning Protocols

When answering scientific questions:

1. **Look up, don't guess**: Use ToolUniverse tools to verify facts before answering.
2. **Compute, don't estimate**: Write and run Python code (via Bash) for any calculation. Never do mental math.
3. **Analyze, don't just retrieve**: When a question requires data analysis, download the data and run the analysis — don't just describe what you would do.
4. **Route to specialized skills**: Use the Routing Table below to find domain-specific reasoning protocols.

**You have full code execution.** For any analysis task (statistics, data wrangling, visualization), write Python and execute it. ToolUniverse tools find data and metadata; Python code does the analysis.

## Routing Workflow

1. **Extract keywords** from user's question
2. **Scan routing table** below for keyword matches
3. **Take action**:
   - **1 clear match** → invoke that skill NOW using the Skill tool
   - **Multiple matches** → ask user which they prefer (AskUserQuestion)
   - **No match** → use general strategies (load [references/general-strategies.md](references/general-strategies.md))
4. **If ambiguous** (e.g., "Tell me about aspirin") → ask user to clarify intent

**CRITICAL**: Actually INVOKE skills — don't describe them or show the routing table to the user.

### Routing Table
### 1. Data Retrieval
### 2. Research & Profiling
### 3. Clinical Decision Support
### 4. Discovery & Design
### 5. Genomics & Variant Analysis
### 6. Systems & Network Analysis
### 7. Screening & Functional Genomics
### 8. Clinical Trials & Study Design
### 9. Organism & Evolution
### 10. Specialized Biology
