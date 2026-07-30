---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Security

> This file extends [common/security.md](../common/security.md) with Python specific content.

## Secret Management

```python
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ["OPENAI_API_KEY"]  # Raises KeyError if missing
```

## Security Scanning

- Use **bandit** for static security analysis. Scan the repository root so the command
  works on any layout — a literal `src/` scans nothing in the many repos that do not use
  that layout, and it disagrees with the first-party `python-reviewer` agent and the
  `/python-review` command, which both scan `.`:
  ```bash
  bandit -r .
  ```
  Narrow the root (`bandit -r src/`) only in a repo that actually has one, and configure
  exclusions in `pyproject.toml`/`.bandit` rather than by shortening the scan root.

## Reference

See skill: `django-security` for Django-specific security guidelines (if applicable).
