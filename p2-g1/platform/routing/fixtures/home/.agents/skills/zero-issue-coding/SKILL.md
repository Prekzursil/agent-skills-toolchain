---
name: zero-issue-coding
description: Use when writing ANY new code in ANY language — enforces patterns that pass Codacy, SonarCloud, DeepSource, QLTY, Semgrep, and Codecov gates on first push without suppressions or exclusions
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

### CLS Compliance (kills 200+ Codacy findings)
### Complexity (kills QLTY/Lizard/SonarCloud findings)
### Exception Handling
### Hardcoded Secrets
### Python — Zero-Issue Patterns
### Security (subprocess, secrets, eval)
### ❌ TRIGGERS: Bandit B602, Codacy security
### ✅ ZERO ISSUES
