---
name: slop-check
description: Use when the user asks if text or an image is AI-generated, to clean AI artifacts or invisible characters, or to score readability (Flesch-Kincaid) via Slop or Not Pro on-device tools (macOS only) ; do NOT use for rewriting or humanizing text (use agentic-humanizer or humanizer) ; returns AI-detection verdict, cleaned text, or readability grade.
license: MIT
allowed-tools:
- Read
- Bash
metadata:
  version: 0.1.0
  compatibility: claude-code codex cursor gemini-cli opencode
  source: https://github.com/numen-tech/slopornot
  upstream_author: Numen Technologies
---

> **Windows note (vendored):** `slop-check` routes to the Slop or Not Pro on-device MCP / `slop` CLI, which is **macOS-only**. On Windows these AI-detection / readability calls will not resolve; the skill is vendored for completeness and cross-platform parity. To humanize text on Windows use `agentic-humanizer` (works standalone) or `humanizer`.

# Slop Check

One-shot access to Slop or Not Pro's on-device analysis. Detect AI text or
images, clean AI artifacts, or score readability, then report a clear
verdict. No interview, no loop.

**Slash command:** `/slop-check [paste text | file path | image path]`

## Critical rules

1. For `image-detect` and explicit `image-score`, MUST prefer the
   app-bundle CLI when the current client can run local shell commands. Use
   MCP for image operations only when CLI execution is unsupported or fails.
   For text, readability, cleanup, and status, try MCP before CLI.
2. MUST verify Pro with a real Pro-gated call. NEVER infer Pro from
   `slop_status` or `slop status`; both succeed for non-Pro users.
3. NEVER block on a structured-question tool. Resolve ambiguity with the
   Step 1 precedence rule and state the assumption, or emit the single
   plain-text input request. Plain text renders on every harness.
4. NEVER create symlinks, edit shell rc files, or otherwise modify PATH.
   Prefer the absolute app-bundle binary at
   `/Applications/Slop Or Not.app/Contents/MacOS/slop` whenever using the
   CLI. Detection, readability, cleanup, score, and status are output-only:

### Step 1: Identify the operation and input
### Step 2: Resolve a working backend
### Step 3: Run the operation
### Step 4: Present the result
### Step 5: Fallback when Slop or Not Pro is unavailable
### Examples
### Pointer files
