---
title: INSTALL
type: note
permalink: dqverify-repo-20261013/skills/cv-studio/install
---

# cv-studio — install & engine setup

The skill (SKILL.md + references) rides the existing `~/.agents/skills` bus and needs **no new
runtime**. The one dependency is the ATS render engine, **RenderCV** (MIT), installed once into an
**isolated venv** so it never touches global Python.

## Why isolated (important)
`pip install "rendercv[full]"` pulls `typer>=0.25`, which **conflicts with `docling`** (needs
`<0.25`) already present in this box's global Python 3.14. Installing into a dedicated venv keeps
the owner's global environment intact. The skill's `cvstudio.py` auto-resolves the engine in this
order: `$CV_STUDIO_RENDERCV` → `~/.local/share/cv-studio/venv` → `~/.local/bin` (pipx) → PATH.

## One-time setup (pick one)

**A. Bundled script (recommended)** — creates the isolated venv + smoke-tests it:
```
# Windows (PowerShell 7)
pwsh ~/.agents/skills/cv-studio/scripts/setup.ps1
# POSIX / WSL
bash ~/.agents/skills/cv-studio/scripts/setup.sh
```

**B. pipx (also isolated):**
```
pipx install "rendercv[full]"
pipx inject rendercv pymupdf      # for the ATS self-check
# then: export CV_STUDIO_RENDERCV="$(command -v rendercv)"
```

**C. Manual venv:**
```
python -m venv ~/.local/share/cv-studio/venv
~/.local/share/cv-studio/venv/Scripts/python -m pip install "rendercv[full]" pymupdf   # POSIX: bin/python
```

## Verify
```
PY=~/.local/share/cv-studio/venv/Scripts/python           # POSIX: .../bin/python
$PY ~/.agents/skills/cv-studio/scripts/cvstudio.py build \
    ~/.agents/skills/cv-studio/assets/sample-profile.yaml --out /tmp/cv-smoke
# expect: "SUCCESS: build sample-profile.yaml -> Sam_Okafor_CV.pdf (ATS self-check passed ...)"
```

## Optional: visual (JSON Resume) path
Node 18+ only, and only for the *human/portfolio* variant (the submitted CV stays on the ATS
path): `npm i -g resumed jsonresume-theme-<name>`, then `cvstudio.py json profile.yaml` →
`npx resumed render profile.resume.json --theme jsonresume-theme-<name>`. Pin a single-column
theme. Design-led CVs should instead route to the owner's `design-studio` / `figma` pipeline.

## Versions proven on this machine (2026-07-19)
RenderCV 2.8 · bundled Typst 0.15.0 · PyMuPDF 1.28.0 · Python 3.14. Installed clean; sample
renders a 2-page tagged PDF that passes the PyMuPDF self-check.