---
title: upstream
type: note
permalink: dqverify-repo-20261013/skills/angr/references/upstream
---

# Upstream Notes

- Official docs: `https://docs.angr.io/`
- Common install path: `py -3 -m pip install --upgrade angr` inside a dedicated venv
- Minimal sanity check:
  - import angr in Python
  - load a small test binary with `angr.Project`
  - create a single entry state and verify exploration runs
- Keep angr scripts under version control when they become part of a repeatable workflow