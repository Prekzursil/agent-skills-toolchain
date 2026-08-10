---
name: voice-create
description: Generate custom voice profiles from natural language descriptions. Use when user wants to create a new writing voice from a description rather than from samples.
license: MIT
metadata:
  version: 1.0.0
  platforms:
  - all
  source: https://github.com/angelarose210/ghostwriter
  upstream_author: angelarose210
---

# voice-create

Generate custom voice profiles from natural language descriptions. Every generated profile includes AI tells avoidance rules by default.

## Triggers

Alternate expressions and non-obvious activations (primary phrases are matched automatically from the skill description):

- "make me sound like [reference]" -> reference-based voice creation
- "voice fingerprint" -> voice profile extraction from text

## Behavior

When triggered, this skill:

1. **Parses the description** to identify:
   - Target audience (developers, executives, general public)
   - Tone characteristics (formal/casual, confident/tentative, warm/clinical)
   - Domain context (technical, marketing, academic, conversational)
   - Any specific constraints or preferences mentioned

2. **Maps description to voice dimensions**:
   - Formality (0-1): casual <-> formal
   - Confidence (0-1): hedging <-> assertive
   - Warmth (0-1): clinical <-> friendly
   - Energy (0-1): calm <-> enthusiastic
   - Complexity (0-1): simple <-> sophisticated

3. **Generates vocabulary guidance**:
   - Preferred terms based on domain
   - Terms to avoid based on tone
   - Signature phrases that match the voice
   - **Always includes AI tells avoidance**: every generated profile's `vocabulary.avoid` list includes the full set of banned AI vocabulary from `../voice-apply/references/ai-tells.md`

4. **Creates structure patterns**:
   - Sentence length preferences
   - Paragraph structure
   - Use of lists, examples, analogies

### Usage Examples
### Technical Documentation Voice
### Friendly Tutorial Voice
### Executive Summary Voice
### Output Location
### Voice Generation Process
### Step 1: Dimension Calibration
### Step 2: Domain Detection
### Step 3: Vocabulary Generation
### Step 4: Structure Selection
### Step 5: Anti-Pattern Rules
