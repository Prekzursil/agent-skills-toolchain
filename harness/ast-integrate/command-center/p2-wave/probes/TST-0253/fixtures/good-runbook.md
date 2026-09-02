# Fixture: good runbook

## Step F-GOOD-1: Catalog parses

```postcondition
{"kind": "json_parse", "path": "command-center/WORK-UNIT-CATALOG.json", "min_bytes": 1024, "required_keys": ["work_units"]}
```

## Step F-GOOD-2: Checklist present

```postcondition
{"kind": "file_exists", "path": "command-center/RELEASE-CHECKLIST.md", "min_bytes": 64, "contains": "git cat-file"}
```
