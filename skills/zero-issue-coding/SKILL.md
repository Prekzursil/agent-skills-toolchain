---
name: zero-issue-coding
description: Use when writing ANY new code in ANY language — enforces patterns that
  pass Codacy, SonarCloud, DeepSource, QLTY, Semgrep, and Codecov gates on first push
  without suppressions or exclusions
permalink: dqverify-repo-20261013/skills/zero-issue-coding/skill
---

# Zero-Issue Coding

## Overview

**Write code that passes every quality gate on the first push.** This skill encodes the patterns that prevent issues, not how to fix them after. If you follow these patterns, you will never trigger a Codacy/SonarCloud/DeepSource/QLTY finding.

**Core principle:** Prevention is 100x cheaper than cleanup. A 2,000-issue backlog takes days to fix. Writing clean from the start takes zero extra time.

## When to Use

- Writing ANY new function, class, or module
- Editing ANY existing code
- Before EVERY commit
- When a gate fails (find the pattern below, apply it, never repeat)

## The Prevention Checklist (Run Mentally Before Every Function)

1. **Null safety** — Can any parameter or return value be null? Handle it NOW.
2. **Complexity** — Will this function have > 3 branches? Split BEFORE writing.
3. **Security** — Does this touch user input, files, network, or secrets? Secure pattern NOW.
4. **Coverage** — What test will cover this? Write the test signature NOW.
5. **Length** — Will this function exceed 50 lines? Plan the extraction NOW.

## C# / .NET — Zero-Issue Patterns

### Null Dereference (kills 70%+ of Codacy findings)

```csharp
// ❌ TRIGGERS: Codacy potential-null-dereference, SonarCloud S2259
public void Process(GameProfile profile)
{
    var name = profile.DisplayName.ToUpper(); // nullable deref
    var count = profile.Symbols.Count;        // nullable deref
}

// ✅ ZERO ISSUES
public void Process(GameProfile profile)
{
    ArgumentNullException.ThrowIfNull(profile);
    var name = profile.DisplayName?.ToUpper() ?? string.Empty;
    var count = profile.Symbols?.Count ?? 0;
}
```

**Rule:** Every reference parameter gets `ThrowIfNull`. Every member access on a potentially-null gets `?.` with a `??` fallback. EVERY. SINGLE. ONE. No exceptions.

### CLS Compliance (kills 200+ Codacy findings)

```csharp
// ❌ TRIGGERS: Codacy CA1014, CA1038
public uint GetOffset() => _offset;
public sbyte GetFlag() => _flag;

// ✅ ZERO ISSUES — use CLS-compliant types in public APIs
public int GetOffset() => (int)_offset;    // or make method internal
public int GetFlag() => _flag;
internal uint GetRawOffset() => _offset;   // non-public = no CLS issue
```

**Rule:** Public APIs expose only: `bool`, `byte`, `short`, `int`, `long`, `float`, `double`, `decimal`, `string`, `object`. Use `internal` for everything else.

### Complexity (kills QLTY/Lizard/SonarCloud findings)

```csharp
// ❌ TRIGGERS: SonarCloud S3776, QLTY CCN > 15
public void HandleAction(ActionKind kind, RuntimeMode mode, bool isVerified)
{
    if (kind == ActionKind.Spawn)
    {
        if (mode == RuntimeMode.Tactical) { /* ... */ }
        else if (mode == RuntimeMode.Galactic) { /* ... */ }
    }
    else if (kind == ActionKind.SetCredits) { /* ... */ }
    else if (kind == ActionKind.SetSpeed) { /* ... */ }
    // 15 more branches...
}

// ✅ ZERO ISSUES — dispatch table + early return
private static readonly Dictionary<ActionKind, Func<RuntimeMode, Task>> Handlers = new()
{
    [ActionKind.Spawn] = HandleSpawn,
    [ActionKind.SetCredits] = HandleCredits,
    [ActionKind.SetSpeed] = HandleSpeed,
};

public Task HandleAction(ActionKind kind, RuntimeMode mode, bool isVerified)
{
    ArgumentNullException.ThrowIfNull(kind);
    if (!isVerified) throw new InvalidOperationException("Action not verified");
    if (!Handlers.TryGetValue(kind, out var handler))
        throw new NotSupportedException($"Unknown action: {kind}");
    return handler(mode);
}
```

**Rule:** If you see yourself writing the 4th `if/else if`, STOP. Use a dictionary, switch expression, or strategy pattern.

### Exception Handling

```csharp
// ❌ TRIGGERS: Codacy CA1031, SonarCloud S2221
try { DoWork(); } catch (Exception) { }

// ✅ ZERO ISSUES
try { DoWork(); }
catch (InvalidOperationException ex) { _logger.LogWarning(ex, "Expected failure"); }
catch (IOException ex) { _logger.LogError(ex, "I/O failure"); throw; }
```

### Hardcoded Secrets

```csharp
// ❌ TRIGGERS: Codacy CWE-798, Semgrep hardcoded-credentials
private const string ApiKey = "sk-abc123";

// ✅ ZERO ISSUES
private readonly string _apiKey = configuration["ApiKey"]
    ?? throw new InvalidOperationException("ApiKey not configured");
```

## Python — Zero-Issue Patterns

### Security (subprocess, secrets, eval)

```python
# ❌ TRIGGERS: Bandit B602, Codacy security
subprocess.call(cmd, shell=True)
password = "hunter2"
result = eval(user_input)

# ✅ ZERO ISSUES
subprocess.run(cmd_list, shell=False, check=True, capture_output=True)
password = os.environ["APP_PASSWORD"]
# For eval: use ast.literal_eval for data, or don't eval at all
```

### Complexity

```python
# ❌ TRIGGERS: SonarCloud S3776, Lizard CCN > 15
def process(data):
    if data.type == "a":
        if data.sub == "x": ...
        elif data.sub == "y": ...
    elif data.type == "b": ...

# ✅ ZERO ISSUES
_PROCESSORS = {"a": _process_a, "b": _process_b}

def process(data):
    handler = _PROCESSORS.get(data.type)
    if handler is None:
        raise ValueError(f"Unknown type: {data.type}")
    return handler(data)
```

### String Concatenation in Lists

```python
# ❌ TRIGGERS: Codacy implicit-string-concatenation
items = [
    "first"
    "second"    # missing comma — silent string concat
]

# ✅ ZERO ISSUES
items = [
    "first",
    "second",
]
```

## TypeScript — Zero-Issue Patterns

### Strict Types

```typescript
// ❌ TRIGGERS: ESLint @typescript-eslint/no-explicit-any
function process(data: any) { ... }

// ✅ ZERO ISSUES
interface ProcessInput { type: string; value: number; }
function process(data: ProcessInput) { ... }
```

## C++ — Zero-Issue Patterns

### Modern C++ (SonarCloud)

```cpp
// ❌ TRIGGERS: SonarCloud cpp:S5827, S5820, S1ావ5
auto* ptr = new MyClass();
typedef unsigned int uint;
void func() { int x = 0; if (condition) x = 1; }

// ✅ ZERO ISSUES
auto ptr = std::make_unique<MyClass>();
using uint = unsigned int;
void func() { const int x = condition ? 1 : 0; }
```

## Test Coverage — Zero-Gap Patterns

```csharp
// ❌ Missing branch coverage — only happy path tested
[Fact]
public void SetCredits_Works() {
    service.SetCredits(player, 1000);
    Assert.Equal(1000, player.Credits);
}

// ✅ 100% branch coverage — all paths tested
[Fact]
public void SetCredits_ValidAmount_SetsCredits() { ... }

[Fact]
public void SetCredits_NullPlayer_ThrowsArgumentNull() {
    Assert.Throws<ArgumentNullException>(() => service.SetCredits(null!, 1000));
}

[Fact]
public void SetCredits_NegativeAmount_ThrowsArgumentOutOfRange() {
    Assert.Throws<ArgumentOutOfRangeException>(() => service.SetCredits(player, -1));
}

[Theory]
[InlineData(0)]
[InlineData(999999)]
[InlineData(float.MaxValue)]
public void SetCredits_BoundaryValues_Succeeds(float amount) { ... }
```

**Rule:** For every function, test: happy path, null inputs, invalid inputs, boundary values, error conditions. This mechanically produces 100% branch coverage.

## Pre-Push (MANDATORY)

Before EVERY push, run `tools/pre-push-verify.sh` or the equivalent for this repo. If it fails, DO NOT PUSH.

## Common Mistakes That Create Backlogs

| Mistake | Issues Created | Prevention |
|---------|---------------|------------|
| No `<Nullable>enable</Nullable>` | 1,500+ null deref | Enable in every .csproj from day 1 |
| Public `uint`/`sbyte` APIs | 200+ CLS findings | Use `int`/`long` publicly, internal for raw types |
| Bare `catch (Exception)` | 50+ per project | Catch specific types only |
| `shell=True` in subprocess | Security finding per call | Always `shell=False` |
| Long methods (100+ lines) | CCN violations cascade | Extract at 30 lines, not 50 |
| Missing `.codacy.yml` exclusion removal | Issues hidden, not fixed | Never exclude first-party code |

## The Bottom Line

**Every pattern above exists because an agent once created thousands of issues by not following it.** These are not theoretical best practices — they are the specific patterns that prevent the specific findings from the specific tools configured on your repos.

Follow them. Zero issues. First push. Every time.