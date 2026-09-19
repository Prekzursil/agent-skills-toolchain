# Handoff: bare name first vs skill search-first

Date: 2026-09-02
Status: complete
Artifact also at: C:\Users\Prekzursil\.agents\state\harness\first-vs-search-first_2026-09-02.md

## Verdict

The name first is not a separate estate skill, slash command, or product.
The matching installed unit is the skill search-first (ECC, research-before-coding).
No inspected file defines first as an alias of search-first.
Calling first "only shorthand" is not a documented mapping.

## Missing first unit (two probes)

Read miss:
- C:\Users\Prekzursil\.agents\skills\first\SKILL.md does not exist
- C:\Users\Prekzursil\.claude\commands\first.md does not exist
- C:\Users\Prekzursil\.claude\skills\first\SKILL.md does not exist
- C:\Users\Prekzursil\.claude\commands\search-first.md does not exist

Independent inventory:
- C:\Users\Prekzursil\.claude\commands\ listing has no first.md
- grep name: first over skill SKILL.md files: 0 hits
- grep "name": "first" in DEPLOYED-MANIFEST.json: 0 hits
- Control: grep "name": "search-first" hits DEPLOYED-MANIFEST.json line 483

## search-first is deployed

C:\Users\Prekzursil\.agents\skills\DEPLOYED-MANIFEST.json lines 482-486:
name search-first, origin ECC, lane external, installs_hook false

C:\Users\Prekzursil\.agents\skills\search-first\SKILL.md frontmatter:
name: search-first
description: Research-before-coding workflow. Search for existing tools, libraries, and patterns before writing custom code. Invokes the researcher agent.
origin: ECC
H1: /search-first — Research Before You Code

Same file copied to C:\Users\Prekzursil\.claude\skills\search-first\SKILL.md

C:\Users\Prekzursil\.agents\skills-index.md line 259:
search-first — Research-before-coding workflow.

C:\Users\Prekzursil\.agents\skills\SKILLS-MANIFEST.md has a search-first row and no first row.

C:\Users\Prekzursil\.claude\capacity-upgrade-2026-07-24\inventory.json lines 2104-2111:
key search-first, dir search-first, name search-first
grep "first": { in that file: 0 hits

C:\Users\Prekzursil\.agents\skills\research-ops\SKILL.md lines 21-22:
search-first — SEPARATE domain (research-before-coding). Uses the full hyphenated name.

H1 /search-first is a skill slash-style title. There is no commands/search-first.md.

## Weak collisions

search-first SKILL.md line 64 Quick Mode: rg through relevant modules/tests first (English adverb)
secsearch SKILL.md line 3: Use FIRST for any cross-source security/pentest/red-team lookup (prefer secsearch)
simplest-probe-first is a different skill
https://www.first.org/about/ quote: FIRST is the Forum of Incident Response and Security Teams.

## Six claims

1. No local skill or slash-command file named first at the two canonical paths.
2. DEPLOYED-MANIFEST.json registers search-first (ECC, external) and not first.
3. search-first is a real ECC skill titled /search-first — Research Before You Code.
4. search-first is not a .claude/commands file; only the skill directory exists.
5. Cited first strings in local skill text are English or another skill instruction.
6. FIRST.org is a CSIRT membership organization, not this harness unit.

## Uncertainties

No inspected file states that first is an alias of search-first.
Runtime slash-command resolution of /first was not executed.
Semantic-router meta.json is a single 2026-06-29 line; isolated invoke row not extracted.
Products named First outside this estate were not exhaustively surveyed beyond FIRST.org and local inventories.
