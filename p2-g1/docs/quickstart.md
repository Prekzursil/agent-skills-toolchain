# Quickstart

Run each example against the installed `ast-examples` package (not the
source tree) in a clean profile:

```bash
ast-examples run --id quickstart-hello
ast-examples run --id quickstart-presets
```

`quickstart-hello` writes `artifacts/quickstart-hello.json` with a council
run record (`kind=council-run`, `sentinel=SUCCESS:COUNCIL`, tally yes=2 / no=0).

`quickstart-presets` writes `artifacts/quickstart-presets.json` listing
presets `C-M01`, `C-02`, and `C-03`.
