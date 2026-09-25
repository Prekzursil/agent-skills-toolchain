---
name: gate-zero-enforcer
description: Use when writing, editing, or generating any code in repositories with CI quality gates - Codacy, SonarCloud, Semgrep, Sentry, QLTY, DeepScan, DeepSource, Codecov, or when a PR fails a quality gate check
---

# Gate zero enforcer

## Overview

**Write code that passes all quality gates on the first push.** Every gate threshold is encoded here — check constraints BEFORE writing, not after a CI failure.

## When to use

- Writing any new code (functions, classes, modules)
- Editing existing code in a gated repository
- A PR has failed a quality gate (use the specific gate section to diagnose)
- Planning a feature that will touch multiple files

## Gate thresholds

### Codacy (all repos under Prekzursil org)

| Gate | Threshold | Notes |
|------|-----------|-------|
| New issues | 0 (minor or above) | Zero tolerance — no warnings, no info-level |
| New security issues | 0 (minor or above) | Includes hardcoded secrets, injection vectors |
| Complexity delta | ≤ 10 per PR | Sum of CCN across all new/changed functions |
| Duplication | 0 cloned blocks | No copy-paste, extract shared logic |
| Coverage variation | 0% regression | Never reduce existing coverage |
| Diff coverage | 100% | Every new/changed line must be tested |

### Per-function limits (Lizard / QLTY)

| Metric | Hard limit | Warning |
|--------|-----------|---------|
| Cyclomatic complexity | ≤ 15 per function | > 10 worth reviewing |
| Function length | ≤ 50 lines | > 40 gets attention |
| Parameter count | ≤ 5 | > 4 consider object param |

### SonarCloud

- Zero bugs, zero vulnerabilities, zero code smells on new code
- Security hotspots must be reviewed (mark as safe or fix)
- Maintain A rating on reliability, security, maintainability

### Codecov

- Overall coverage must not decrease
- Patch coverage: 100% (same as Codacy diff coverage)
- No flags may drop below their baseline

### Semgrep

- Zero findings on new/changed files
- Applies to: security, correctness, performance, best-practice rulesets

### DeepScan / DeepSource

- Zero new issues at any severity
- DeepSource Autofix suggestions should be reviewed and applied

### Sentry (runtime)

- No new unhandled exceptions introduced
- Error rate must not increase after deployment

## Pre-write checklist

Before writing ANY function, verify:

1. **Complexity budget** — will this function have more than 3 branches? If yes, split into helpers BEFORE writing
2. **Test plan** — what tests will cover this? Write test signatures first
3. **Security surface** — does this touch user input, file I/O, network, or secrets? Apply secure patterns from the start
4. **Import hygiene** — only import what you use, prefer specific imports over wildcards

## Language-specific patterns

### Python

```python
# ❌ Fails Codacy/Bandit — hardcoded secret
API_KEY = "sk-abc123"

# ✅ Passes all gates
API_KEY = os.environ["API_KEY"]

# ❌ Fails Codacy — CCN > 15, too many branches
def process(data):
    if data.type == "a":
        if data.sub == "x":
            ...
        elif data.sub == "y":
            ...
    elif data.type == "b":
        ...

# ✅ Passes — dispatch table, CCN = 1
PROCESSORS = {"a": process_a, "b": process_b}
def process(data):
    return PROCESSORS[data.type](data)

# ❌ Fails Bandit B602 — subprocess with shell=True
subprocess.call(cmd, shell=True)

# ✅ Passes
subprocess.run(cmd_list, shell=False, check=True)
```

Bandit skips: `B101` (assert in tests is fine), exclude `tests/` directory.

### TypeScript / Node.js

```typescript
// ❌ Fails ESLint/Codacy — unused import
import { foo, bar, baz } from './utils';
// only foo is used

// ✅ Import only what you use
import { foo } from './utils';

// ❌ Fails complexity gate — nested ternaries
const result = a ? (b ? (c ? x : y) : z) : w;

// ✅ Extract to named function
function determineResult(a: boolean, b: boolean, c: boolean) {
  if (!a) return w;
  if (!b) return z;
  return c ? x : y;
}
```

ESLint 9 flat config required for `pbinfo-get-unsolved` and similar Node.js 20 repos.

### C# / .NET (SWFOC Trainer)

```csharp
// ❌ Fails — empty catch swallows errors
try { DoWork(); } catch { }

// ✅ Log or rethrow
try { DoWork(); }
catch (InvalidOperationException ex)
{
    _logger.LogError(ex, "DoWork failed");
    throw;
}

// ❌ Fails — magic number
if (hp > 9999) { ... }

// ✅ Named constant
private const int MaxHitPoints = 9999;
if (hp > MaxHitPoints) { ... }
```

## When a gate fails

1. Read the EXACT error message from CI output
2. Match it to the gate section above
3. Fix the root cause, not the symptom (don't just suppress the warning)
4. Run local verification before pushing:

```bash
# Python repos
bandit -r src/ -ll --exclude tests/
lizard src/ -C 15 -L 60 -a 5 -x "*/tests/*"
pytest --cov=src --cov-report=term-missing

# Node.js repos
npx eslint . --max-warnings 0
npx jest --coverage --coverageThreshold='{"global":{"branches":100,"functions":100,"lines":100}}'

# C# repos
dotnet build --warnaserror
dotnet test --collect:"XPlat Code Coverage"
```

## Common mistakes

| Mistake | Gate it fails | Fix |
|---------|--------------|-----|
| `assert` in production code | Codacy/Bandit B101 | Use proper validation/exceptions |
| `# type: ignore` without reason | Codacy | Add specific error code: `# type: ignore[attr-defined]` |
| Catching broad `Exception` | Codacy/SonarCloud | Catch specific exception types |
| Long parameter lists | QLTY/Lizard | Use dataclass/TypedDict/options object |
| Duplicated logic across files | Codacy duplication | Extract to shared utility |
| Test file without assertions | Codecov (inflates coverage) | Every test must assert something meaningful |
