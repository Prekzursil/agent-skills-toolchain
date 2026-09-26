---
title: codeblocks-pretty-prints-stable lean-quality-gate GREEN (2026-06-20)
type: note
permalink: main/projects/reframe/codeblocks-pretty-prints-stable-lean-quality-gate-green-2026-06-20
tags:
- lean-quality-gate
- fleet
- codeblocks
- ci-green
---

# codeblocks-pretty-prints-stable lean-quality-gate GREEN

Branch `feat/lean-quality-gate`, final SHA `0c2914a`. `quality / quality` CI run 27857617889 = **success** (all lanes green).

## Repo shape
Python-only source under `scripts/` (8 modules) + `tests/` (unittest, 41 tests). Also a thin `package.json` (only @playwright/test devDep, no first-party ts/js source) so jsts lanes run but find nothing lintable. Coverage gate uses the **unittest path** (no pytest config present): `coverage run -m unittest discover` then `coverage report --fail-under=100`. `.coveragerc`: branch=True, source=scripts, omit __init__, fail_under=100.

## Two fixes (real, scoped)
1. `style:` ruff-format `.quality/run_coverage_gate.py` (blank line after docstring + line wrap). SHA 544fce9.
2. **THE CI fix** `fix(ci):` added a runtime `requirements.txt` declaring `defusedxml==0.7.1`. SHA 0c2914a.

## Root cause (the load-bearing finding)
CI failed `gate-tests-coverage python` with `ModuleNotFoundError: No module named 'defusedxml'` (2 tests errored → coverage failed). `defusedxml` backs `scripts/quality/normalize_coverage_xml.py` but was ONLY in `requirements-dev.txt`. The lean gate v1 coverage lane **deliberately excludes** dev/test/lint/doc/ci requirements (`grep -Eiv 'requirements.*(dev|test|lint|doc|ci).*\.txt$'`) and there was no pyproject/setup.* to `pip install .`, so no runtime dep got installed. Fix = ship a plain `requirements.txt` (matched + NOT excluded by the gate regex) with the runtime dep.

## Gotcha for the fleet
Local-pass-but-CI-fail trap: a venv with the dep pre-installed hides this. To reproduce the gate, install ONLY runtime `requirements.txt` (not `-dev`), then run the unittest coverage path. The remaining basedpyright `reportMissingModuleSource` lines for defusedxml are WARNINGS (no type stubs), not errors — gate reports "0 errors", green.

## opengrep/osv on Windows
opengrep installer rejects Windows (`Operating system 'Windows_NT' unsupported`) — cannot run gate-4 locally on a Windows host; verified by inspecting the curated ruleset (exec/eval/shell=True/os.system/pickle/yaml.load/md5-sha1/verify=False/jwt) and grepping source = no matches. CI confirmed gate-sast + gate-deps green.
