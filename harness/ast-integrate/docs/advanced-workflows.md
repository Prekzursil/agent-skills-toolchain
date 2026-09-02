# Advanced workflows

These examples also run from the installed package:

```
ast-examples run --id advanced-resume
ast-examples run --id advanced-import-dag
```

`advanced-resume` resumes checkpoint `ck-adv-1` under majority-quorum and
writes `artifacts/advanced-resume.json`.

`advanced-import-dag` imports a two-unit DAG (`wait`, `timeout_seconds`,
`prompt_file`; no inline `--prompt`) into `artifacts/advanced-import-dag.json`.
