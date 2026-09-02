# Runbook: how to run session-transcript-normalizer

We need a workflow named session-transcript-normalizer to be implemented.

workflow id: session-transcript-normalizer

Steps:
1. Load the raw transcript
2. Strip tool XML and collapse duplicate turns
3. Emit a canonical JSONL row per utterance

How to create the operator copy: check this runbook into docs/.
