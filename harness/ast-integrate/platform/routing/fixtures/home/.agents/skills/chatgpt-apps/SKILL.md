---
name: chatgpt-apps
description: Build, scaffold, refactor, and troubleshoot ChatGPT Apps SDK applications that combine an MCP server and widget UI. Use when Codex needs to design tools, register UI resources, wire the MCP Apps bridge or ChatGPT compatibility APIs, apply Apps SDK metadata or CSP or domain settings, or produce a docs-aligned project scaffold. Prefer a docs-first workflow by invoking the openai-docs skill or OpenAI developer docs MCP tools before generating code.
---

# ChatGPT Apps

## Overview

Scaffold ChatGPT Apps SDK implementations with a docs-first, example-first workflow, then generate code that follows current Apps SDK and MCP Apps bridge patterns.

Use this skill to produce:

- A primary app-archetype classification and repo-shape decision
- A tool plan (names, schemas, annotations, outputs)
- An upstream starting-point recommendation (official example, ext-apps example, or local fallback scaffold)
- An MCP server scaffold (resource registration, tool handlers, metadata)
- A widget scaffold (MCP Apps bridge first, `window.openai` compatibility/extensions second)
- A reusable Node + `@modelcontextprotocol/ext-apps` starter scaffold for low-dependency fallbacks
- A validation report against the minimum working repo contract
- Local dev and connector setup steps
- A short stakeholder summary of what the app does (when requested)

## Mandatory Docs-First Workflow

Use `$openai-docs` first whenever building or changing a ChatGPT Apps SDK app.

1. Invoke `$openai-docs` (preferred) or call the OpenAI docs MCP server directly.
2. Fetch current Apps SDK docs before writing code, especially (baseline pages):
   - `apps-sdk/build/mcp-server`
   - `apps-sdk/build/chatgpt-ui`
   - `apps-sdk/build/examples`
   - `apps-sdk/plan/tools`
   - `apps-sdk/reference`
3. Fetch `apps-sdk/quickstart` when scaffolding a new app or generating a first-pass implementation, and check the official examples repo/page before inventing a scaffold from scratch.
4. Fetch deployment/submission docs when the task includes local ChatGPT testing, hosting, or public launch:

### Prompt Guidance
### Classify The App Before Choosing Code
### Default Starting-Point Order
### Build Workflow
### 0. Classify The App Archetype
### 1. Plan Tools Before Code
### 2. Choose an App Architecture
### 2a. Start From An Upstream Example When One Fits
### 2b. Use the Starter Script When a Low-Dependency Fallback Helps
### 3. Scaffold the MCP Server
### 4. Scaffold the Widget UI
