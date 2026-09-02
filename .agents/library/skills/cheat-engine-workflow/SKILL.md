---
name: cheat-engine-workflow
description: Use when performing Cheat Engine-driven runtime analysis, including value scanning, pointer sanity checks, AOB validation, structure inspection, and trainer-oriented confirmation during reverse-engineering or game runtime workflows.
---

# Cheat Engine Workflow

## Overview

Use Cheat Engine when the question is about live values, pointer stability, structure inspection, or validating an address/signature against the running process. It complements `$x64dbg`; it does not replace a debugger.

## Quick Workflow

1. Attach Cheat Engine to the running target process.
2. Start with the narrowest possible live fact: a value, a toggle, a structure field, or an AOB candidate from a known code region.
3. Use scans and rescans to confirm the smallest stable set of addresses or values.
4. If an address matters long-term, record the module base, surrounding bytes, and any pointer-chain assumptions immediately.
5. Hand confirmed findings to `$dump-to-signature-workflow`, `$swfoc-runtime-address-hunting`, or the relevant static-analysis skill when you need a durable artifact.

## Common Mistakes

- Treating a one-run absolute address as stable without module-base context.
- Using Cheat Engine alone when call flow or control transfer still needs debugger evidence.
- Saving only the final value and forgetting the bytes, module, or pointer assumptions that explain it.

## Reference Map

Read `references/workflow.md` for the local MCP bridge status, the recommended scan discipline, and when to escalate to x64dbg or BinDiff/BinExport.
