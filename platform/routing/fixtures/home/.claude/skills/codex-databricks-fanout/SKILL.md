---
name: codex-databricks-fanout
description: Use when fanning out Codex CLI agents onto Databricks — running many parallel Codex/LLM work units on job clusters, scaling past a local RAM ceiling, or deciding between Databricks / local / Modal / RunPod for a large agent fan-out. Carries the measured constraints from a 608-unit production run + a 48-unit auth-research re-prove so a session does not re-derive them wrong.
---

# Codex fan-out on Databricks

Everything below was **measured on 2026-07-19** on workspace `bolt-datascience`
(`costin.ionescu@bolt.eu` / profile DEFAULT). Facts marked MEASURED are not to be
re-litigated from first principles — a session reasoning from scratch about this
gets the binding constraint wrong (see §1).

## 1. The constraint everyone guesses wrong

A session planning this will typically assert:

> *"Databricks is Spark/Jobs, not Codex CLI hosts. Codex OAuth + auth.json must NOT fan out to N
> workers — that's the dual-writer failure mode."*

**Both halves are wrong as stated.**

**Databricks job nodes host Codex CLI fine.** The runtime is ordinary Linux. You install
node + `@openai/codex` (or the official tarball) and run `codex exec`. It is not
*Spark-native*, but "not a Codex host" is false — **608 units** (mega-audit) and a
**48-unit auth-research re-prove (run 343617464274709)** completed this way.

**One shared `auth.json` served 180 concurrent Codex processes on one node with zero auth
corruption.** MEASURED, batch-01. Of 180, exactly 120 failed and **every single failure was
`429 Too Many Requests — exceeded retry limit`**, all dying in a 37–41s band. They fired at t=0,
hit the same rate window, burned codex's internal retries together, and gave up together. The 60
survivors were pristine. The node still had **228.9 GB free**.

That is a **thundering herd against the API rate limit**, not a capacity problem and not an auth
race. The real binding constraint at high fan-out is **arrival rate**, and the fix is a stagger:

### What is NOT proven (do not overclaim)
### 2. Account-level facts (MEASURED)
### Required submit shape (copy this)
### 3. Batching is mandatory
### 4. Classify units before dispatch
### 5. Getting results back
### 6. Completion is an AND-gate, never an exit code
### 7. Choosing the execution model
### 8. Pre-flight checklist
### 9. Harness paths (this workspace)
