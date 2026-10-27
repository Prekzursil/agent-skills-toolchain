---
name: ui-invariant-walk
description: Use when you want a property-based random-walk oracle that DRIVES a running web/Electron app and asserts UI invariants over a randomized command sequence — "no enabled button is a dead click" (an enabled, visible control must produce an observable state change) and "no route errors" (no navigation may reach an error route, throw an uncaught exception, or log a console error). Model-based testing via fast-check (`fc.commands` + `fc.asyncModelRun`) driving Playwright, with automatic shrinking to a minimal reproducing click/nav sequence. Ships as a SHADOW-mode advisory oracle (observe + log to a bounded rotating sink, never blocks CI or nags). Optionally deepen the existing Python Hypothesis suite with HypoFuzz nightly — but ONLY after verifying HypoFuzz's shifted license; the fast-check oracle ships regardless. NOT for pixel/design critique (use ui-audit), NOT for deterministic single-flow E2E (use Playwright directly).
metadata:
  origin: gem-hunt-2026-07-12
  item: ui-invariant-walk-oracle
  evidence: MASTER A-Tier2 (agentic-repair-2 #9, agentic-repair-1 #10); COUNCIL-VERDICT C5 shadow-first
---

# ui-invariant-walk Skill

A **model-based property test** that fans a *randomized* walk of Click / Navigate commands across a
running app and asserts UI **invariants** after every step. Where a hand-written E2E test proves one
scripted path, this oracle explores thousands of paths and, on failure, **shrinks** to the shortest
sequence that reproduces the violation.

**Skill location:** `~/.Codex/skills/ui-invariant-walk/`

Two invariants ship by default:

| ID | Invariant | Fails when |
|----|-----------|-----------|
| **INV1 DEAD_CLICK** | *No enabled button is a dead click.* | An **enabled + visible** control is clicked and produces **no observable state change** (no URL change, no DOM mutation, no network request, no dialog). |
| **INV2 ROUTE_ERROR** | *No route errors.* | After any step the app is on an **error route** (`/error`, `/404`, `/500`), logged a **`console.error`**, or threw an **uncaught page exception**. |

Both are cheap, app-agnostic, and catch a real class of agentic-repair regression: green unit tests +
a UI where a button silently does nothing or a route 500s. (Evidence: gem-hunt MASTER A-Tier2
agentic-repair-2 #9 / agentic-repair-1 #10 — "invariant random-walk UI oracle".)

---

## When to use

- After any UI change to **Reframe** (Electron+React), **momentstudio** (web), **bilbo-web**, WebCoder.
- As a **nightly / pre-PR** advisory sweep — surface dead controls and broken routes the scripted suite never visits.
- When a "tests pass" claim needs an **external, executable** UI check (see COUNCIL-VERDICT: the done-gate is spoofable; only executable/external evidence counts).

### Shadow-mode contract (COUNCIL-VERDICT C5 — MANDATORY)
### Install once
### The oracle — `oracle.mjs`
### Run it
### Start your app first (e.g. Reframe dev server / momentstudio), then:
### Proven mechanism (self-test)
### Optional: HypoFuzz nightly (Python) — LICENSE-GATED, do NOT wire blindly
### Anti-overfit / charter notes
