---
name: instinct-import
description: Import instincts from file or URL into project/global scope
command: true
---

# Instinct Import Command

## Implementation

Run the instinct CLI using the plugin root path:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/continuous-learning-v2/scripts/instinct-cli.py" import <file-or-url> [--dry-run] [--force] [--min-confidence 0.7] [--scope project|global]
```

Or if `CLAUDE_PLUGIN_ROOT` is not set (manual installation):

```bash
python3 ~/.claude/skills/continuous-learning-v2/scripts/instinct-cli.py import <file-or-url>
```

Import instincts from local file paths or HTTP(S) URLs.

## Usage

```
/instinct-import team-instincts.yaml
/instinct-import https://github.com/org/repo/instincts.yaml
/instinct-import team-instincts.yaml --dry-run
/instinct-import team-instincts.yaml --scope global --force
```

## What to Do

1. Fetch the instinct file (local path or URL)
2. Parse and validate the format
3. Check for duplicates with existing instincts
4. Merge or add new instincts
