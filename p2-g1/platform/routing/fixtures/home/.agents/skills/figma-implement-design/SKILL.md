---
name: "figma-implement-design"
description: Use when the user provides Figma URLs or node IDs and needs production-ready code with pixel-perfect 1:1 fidelity to the design, translating Figma components into project-convention code via the Figma MCP ; do NOT use for generic Figma data fetching or MCP setup (use figma) ; returns implemented component code matching Figma specs.
---


# Implement Design

## Overview

This skill provides a structured workflow for translating Figma designs into production-ready code with pixel-perfect accuracy. It ensures consistent integration with the Figma MCP server, proper use of design tokens, and 1:1 visual parity with designs.

## Prerequisites

- Figma MCP server must be connected and accessible
- User must provide a Figma URL in the format: `https://figma.com/design/:fileKey/:fileName?node-id=1-2`
  - `:fileKey` is the file key
  - `1-2` is the node ID (the specific component or frame to implement)
- **OR** when using `figma-desktop` MCP: User can select a node directly in the Figma desktop app (no URL required)
- Project should have an established design system or component library (preferred)

## Required Workflow

**Follow these steps in order. Do not skip steps.**

### Step 0: Set up Figma MCP (if not already configured)

If any MCP call fails because Figma MCP is not connected, pause and set it up:

1. Add the Figma MCP:
   - `codex mcp add figma --url https://mcp.figma.com/mcp`
2. Enable remote MCP client:
   - Set `[features].rmcp_client = true` in `config.toml` **or** run `codex --enable rmcp_client`
3. Log in with OAuth:
   - `codex mcp login figma`

After successful login, the user will have to restart codex. You should finish your answer and tell them so when they try again they can continue with Step 1.

### Step 1: Get Node ID

#### Option A: Parse from Figma URL

When the user provides a Figma URL, extract the file key and node ID to pass as arguments to MCP tools.

### Step 2: Fetch Design Context
### Step 3: Capture Visual Reference
### Step 4: Download Required Assets
### Step 5: Translate to Project Conventions
### Step 6: Achieve 1:1 Visual Parity
### Step 7: Validate Against Figma
### Implementation Rules
### Component Organization
