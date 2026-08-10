---
name: mle-workflow
description: Production machine-learning engineering workflow for data contracts, reproducible training, model evaluation, deployment, monitoring, and rollback. Use when building, reviewing, or hardening ML systems beyond one-off notebooks.
origin: ECC
---

# Machine Learning Engineering Workflow

Use this skill to turn model work into a production ML system with clear data contracts, repeatable training, measurable quality gates, deployable artifacts, and operational monitoring.

## When to Activate

- Planning or reviewing a production ML feature, model refresh, ranking system, recommender, classifier, embedding workflow, or forecasting pipeline
- Converting notebook code into a reusable training, evaluation, batch inference, or online inference pipeline
- Designing model promotion criteria, offline/online evals, experiment tracking, or rollback paths
- Debugging failures caused by data drift, label leakage, stale features, artifact mismatch, or inconsistent training and serving logic
- Adding model monitoring, canary rollout, shadow traffic, or post-deploy quality checks

## Scope Calibration

Use only the lanes that fit the system in front of you. This skill is useful for ranking, search, recommendations, classifiers, forecasting, embeddings, LLM workflows, anomaly detection, and batch analytics, but it should not force one architecture onto all of them.

- Do not assume every model has supervised labels, online serving, a feature store, PyTorch, GPUs, human review, A/B tests, or real-time feedback.
- Do not add heavyweight MLOps machinery when a data contract, baseline, eval script, and rollback note would make the change reviewable.
- Do make assumptions explicit when the project lacks labels, delayed outcomes, slice definitions, production traffic, or monitoring ownership.

### Related Skills
### Reuse the SWE Surface
### Ten MLE Task Simulations
### Iteration Compact
### Decision Brain
### Metric and Mistake Economics
### Data and Feature Hypotheses
### Error Analysis Loop
### Observation Ledger
### Core Workflow
### 1. Define the Prediction Contract
