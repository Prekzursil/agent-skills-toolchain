# Extractor control (not part of the product docs tree)

Untagged JSON must be ignored even if it looks like a workflow object:

```json
{
  "id": "wf.control.untagged-must-be-ignored",
  "tools": ["Read"],
  "stop_rule": {"max_stages": 1, "on_error": "halt"},
  "stages": [{"id": "noop", "type": "task", "tools": ["Read"]}]
}
```

Tagged with the `workflow` info token:

```workflow
{
  "id": "wf.control.tagged-bare",
  "tools": ["Read"],
  "stop_rule": {"max_stages": 1, "on_error": "halt"},
  "stages": [
    {
      "id": "only",
      "type": "task",
      "tools": ["Read"],
      "inputs": ["repo"],
      "outputs": ["out.json"]
    }
  ]
}
```

Tagged as `json workflow`:

```json workflow
{
  "id": "wf.control.tagged-json-workflow",
  "tools": ["Grep"],
  "stop_rule": {"max_stages": 1, "on_error": "halt"},
  "stages": [
    {
      "id": "only",
      "type": "task",
      "tools": ["Grep"],
      "inputs": ["repo"],
      "outputs": ["hits.json"]
    }
  ]
}
```
