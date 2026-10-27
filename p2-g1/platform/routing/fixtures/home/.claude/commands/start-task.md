# Start Task

Determine task complexity and use appropriate workflow for efficient development.

## Usage

```text
/start-task <task-description>
```

## Router — pick the flow FIRST (deterministic; never make the user choose)

Match the task top-to-bottom; **first match wins**. ~75-80% route with no extra model call. A `*`-prefix means the user already scoped it → skip to the work.

| Task shape | Flow | Notes |
|---|---|---|
| read-only · <1 file · <3 tool-calls | **T0 just-do-it** (no gates) | the anti-over-engineering escape hatch — the router MUST be allowed to say "trivial" |
| single-file, bounded | **T1** `EnterPlanMode` | |
| ≥3 files AND a spec / Definition-of-Done | **T2 metaswarm gates** | design → plan → adversarial → coverage |
| known recurring pipeline (fixed steps) | **T3 Workflow DAG** | + per-phase checkpoint |
| RE-discovery OR novel / from-scratch design | **T4 parallel Task agents + council** | run the cheapest approach first (`simplest-probe-first`) |
