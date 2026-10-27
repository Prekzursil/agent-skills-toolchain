---
name: voice-analyze
description: Reverse-engineer voice profiles from sample content by analyzing writing patterns. Use when user pastes writing samples and wants to extract their style.
license: MIT
metadata:
  version: 1.0.0
  platforms:
  - all
  source: https://github.com/angelarose210/ghostwriter
  upstream_author: angelarose210
---

# voice-analyze

Reverse-engineer voice profiles from sample content by analyzing writing patterns. Detects and flags AI writing tells so the resulting profile produces human-sounding output.

## Triggers

Alternate expressions and non-obvious activations (primary phrases are matched automatically from the skill description):

- "voice fingerprint" -> voice profile extraction
- "what's my writing style" -> voice analysis

## Behavior

When triggered, this skill:

1. **Analyzes text samples** for:
   - Sentence structure and length patterns
   - Vocabulary sophistication and domain
   - Tone markers (formality, confidence, warmth)
   - Structural patterns (lists, examples, questions)
   - Perspective and voice choices

2. **Extracts measurable features**:
   - Average sentence length
   - Vocabulary complexity (syllables, word length)
   - Contraction usage
   - Personal pronoun frequency
   - Question density
   - List/bullet usage

3. **Scans for AI writing tells** (see `../voice-apply/references/ai-tells.md`):
   - Flags any banned vocabulary found in the sample (verbs, adjectives, nouns, adverbs from the tells list)
   - Detects banned sentence structures: "It's not X, it's Y" negation patterns, self-posed questions answered immediately, anaphora abuse, present participle trailing clauses
   - Measures em dash frequency (AI models use ~10x more than human writers)
   - Checks for uniform sentence length clustering (the "burstiness problem": AI clusters at 15-20 words, humans swing from 3-word fragments to 40-word sprawls)

### Usage Examples
### Analyze Existing Documentation
### Match Brand Voice
### Capture Personal Style
### Analysis Methodology
### Feature Extraction
### AI Tells Detection Pass
### Dimension Calibration
### Vocabulary Extraction
### Output Format
### Integration
