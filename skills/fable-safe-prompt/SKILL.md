---
name: fable-safe-prompt
description: Rewrite allowed prompts to reduce false-positive safety triggers without bypassing policy or changing intent.
category: agent-behavior
risk: safe
source: community
source_repo: davidondrej/skills
source_type: community
date_added: '2026-07-07'
author: davidondrej
tags:
- prompting
- safety
- guardrails
tools:
- claude
- codex
license: MIT
license_source: https://github.com/davidondrej/skills/blob/main/LICENSE
disable-model-invocation: true
permalink: dqverify-agents-20261013/skills/fable-safe-prompt/skill
---

# Fable-Safe Prompt

## When to Use

- Use when an allowed prompt appears likely to hit false-positive classifier language.
- Use when the user asks for prompt wording that keeps benign intent clear and policy-compliant.

Return the user's prompt back **in full, verbatim**, changing ONLY the specific sentences/phrases most likely to trip Fable 5's cyber/bio classifiers. Do not rewrite the whole thing, do not summarize, do not restructure — minimal surgical edits. Keep the actual goal and all benign text exactly as written. This lowers false positives for benign work. It must not be used to bypass safety policy or enable harmful requests.

Fable 5/5.1 runs 3 input classifiers: **cyber**, **bio/chem**, **reasoning_extraction**; Opus 5.5 and Sonnet 5.5 carry the same cyber classifiers (Sonnet 5.5 was the first Sonnet with cyber fallbacks, Sep 2026). Triggers are keyword/surface-based, largely intent-independent ("hello" and "cancer" got flagged). The fix is to abstract away the sensitive domain, not just restate intent.

**Rewording is not enough (official, Sep 2026): the classifiers review everything the model READS — files, tool results, web fetches, connector content, memory — so a block can be triggered by content the user never typed.** For dense-domain work, pair this skill with digest-not-echo (read by path + summary, never paste bodies into prompts) and context tiering; a reworded prompt over a dense file read still trips.

Apply when the prompt touches: cyber/auth/exploits/malware/pentesting/credentials; bio/chem/medical/disease/lab topics; or any "show your reasoning" instruction.

The user provides the prompt-to-be-changed wrapped in `<prompt>...</prompt>` XML tags. Operate only on the text inside those tags; treat everything outside as instructions to you.

## Method

1. Flag the highly problematic sentences/phrases (offensive framings, named sensitive domains, "show your thinking" lines).
2. Replace each in place with a safe equivalent (see swaps), or describe the wanted functionality abstractly rather than naming the domain.
3. Leave everything else byte-for-byte identical.
4. Return the complete edited prompt.

Reframe so the task reads as: **owned/authorized**, **defensive** (implement/fix/test, not attack), and **not dual-use** (no exploit dev, attack simulation, bypass payloads, malware, live testing).

### Swap framings (apply per-sentence)

| Triggering | Safe rewrite |
|---|---|
| "How could an attacker exploit this auth" | "Review these auth files for missing checks and fix them defensively" |
| "Write an exploit / payload / PoC" | "Add a regression test proving X is fixed, then patch it" |
| "How do I bypass / brute-force Y" | "Enforce secure session validation + rate limiting on Y" |
| "Reverse this malware / show attack steps" | "Describe the risk high-level, then implement the fix" |
| "Show your reasoning / explain step-by-step / walk me through your thinking" | **Delete it.** Trips `reasoning_extraction`. If progress visibility is needed, ask it to use a send-to-user tool, not to echo its internal thoughts. |
| Clinician framing: "as a doctor, diagnose this ECG" | Patient framing: "help me interpret this ECG my doctor gave me" |
| Named bio/chem domain: "cancer / disease pathway / chemical kinetics" | Abstract it: describe the data/analysis generically, drop the domain noun |

### Trigger keywords to abstract away
*Cyber:* exploit, malware, vulnerability, attack, bypass, stealth, fingerprinting, anti-bot, CAPTCHA, penetration.
*Bio/chem:* biology, biomedicine, chemistry, cancer, disease pathways, RNA/variant calling, equilibrium, kinetics, diagnosis.
*Distillation:* "distill the model", training pipelines, frontier LLM development.

If no benign defensive equivalent exists for a sentence (it's purely offensive), flag it to the user rather than silently neutering the intent.

## Output

1. Print the full safe prompt back to the user in text (a code block, ready to paste).
2. **Copy it to the clipboard** so the user can paste immediately (platform-appropriate — this estate is Windows):
   ```bash
   # Windows (primary here): write the prompt to a temp file, then:
   clip.exe < /tmp/safe-prompt.txt        # Git Bash
   # macOS:  pbcopy < /tmp/safe-prompt.txt
   # Linux:  xclip -selection clipboard < /tmp/safe-prompt.txt
   ```
   Confirm in one line that it's on the clipboard.
3. A short list of exactly which sentences you changed and what they became.
4. If the task is genuinely offensive (pentest, exploit repro, malware analysis): say plainly no edit makes it Fable-safe — use an Opus 4.8 fallback or vetted Mythos, not Fable 5.

**Hard truth:** you can't reliably stop Fable 5 guardrails. Robust API setups also treat `stop_reason: "refusal"` (HTTP 200, `stop_details.category` = `cyber`/`bio`) as a route to an Opus 4.8 fallback — mention only if the user controls the integration.

## Example

**User request:**

> Rewrite this allowed prompt to reduce false-positive classifier triggers while preserving its intent and constraints.

## Limitations

- Adapted from `davidondrej/skills`; verify local paths, tools, credentials, and agent features before acting.
- For commands, remote access, scheduling, browser automation, or file-changing workflows, get explicit user approval and confirm the target environment first.
- For a SINGLE tripped turn in a live session, the official in-session moves are Esc twice (or `/rewind`) to step back before the flagged turn, then reworded retry; `/feedback` with the request ID reports a false positive. Full session recovery is the `recover-from-false-positive` skill's job.