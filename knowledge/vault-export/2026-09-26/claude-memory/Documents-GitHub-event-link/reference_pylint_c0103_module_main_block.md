---
name: Pylint C0103 fires inside `if __name__ == "__main__":` blocks
description: Pylint treats names assigned directly inside `if __name__ == "__main__":`
  as module-level constants and flags them as not-UPPER_CASE. Wrap the CLI logic in
  a function so locals stay local-scoped.
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-pylint-c0103-module-main-block
---

Pylint considers any name assigned inside `if __name__ == "__main__":`
to be module-level scope, which means it falls under the C0103
"constant naming" rule (UPPER_CASE required) instead of the
"local variable" rule (snake_case allowed). Even names with leading
underscore (e.g., `_filename`) are flagged because pylint sees them
as module-private constants, not function-private locals.

Symptom: `C0103: Constant name "_filename" doesn't conform to
UPPER_CASE naming style`.

The fix: extract the entire CLI body into a function (`def main()`,
`def _run_cli()`, etc.) and call it from the `if __name__` guard.
Inside the function the same names are now true local variables and
snake_case is correct.

```python
def _run_cli() -> None:  # pragma: no cover — ad-hoc CLI
    label, slug, ... = sys.argv[1:N]
    ...
    filename = "..."  # snake_case is fine here

if __name__ == "__main__":  # pragma: no cover — ad-hoc CLI
    _run_cli()
```

This was demonstrated in PR #208 (QZP) where `bypass_labels.py`'s
inline CLI body was extracted to drop two C0103 findings.