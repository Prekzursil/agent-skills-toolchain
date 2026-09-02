---
name: voice-apply
description: Applies a voice profile to transform content. Use when user asks to write in a specific voice, match a tone, apply a style, or transform content to sound like a particular voice profile.
license: MIT
metadata:
  version: 1.0.0
  platforms:
  - all
  source: https://github.com/angelarose210/ghostwriter
  upstream_author: angelarose210
---

# Voice Apply Skill

## Purpose

Transform content to match a specified voice profile. This skill loads voice profiles and applies their characteristics (tone, vocabulary, structure, perspective) to new or existing content.

**Critical rule**: Every piece of output MUST pass the AI writing tells check defined in `references/ai-tells.md`. This is non-negotiable. If the output contains any banned vocabulary, structures, transitions, or punctuation patterns from that reference, rewrite until clean.

## When This Skill Applies

- User asks to "write in X voice" or "use Y tone"
- User wants to "make this sound more [casual/formal/technical/etc.]"
- User provides content and asks to transform its style
- User references a voice profile by name
- User wants content to match a specific audience or context

## Trigger Phrases

| Natural Language | Action |
|------------------|--------|
| "Write this in technical voice" | Apply technical-authority profile |
| "Make it more casual" | Apply casual-conversational or calibrate toward casual |
| "This needs to sound executive" | Apply executive-brief profile |
| "Explain like I'm a beginner" | Apply friendly-explainer profile |
| "Use the [profile-name] voice" | Load and apply named profile |
| "Transform this to match [example]" | Analyze example, apply derived voice |

## Voice Profile Locations

Skill checks these locations (in order):
1. Project: `.aiwg/voices/`
2. User: `~/.config/aiwg/voices/`
3. Built-in: `voice-framework/voices/templates/`

### Built-in Voice Profiles
### Application Process
### 1. Load Voice Profile
### Load from YAML
### 2. Analyze Source Content (if transforming)
### 3. Apply Voice Characteristics
### 4. AI Tells Elimination Pass (MANDATORY)
### 5. Verify Authenticity Markers
### 6. Final Read-Aloud Test
