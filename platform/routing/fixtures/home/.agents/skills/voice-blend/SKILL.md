---
name: voice-blend
description: Combine multiple voice profiles with weighted mixing to create hybrid voices. Use when user wants to mix or blend two or more writing styles together.
license: MIT
metadata:
  version: 1.0.0
  platforms:
  - all
  source: https://github.com/angelarose210/ghostwriter
  upstream_author: angelarose210
---

# voice-blend

Combine multiple voice profiles with weighted mixing to create hybrid voices.

## Triggers

Alternate expressions and non-obvious activations (primary phrases are matched automatically from the skill description):

- "70/30 [voice A]/[voice B]" -> ratio-based voice blending
- "blend voices" -> voice mixing

## Behavior

When triggered, this skill:

1. **Loads source voice profiles** from:
   - Built-in templates (`voices/templates/`)
   - Project voices (`.aiwg/voices/`)
   - User voices (`~/.config/aiwg/voices/`)

2. **Parses blend specification**:
   - Equal blend: "blend X and Y" -> 50%/50%
   - Weighted blend: "70% X, 30% Y" -> explicit weights
   - Multi-voice: "blend X, Y, and Z" -> equal thirds

3. **Interpolates dimensions**:
   - Weighted average of tone values (formality, confidence, etc.)
   - Merged vocabulary lists (union of prefer, intersection of avoid)
   - Dominant structure patterns from highest-weighted voice

4. **Generates hybrid profile** with clear lineage tracking

## Usage Examples

### Equal Blend
```
User: "Blend technical-authority and friendly-explainer"

Result: 50/50 blend
- formality: 0.45 (avg of 0.7 and 0.2)
- confidence: 0.8 (avg of 0.9 and 0.7)
- warmth: 0.55 (avg of 0.3 and 0.8)
- vocabulary: merged from both
```

### Weighted Blend
```
User: "80% executive-brief, 20% casual-conversational"

Result: Weighted blend
- formality: 0.7 (0.8*0.85 + 0.2*0.15)
- confidence: 0.86 (0.8*0.9 + 0.2*0.6)
- Dominant structure from executive-brief

### Multi-Voice Blend
### Blend Algorithm
### Dimension Interpolation
### Vocabulary Merging
### Structure Resolution
### Perspective Handling
### Output Format
### Output Location
