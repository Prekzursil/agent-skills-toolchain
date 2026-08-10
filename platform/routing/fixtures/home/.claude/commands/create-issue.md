# Create GitHub Issue

Create a comprehensive, well-structured GitHub issue with embedded agent instructions for autonomous PR lifecycle management.

## Usage

```text
/create-issue [type] [description]
```

**Arguments** (optional - will prompt if not provided):

- `type`: `feature`, `bug`, or `refactor`
- `description`: Brief description of the issue

## Examples

```bash
# Interactive mode (prompts for all details)
/create-issue

# With type specified
/create-issue feature

# With type and description
/create-issue bug "Login fails when email contains plus sign"
```

## What This Does

1. **Gathers context** through interactive questions
2. **Generates comprehensive issue** with all required sections:
   - Problem/Feature specification with clear scope
   - Technical specification (types, schemas, APIs)
   - TDD Implementation Plan with test-first cycles
   - Error handling matrix
   - Files to create/modify
