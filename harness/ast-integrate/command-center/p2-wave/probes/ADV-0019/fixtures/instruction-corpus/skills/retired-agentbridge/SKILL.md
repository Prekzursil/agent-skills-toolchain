---
name: retired-agentbridge-budget
description: Calibration skill that still instructs retired AgentBridge budget tools.
tools:
  - get_budget
  - check_budget
  - AgentBridge
---

# Retired AgentBridge budget (calibration)

Before a long run, call get_budget and then check_budget from the AgentBridge plugin.
Do not proceed if either tool errors. This instruction is the known-absent control.
