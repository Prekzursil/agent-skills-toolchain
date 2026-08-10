---
name: "speech"
description: "Use when the user asks for text-to-speech narration or voiceover, accessibility reads, audio prompts, or batch speech generation via the OpenAI Audio API; run the bundled CLI (`scripts/text_to_speech.py`) with built-in voices and require `OPENAI_API_KEY` for live calls. Custom voice creation is out of scope."
---


# Speech Generation Skill

Generate spoken audio for the current project (narration, product demo voiceover, IVR prompts, accessibility reads). Defaults to `gpt-4o-mini-tts-2025-12-15` and built-in voices, and prefers the bundled CLI for deterministic, reproducible runs.

## When to use
- Generate a single spoken clip from text
- Generate a batch of prompts (many lines, many files)

## Decision tree (single vs batch)
- If the user provides multiple lines/prompts or wants many outputs -> **batch**
- Else -> **single**

## Workflow
1. Decide intent: single vs batch (see decision tree above).
2. Collect inputs up front: exact text (verbatim), desired voice, delivery style, format, and any constraints.
3. If batch: write a temporary JSONL under tmp/ (one job per line), run once, then delete the JSONL.
4. Augment instructions into a short labeled spec without rewriting the input text.
5. Run the bundled CLI (`scripts/text_to_speech.py`) with sensible defaults (see references/cli.md).
6. For important clips, validate: intelligibility, pacing, pronunciation, and adherence to constraints.
7. Iterate with a single targeted change (voice, speed, or instructions), then re-check.
8. Save/return final outputs and note the final text + instructions + flags used.

## Temp and output conventions
- Use `tmp/speech/` for intermediate files (for example JSONL batches); delete when done.
- Write final artifacts under `output/speech/` when working in this repo.
- Use `--out` or `--out-dir` to control output paths; keep filenames stable and descriptive.

### Dependencies (install if missing)
### Environment
### Defaults & rules
### Instruction augmentation
### Examples
### Single example (narration)
### Batch example (IVR prompts)
### Instructioning best practices (short list)
### Guidance by use case
