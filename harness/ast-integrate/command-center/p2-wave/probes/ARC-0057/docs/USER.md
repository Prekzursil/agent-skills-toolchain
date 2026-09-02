# A8 product surface — documentation-command corpus

A8 is organized around owner jobs, not subsystems. One command:
`a8_product.py`. Three verbs: `jobs`, `catalog`, `cockpit`.

This file is the product documentation the ARC-0057 suite executes. It is not
an A8 DESIGN.json rebuild.

## First run

```bash
python3 command-center/p2-wave/probes/ARC-0057/a8_product.py --help
python3 command-center/p2-wave/probes/ARC-0057/a8_product.py jobs
python3 command-center/p2-wave/probes/ARC-0057/a8_product.py catalog --format json
python3 command-center/p2-wave/probes/ARC-0057/a8_product.py cockpit --plain
```

## Visual cockpit (not on this Linux worktree)

<!-- doc-test:skip reason="visual cockpit surface is not present on this Linux worktree" -->
```bash
python3 command-center/p2-wave/probes/ARC-0057/a8_product.py cockpit --visual
```
