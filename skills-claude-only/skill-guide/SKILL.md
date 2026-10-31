---
name: skill-guide
description: Explain how to create, organize, and maintain skills in .agents/skills
  when the user asks about skills.
permalink: dqverify-repo-20261013/skills-claude-only/skill-guide/skill
---

When asked about skills:

1. Explain required structure:
- One directory per skill under `.agents/skills`.
- A required `SKILL.md` file with YAML frontmatter.

2. Explain required frontmatter:
- `name`: short unique identifier.
- `description`: explicit trigger guidance for when the skill should be used.

3. Provide a minimal starter template and ask for:
- the task scope,
- expected input/output,
- success criteria.

4. Recommend progressive disclosure:
- keep `SKILL.md` concise,
- put large references/examples in separate files.

5. Suggest validation checklist:
- clear trigger description,
- deterministic steps,
- no secrets in skill files,
- tested with at least one real prompt.