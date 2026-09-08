# Vacuous-test AST detector (TST-0348 / C23)

Scan Python tests by AST for four vacuous classes:

- `no_assertion`
- `constant_assertion`
- `mock_configured_assertion`
- `swallowed_failure`

String/docstring mentions of the word `assert` do not count as assertions.

```bash
python tools/vacuous-test-detector/vacuous_detector.py --json \
  tools/vacuous-test-detector/fixtures
python -m pytest tools/vacuous-test-detector/tests -q
```
