# 13 Architecture candidates (reconstructed stand-in)

STATUS: RECONSTRUCTED. The catalog path
`C:/Users/Prekzursil/.claude/harness-restore-20260806/13-ARCHITECTURE-CANDIDATES.md`
is not a file on this Linux worktree (Path.is_file is false at every searched
root). A1-A9 heading titles are transcribed from
`command-center/WORK-UNIT-CATALOG.json` Phase 3 seven-lens titles. A10 and A11
exist as IDs in the ARC-0001 question (`A1-A11`) but have no seven-lens title
in this catalog; their headings are labeled UNRECOVERED.

## 1 Purpose

Eleven committed architecture candidates. Mapping onto the nine spec-mandated
classes is the ARC-0001 question. Do not treat this stand-in as byte-identical
to the missing Windows blob.

## 2 Candidate headings

## A1 (config-first minimal)

Static versioned config. No generated layer. No resident runtime. Catalog
seven-lens block begins at ARC-0003.

## A2 (generated single-source-of-truth)

A generator emits the live tree from a registry. Catalog seven-lens block
begins at ARC-0010.

## A3 (marketplace-first)

Lockfile-pinned packages as the control plane. Catalog seven-lens block
begins at ARC-0017.

## A4 (gateway / lazy-activation)

A gateway mediates activation with a resident-set floor. Catalog seven-lens
block begins at ARC-0024.

## A5 (distributed workflow-runtime)

Ledgered work-unit runtime across substrates. Catalog seven-lens block
begins at ARC-0031.

## A6 (cross-vendor adapter)

Guaranteed / best-effort / vendor-only tiers. Catalog seven-lens block
begins at ARC-0038.

## A7 (security-first)

Single permission choke point. Catalog seven-lens block begins at ARC-0045.

## A8 (UX / product-first)

Owner jobs-to-be-done and one error-message contract. Catalog seven-lens
block begins at ARC-0052.

## A9 (maximal hybrid)

Compose subsystems; keep each control plane singular. Catalog seven-lens
block begins at ARC-0059.

## A10 (UNRECOVERED-HEADING — catalog-id-only)

Heading text is not recoverable from this worktree. No `A10 (` seven-lens
title exists in WORK-UNIT-CATALOG.json. Disposition in ARC-0001 is REJECT
until live doc 13 is seated.

## A11 (UNRECOVERED-HEADING — catalog-id-only)

Heading text is not recoverable from this worktree. No `A11 (` seven-lens
title exists in WORK-UNIT-CATALOG.json. Disposition in ARC-0001 is REJECT
until live doc 13 is seated.

## 3 Hazard matrix

Column headers are the eleven candidates. Rows are hazard classes. Cell marks
are stand-in labels, not measured scores.

| hazard | A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 | A9 | A10 | A11 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duplicate-control-plane | L | M | M | H | H | M | L | L | H | ? | ? |
| spec-drift | H | L | M | M | M | M | L | H | H | ? | ? |
| overclaim | M | M | M | M | M | H | M | M | H | ? | ? |
