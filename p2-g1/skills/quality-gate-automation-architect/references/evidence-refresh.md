# Evidence Refresh

Use this reference when the user wants the skill or its references to learn from recurring sessions, repos, and conversations over time.

## Repo policy

Store only derived summaries in this repo.

Do not commit:

- raw session exports
- raw conversation transcripts
- raw copied chat logs
- secrets or provider tokens

## Good evidence sources

- accepted PRs and merged workflow changes
- local `docs/plans/` and `docs/incubating/` notes
- derived memory summaries and rollout summaries
- workflow files, prompt files, and validation scripts from real repos
- postmortems for blocked or flaky automation runs

## Refresh workflow

1. Collect repeated tool patterns from recent work.
2. Normalize them into a reusable statement:
   - what failed
   - what signal exposed it
   - what guardrail or design change helped
3. Decide whether the insight belongs in:
   - the core skill
   - a tool-specific reference
   - an incubation note for a future skill
4. Add the note with a date and evidence class.
5. Keep the wording tool-neutral unless the behavior is vendor-specific.

## What to capture

- control-plane choices that worked or failed
- retry-loop stop rules
- provider quirks such as stale contexts or denominator traps
- useful prompt patterns
- validation stacks that increased confidence
- when a local lane was helpful versus harmful

## What not to capture

- one-off project narratives with no reusable lesson
- stale line numbers or temporary branch names unless the branch itself is the lesson
- private issue text copied verbatim when a short summary will do

## Entry template

Use this structure when adding derived notes:

```markdown
### YYYY-MM-DD - short topic
- Source class: memory | accepted PR | workflow review | repo postmortem
- Reusable lesson:
- Guardrail or prompt consequence:
- Scope notes:
```

## Promotion rule

If a pattern shows up repeatedly and changes behavior, move it from an incubation note into the relevant live reference file.
