# windows-shell.md section 8b (pin parity) — reconstructed for CNF-0185

This Linux worktree does not ship `rules/common/windows-shell.md`. The catalog
names section 8b as an input to CNF-0185. The discipline encoded here, and
enforced by `toolchain.py`, is:

8b. Pin parity. When a claim was measured under a CI-pinned tool version,
invoke that version by an explicit, version-qualified path (or
`python -m <tool>` after installing `==<pin>` into an isolated prefix). Do
not treat a green from the ambient PATH as evidence about the pin. Read the
tool's own `--version` / `version` stdout and cite the invocation used.

P2-BUILD-ROUND2 cites the same 8b rule next to orchestrator-issued pin
invocations. CNF-0185's known estate precedent is ruff 0.15.17 (CI) vs
0.15.22 (ambient local) disagreeing on identical bytes.
