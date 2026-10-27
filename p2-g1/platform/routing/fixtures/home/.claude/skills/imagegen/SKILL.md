---
name: "imagegen"
description: "Use when the user asks to generate or edit images via the OpenAI Image API (for example: generate image, edit/inpaint/mask, background removal or replacement, transparent background, product shots, concept art, covers, or batch variants); run the bundled CLI (`scripts/image_gen.py`) and require `OPENAI_API_KEY` for live calls."
---


# Image Generation Skill

Generates or edits images for the current project (e.g., website assets, game assets, UI mockups, product mockups, wireframes, logo design, photorealistic images, infographics). Defaults to `gpt-image-1.5` and the OpenAI Image API, and prefers the bundled CLI for deterministic, reproducible runs.

## When to use
- Generate a new image (concept art, product shot, cover, website hero)
- Edit an existing image (inpainting, masked edits, lighting or weather transformations, background replacement, object removal, compositing, transparent background)
- Batch runs (many prompts, or many variants across prompts)

## Decision tree (generate vs edit vs batch)
- If the user provides an input image (or says “edit/retouch/inpaint/mask/translate/localize/change only X”) → **edit**
- Else if the user needs many different prompts/assets → **generate-batch**
- Else → **generate**

## Workflow
1. Decide intent: generate vs edit vs batch (see decision tree above).
2. Collect inputs up front: prompt(s), exact text (verbatim), constraints/avoid list, and any input image(s)/mask(s). For multi-image edits, label each input by index and role; for edits, list invariants explicitly.
3. If batch: write a temporary JSONL under tmp/ (one job per line), run once, then delete the JSONL.
4. Augment prompt into a short labeled spec (structure + constraints) without inventing new creative requirements.
5. Run the bundled CLI (`scripts/image_gen.py`) with sensible defaults (see references/cli.md).

### Temp and output conventions
### Dependencies (install if missing)
### Environment
### Defaults & rules
### Prompt augmentation
### Use-case taxonomy (exact slugs)
### Examples
### Generation example (hero image)
### Edit example (invariants)
### Prompting best practices (short list)
