---
title: CATALOG-INTEGRITY
type: note
permalink: dqverify-repo-20261013/command-center/catalog-integrity
---

# CATALOG-INTEGRITY - mechanical audit of command-center/catalog-slices/

Generated: 2026-08-09T18:47:11Z by `command-center/_catalog_integrity.py`

## Headline

- **2007 units** across 22 slice files, target 2048 -> **shortfall 41**
- files that failed to parse: **0** 
- duplicate ids: **0**
- malformed ids (not CODE-NNNN): **0**
- phases with ZERO units: **0** 
- unresolved dependency refs: **0** unit-id + **41** unknown-form
- dependency cycles: **1**
- exact normalised title+target duplicate clusters: **0**; exact title-only clusters: **2**
- units inside a Jaccard>=0.8 overlap cluster: **0** in **0** clusters
- detector control: **CONFIRMED** (10/10 detectors fire on a seeded defect AND stay silent on the real corpus)

## 1. File existence and parse

| file | bytes | parses | units | error |
|---|---:|---|---:|---|
| ADV-1.json | 414535 | yes | 128 |  |
| ADV-2.json | 67360 | yes | 16 |  |
| ARC-1.json | 302977 | yes | 112 |  |
| AUD-1.json | 218397 | yes | 96 |  |
| BLD-1.json | 184711 | yes | 64 |  |
| CC-1.json | 66265 | yes | 24 |  |
| CNF-1.json | 323675 | yes | 128 |  |
| CNF-2.json | 168516 | yes | 64 |  |
| CNL-1.json | 371117 | yes | 128 |  |
| IMP-1.json | 289216 | yes | 128 |  |
| IMP-2.json | 281749 | yes | 128 |  |
| IMP-3.json | 312071 | yes | 118 |  |
| IMP-4.json | 176184 | yes | 96 |  |
| REL-1.json | 71538 | yes | 24 |  |
| RES-1.json | 360666 | yes | 128 |  |
| RES-2.json | 182076 | yes | 65 |  |
| SYN-1.json | 139792 | yes | 48 |  |
| TST-1.json | 270232 | yes | 128 |  |
| TST-2.json | 266912 | yes | 128 |  |
| TST-3.json | 233477 | yes | 96 |  |
| WFA-1.json | 335661 | yes | 128 |  |
| WFA-2.json | 94628 | yes | 32 |  |

## 2. Unit counts and where the shortfall lives

Total **2007** / target **2048** = shortfall **41**.

Attribution verdict: **CONFIRMED: per-family deficits sum exactly to the global shortfall**

| id family | units | bucket | quota | deficit | mapping basis |
|---|---:|---|---:|---:|---|
| ADV | 144 | B10 | 144 | 0 | declared `bucket` field on 144/144 units |
| ARC | 112 | B06 | 112 | 0 | unique unclaimed bucket whose quota == family size (112) |
| AUD | 96 | B02 | 96 | 0 | declared `bucket` field on 96/96 units |
| BLD | 64 | B11 | 64 | 0 | unique unclaimed bucket whose quota == family size (64) |
| CC | 24 | B01 | 24 | 0 | bucket name "command-center and corpus-control" matches family hint "command-center" (quota 24) |
| CNF | 192 | B09 | 192 | 0 | unique unclaimed bucket whose quota == family size (192) |
| CNL | 128 | B05 | 128 | 0 | unique unclaimed bucket whose quota == family size (128) |
| IMP | 470 | B07 | 480 | **10** | max authored id IMP-0480 == bucket quota 480; family numbered itself to the quota |
| REL | 24 | B13 | 24 | 0 | max authored id REL-0024 == bucket quota 24; family numbered itself to the quota |
| RES | 193 | B03 | 224 | **31** | bucket name "deep-research, ecosystem, and gem-hunt" matches family hint "research" (quota 224) |
| SYN | 48 | B12 | 48 | 0 | unique unclaimed bucket whose quota == family size (48) |
| TST | 352 | B08 | 352 | 0 | unique unclaimed bucket whose quota == family size (352) |
| WFA | 160 | B04 | 160 | 0 | declared `bucket` field on 32/160 units |

Sum of per-family deficits = **41**, global shortfall = **41**, exact match = **True**. Bucket-mapping collisions: none. Buckets with no id family: none.

Ids the slice authors skipped (never written, not merely renumbered):

- **IMP**: 470 units, highest id `IMP-0480`, **10 missing**: ['IMP-0375', 'IMP-0376', 'IMP-0377', 'IMP-0378', 'IMP-0379', 'IMP-0380', 'IMP-0381', 'IMP-0382', 'IMP-0383', 'IMP-0384']

## 3. Duplicate ids across all files

None. 2007 units carry 2007 distinct ids.

## 4. ID format and sequence

Malformed (not `CODE-NNNN`): 0 

| prefix | count | distinct | min | max | contiguous 1..N | gaps | repeated |
|---|---:|---:|---:|---:|---|---|---|
| ADV | 144 | 144 | 1 | 144 | yes | none | none |
| ARC | 112 | 112 | 1 | 112 | yes | none | none |
| AUD | 96 | 96 | 1 | 96 | yes | none | none |
| BLD | 64 | 64 | 1 | 64 | yes | none | none |
| CC | 24 | 24 | 1 | 24 | yes | none | none |
| CNF | 192 | 192 | 1 | 192 | yes | none | none |
| CNL | 128 | 128 | 1 | 128 | yes | none | none |
| IMP | 470 | 470 | 1 | 480 | **NO** | 10: [375, 376, 377, 378, 379, 380, 381, 382, 383, 384] | none |
| REL | 24 | 24 | 1 | 24 | yes | none | none |
| RES | 193 | 193 | 1 | 193 | yes | none | none |
| SYN | 48 | 48 | 1 | 48 | yes | none | none |
| TST | 352 | 352 | 1 | 352 | yes | none | none |
| WFA | 160 | 160 | 1 | 160 | yes | none | none |

## 5. Required-field coverage

19 spec-mandated fields (_USER-PROMPTS.md:10607-10625) + 'bucket' (allocation authority: PHASE-GRAPH.json allocation_buckets) = 20

| field | absent key | present-but-empty |
|---|---:|---:|
| id | 0 | 0 |
| title | 0 | 0 |
| phase | 0 | 0 |
| question_or_target | 0 | 0 |
| inputs | 0 | 0 |
| dependencies | 0 | 10 |
| assigned_model_vendor_role | 0 | 0 |
| tool_permissions | 0 | 0 |
| execution_substrate | 0 | 0 |
| timeout_seconds | 0 | 0 |
| output_path | 0 | 0 |
| output_schema | 0 | 0 |
| evidence_requirement | 0 | 0 |
| tests_required | 0 | 0 |
| reviewer_requirement | 0 | 0 |
| completion_sentinel | 0 | 0 |
| retry_policy | 0 | 0 |
| failure_classification | 0 | 0 |
| owner_approval_required | 0 | 0 |
| bucket | 1735 | 0 |

- absent `bucket` by bucket: {'prefix:ARC': 112, 'prefix:BLD': 64, 'prefix:CC': 24, 'prefix:CNF': 192, 'prefix:CNL': 128, 'prefix:IMP': 470, 'prefix:REL': 24, 'prefix:RES': 193, 'prefix:SYN': 48, 'prefix:TST': 352, 'prefix:WFA': 128}
- empty `dependencies` by bucket: {'prefix:CC': 7, 'prefix:REL': 1, 'prefix:TST': 2}

Auxiliary (non-required) field presence out of 2007: {'slice': 240, 'mechanism': 160, 'not_a_duplicate_because': 160, 'spec_anchor': 160, 'dependency_anchors': 16}

## 6. Near-duplicate / padding analysis (the substantive check)

Normalisation: lowercase `title + question_or_target`, strip non-alphanumerics, drop 139 stopwords and <=2-char tokens (keeping ['api', 'ci', 'cli', 'db', 'id', 'io', 'mcp', 'os', 'pr', 'ui', 'ux', 'wu']).

- scan floor 0.3 (pairs are enumerated down to this Jaccard, so the buckets below the reporting threshold are real counts, not prune artifacts)
- pairs by Jaccard threshold: {'0.4': 4, '0.3': 44}
- **maximum pairwise Jaccard in the whole catalog = 0.4286** (ADV-0091 vs IMP-0318)
  - `Instant-unanimity trigger: does suspiciously fast agreement force re-evaluation?`
  - `Instant-unanimity trigger with blind re-evaluation and forced dissent`
- exact normalised title+target clusters: 0
- exact normalised title-only clusters: 2
- identical token-bag clusters: 0
- Jaccard>=0.8 clusters: 0 covering 0 units; sizes=[]

### Exact normalised title-only collisions (top 20)

- **2x** ['ADV-0093', 'CNL-0087'] in ['ADV-1.json', 'CNL-1.json']
  - `Sycophancy toward the chair or the owner`
- **2x** ['CNL-0032', 'IMP-0283'] in ['CNL-1.json', 'IMP-3.json']
  - `Proposer-critic-judge pipeline topology`

### 20 worst high-overlap clusters (Jaccard>=0.8)

**None.** Zero clusters exist at Jaccard>=0.8 - the whole-catalog maximum is 0.4286, so no pair comes close to the padding threshold. The detector is proved able to find a planted clone in this same corpus (see the detector-control section), so this zero is a measurement, not a silent detector.

### 20 most-similar pairs in the catalog (ranked, no threshold)

1. J=0.4286 `ADV-0091` (ADV-1.json) vs `IMP-0318` (IMP-3.json)
   - Instant-unanimity trigger: does suspiciously fast agreement force re-evaluation?
   - Instant-unanimity trigger with blind re-evaluation and forced dissent
2. J=0.4219 `TST-0026` (TST-1.json) vs `CC-0012` (CC-1.json)
   - Launcher and schema freeze gate with a versioned-migration requirement
   - Freeze the schemas and launchers, and require a versioned migration for every later change
3. J=0.4194 `ADV-0026` (ADV-1.json) vs `AUD-0081` (AUD-1.json)
   - Auto-loaded agent config in a freshly cloned untrusted repository
   - Untrusted auto-loaded configuration audit in cloned and vendored trees
4. J=0.4118 `IMP-0437` (IMP-4.json) vs `TST-0076` (TST-1.json)
   - Arm the disarmed work-unit field-completeness check in CI
   - Conformance validator self-test: prove the validator is armed in CI
5. J=0.3875 `TST-0347` (TST-3.json) vs `SYN-0043` (SYN-1.json)
   - Prove each of the 21 program stopping conditions can actually be made false
   - Terminal evaluation of the 21 program stopping conditions, with NOT-CHECKED blocking completion
6. J=0.383 `WFA-0005` (WFA-1.json) vs `WFA-0148` (WFA-2.json)
   - Adjudicate the 6 classification values that 0 of 284 candidates ever received
   - Classifier expressiveness audit: six vocabulary values were never assigned
7. J=0.3725 `IMP-0006` (IMP-1.json) vs `IMP-0067` (IMP-1.json)
   - plugin.json manifest JSON Schema extending the existing .claude-plugin/plugin.json
   - Canonical registry index schema extending .claude-plugin/marketplace.json
8. J=0.3667 `IMP-0446` (IMP-4.json) vs `IMP-0223` (IMP-2.json)
   - Worktree-per-shard provisioner with content-preserving teardown
   - Implement worktree provisioning and teardown per implementation shard
9. J=0.3647 `IMP-0436` (IMP-4.json) vs `CC-0001` (CC-1.json)
   - Per-unit override semantics for the nine globally-defaulted catalog fields
   - Make all 19 contract fields per-unit expressible, and arm the completeness gate that proves it
10. J=0.3647 `CNF-0001` (CNF-1.json) vs `CNF-0129` (CNF-2.json)
   - Confirmation receipt and discrepancy-record schemas with a rejecting validator
   - Author the confirmation-record schema and make an unsourced CONFIRMED verdict unrepresentable
11. J=0.36 `TST-0125` (TST-1.json) vs `TST-0338` (TST-3.json)
   - Coverage-threshold source of truth with an explicit NOT-CHECKED emitter
   - Read the coverage threshold from the project SSOT and emit NOT-CHECKED when there is none
12. J=0.3571 `RES-0037` (RES-1.json) vs `IMP-0065` (IMP-1.json)
   - Measure the per-session process cost of stdio versus HTTP MCP transports on this box
   - Lazy shared MCP activation to end per-session process multiplication
13. J=0.3542 `IMP-0477` (IMP-4.json) vs `ARC-0110` (ARC-1.json)
   - Versioned schema migration engine with a launcher freeze marker
   - Freeze ceremony: schemas and launchers frozen, changes only by versioned migration
14. J=0.35 `WFA-0103` (WFA-1.json) vs `IMP-0185` (IMP-2.json)
   - Fusion operator: best-of-breed, selecting each stage from whichever source performs it best
   - Implement best-of-breed fusion driven by per-stage benchmark evidence
15. J=0.35 `AUD-0095` (AUD-1.json) vs `ARC-0110` (ARC-1.json)
   - Launcher and schema freeze inventory with a versioned-migration requirement
   - Freeze ceremony: schemas and launchers frozen, changes only by versioned migration
16. J=0.3462 `CNL-0037` (CNL-1.json) vs `CNL-0123` (CNL-1.json)
   - Nested subcouncils and council-of-councils fan-in
   - Council-of-councils fan-in simulation including the disagreement case
17. J=0.34 `WFA-0083` (WFA-1.json) vs `CC-0009` (CC-1.json)
   - Register every WFA artifact in the manifest and prove downstream consumers can read it
   - Enforce artifact-manifest registration and prove a downstream consumer can actually read each entry
18. J=0.3382 `IMP-0433` (IMP-4.json) vs `CC-0002` (CC-1.json)
   - Author the absent receipt schema every work unit is contracted to satisfy
   - Create the receipt substrate every work unit is contracted to write to
19. J=0.3333 `WFA-0012` (WFA-1.json) vs `CC-0005` (CC-1.json)
   - Make every WFA gate runnable on the Windows dev box (CRLF-versus-LF portability)
   - Make the manifest provenance gate hash the git blob, not the Windows working tree
20. J=0.3333 `IMP-0477` (IMP-4.json) vs `TST-0026` (TST-1.json)
   - Versioned schema migration engine with a launcher freeze marker
   - Launcher and schema freeze gate with a versioned-migration requirement

### 20 worst clusters at the exploratory Jaccard>=0.35 threshold

14 clusters covering 29 of 2007 units (1.4%). 0.35 is a LOOSE threshold - these are thematic neighbours, not duplicates. Listed so the "where is the overlap" question has a concrete answer.

1. **size 3**, mean J=0.3521, max J=0.3542, files=['ARC-1.json', 'AUD-1.json', 'IMP-4.json']
   - `ARC-0110` Freeze ceremony: schemas and launchers frozen, changes only by versioned migration
   - `AUD-0095` Launcher and schema freeze inventory with a versioned-migration requirement
   - `IMP-0477` Versioned schema migration engine with a launcher freeze marker
2. **size 2**, mean J=0.4286, max J=0.4286, files=['ADV-1.json', 'IMP-3.json']
   - `ADV-0091` Instant-unanimity trigger: does suspiciously fast agreement force re-evaluation?
   - `IMP-0318` Instant-unanimity trigger with blind re-evaluation and forced dissent
3. **size 2**, mean J=0.4219, max J=0.4219, files=['CC-1.json', 'TST-1.json']
   - `CC-0012` Freeze the schemas and launchers, and require a versioned migration for every later change
   - `TST-0026` Launcher and schema freeze gate with a versioned-migration requirement
4. **size 2**, mean J=0.4194, max J=0.4194, files=['ADV-1.json', 'AUD-1.json']
   - `ADV-0026` Auto-loaded agent config in a freshly cloned untrusted repository
   - `AUD-0081` Untrusted auto-loaded configuration audit in cloned and vendored trees
5. **size 2**, mean J=0.4118, max J=0.4118, files=['IMP-4.json', 'TST-1.json']
   - `IMP-0437` Arm the disarmed work-unit field-completeness check in CI
   - `TST-0076` Conformance validator self-test: prove the validator is armed in CI
6. **size 2**, mean J=0.3875, max J=0.3875, files=['SYN-1.json', 'TST-3.json']
   - `SYN-0043` Terminal evaluation of the 21 program stopping conditions, with NOT-CHECKED blocking completion
   - `TST-0347` Prove each of the 21 program stopping conditions can actually be made false
7. **size 2**, mean J=0.383, max J=0.383, files=['WFA-1.json', 'WFA-2.json']
   - `WFA-0005` Adjudicate the 6 classification values that 0 of 284 candidates ever received
   - `WFA-0148` Classifier expressiveness audit: six vocabulary values were never assigned
8. **size 2**, mean J=0.3725, max J=0.3725, files=['IMP-1.json']
   - `IMP-0006` plugin.json manifest JSON Schema extending the existing .claude-plugin/plugin.json
   - `IMP-0067` Canonical registry index schema extending .claude-plugin/marketplace.json
9. **size 2**, mean J=0.3667, max J=0.3667, files=['IMP-2.json', 'IMP-4.json']
   - `IMP-0223` Implement worktree provisioning and teardown per implementation shard
   - `IMP-0446` Worktree-per-shard provisioner with content-preserving teardown
10. **size 2**, mean J=0.3647, max J=0.3647, files=['CC-1.json', 'IMP-4.json']
   - `CC-0001` Make all 19 contract fields per-unit expressible, and arm the completeness gate that proves it
   - `IMP-0436` Per-unit override semantics for the nine globally-defaulted catalog fields
11. **size 2**, mean J=0.3647, max J=0.3647, files=['CNF-1.json', 'CNF-2.json']
   - `CNF-0001` Confirmation receipt and discrepancy-record schemas with a rejecting validator
   - `CNF-0129` Author the confirmation-record schema and make an unsourced CONFIRMED verdict unrepresentable
12. **size 2**, mean J=0.36, max J=0.36, files=['TST-1.json', 'TST-3.json']
   - `TST-0125` Coverage-threshold source of truth with an explicit NOT-CHECKED emitter
   - `TST-0338` Read the coverage threshold from the project SSOT and emit NOT-CHECKED when there is none
13. **size 2**, mean J=0.3571, max J=0.3571, files=['IMP-1.json', 'RES-1.json']
   - `IMP-0065` Lazy shared MCP activation to end per-session process multiplication
   - `RES-0037` Measure the per-session process cost of stdio versus HTTP MCP transports on this box
14. **size 2**, mean J=0.35, max J=0.35, files=['IMP-2.json', 'WFA-1.json']
   - `IMP-0185` Implement best-of-breed fusion driven by per-stage benchmark evidence
   - `WFA-0103` Fusion operator: best-of-breed, selecting each stage from whichever source performs it best

## 7. Dependency resolution and cycles

- total dependency refs: 3695
- unresolved unit-id refs: **0** 
- bucket-code refs: {'B07': 299, 'B06': 61, 'B01': 234, 'B09': 36, 'B12': 19, 'B08': 89, 'B02': 61, 'B13': 45, 'B03': 44, 'B04': 34, 'B05': 47, 'B10': 33, 'B11': 4} (legal set B01..B13 from PHASE-GRAPH.json allocation_buckets)
- illegal bucket refs: none
- **unknown-form refs: 41** distinct ['BKT-ARC', 'BKT-CMD', 'BKT-IMP', 'WFA-1of2']
  - `TST-0001` -> `BKT-CMD` at TST-1.json[0]
  - `TST-0001` -> `BKT-IMP` at TST-1.json[0]
  - `TST-0002` -> `BKT-CMD` at TST-1.json[1]
  - `TST-0013` -> `BKT-CMD` at TST-1.json[12]
  - `TST-0023` -> `BKT-CMD` at TST-1.json[22]
  - `TST-0033` -> `BKT-ARC` at TST-1.json[32]
  - `TST-0034` -> `BKT-ARC` at TST-1.json[33]
  - `TST-0035` -> `BKT-ARC` at TST-1.json[34]
  - `TST-0036` -> `BKT-ARC` at TST-1.json[35]
  - `TST-0037` -> `BKT-ARC` at TST-1.json[36]
  - `TST-0038` -> `BKT-ARC` at TST-1.json[37]
  - `TST-0039` -> `BKT-ARC` at TST-1.json[38]
  - `TST-0040` -> `BKT-ARC` at TST-1.json[39]
  - `TST-0041` -> `BKT-ARC` at TST-1.json[40]
  - `TST-0042` -> `BKT-ARC` at TST-1.json[41]
  - `TST-0043` -> `BKT-ARC` at TST-1.json[42]
  - `TST-0044` -> `BKT-ARC` at TST-1.json[43]
  - `TST-0045` -> `BKT-ARC` at TST-1.json[44]
  - `TST-0046` -> `BKT-ARC` at TST-1.json[45]
  - `TST-0047` -> `BKT-ARC` at TST-1.json[46]
  - `TST-0048` -> `BKT-ARC` at TST-1.json[47]
  - `TST-0049` -> `BKT-ARC` at TST-1.json[48]
  - `TST-0050` -> `BKT-ARC` at TST-1.json[49]
  - `TST-0051` -> `BKT-ARC` at TST-1.json[50]
  - `WFA-0129` -> `WFA-1of2` at WFA-2.json[0]
  - `WFA-0130` -> `WFA-1of2` at WFA-2.json[1]
  - `WFA-0134` -> `WFA-1of2` at WFA-2.json[5]
  - `WFA-0136` -> `WFA-1of2` at WFA-2.json[7]
  - `WFA-0138` -> `WFA-1of2` at WFA-2.json[9]
  - `WFA-0141` -> `WFA-1of2` at WFA-2.json[12]
  - `WFA-0143` -> `WFA-1of2` at WFA-2.json[14]
  - `WFA-0147` -> `WFA-1of2` at WFA-2.json[18]
  - `WFA-0148` -> `WFA-1of2` at WFA-2.json[19]
  - `WFA-0149` -> `WFA-1of2` at WFA-2.json[20]
  - `WFA-0151` -> `WFA-1of2` at WFA-2.json[22]
  - `WFA-0153` -> `WFA-1of2` at WFA-2.json[24]
  - `WFA-0154` -> `WFA-1of2` at WFA-2.json[25]
  - `WFA-0155` -> `WFA-1of2` at WFA-2.json[26]
  - `WFA-0156` -> `WFA-1of2` at WFA-2.json[27]
  - `WFA-0157` -> `WFA-1of2` at WFA-2.json[28]
- self-dependencies: ['IMP-0274', 'IMP-0277', 'IMP-0299']
- **cycles: 1** [['IMP-0023', 'IMP-0028', 'IMP-0029']]

## 8. Units per phase (all 21 canonical phase ids)

| phase | units |
|---|---:|
| 0 | 122 |
| 1 | 36 |
| 2 | 193 |
| 2A | 85 |
| 2B | 66 |
| 2C | 128 |
| 3 | 77 |
| 4 | 91 |
| 5 | 79 |
| 6 | 64 |
| 7 | 128 |
| 7A | 115 |
| 8 | 26 |
| 9 | 29 |
| 10 | 295 |
| 11 | 186 |
| 12 | 129 |
| 13 | 64 |
| 14 | 51 |
| 15 | 31 |
| 16 | 12 |

Non-canonical phase values: none

## 9. Bucket allocation

- `bucket` field declared on 272/2007 units: {'B10': 144, 'B02': 96, 'B04': 32}
- id-prefix distribution: {'ADV': 144, 'ARC': 112, 'AUD': 96, 'BLD': 64, 'CC': 24, 'CNF': 192, 'CNL': 128, 'IMP': 470, 'REL': 24, 'RES': 193, 'SYN': 48, 'TST': 352, 'WFA': 160}
- spec quota (PHASE-GRAPH.json allocation_buckets, sum 2048): {'B01': 24, 'B02': 96, 'B03': 224, 'B04': 160, 'B05': 128, 'B06': 112, 'B07': 480, 'B08': 352, 'B09': 192, 'B10': 144, 'B11': 64, 'B12': 48, 'B13': 24}

## 10. Detector control (seeded-defect / both-states test)

Verdict: **CONFIRMED** - 10/10 detectors fire on a seeded defect in a scratch copy AND are silent on that same defect in the real corpus. A detector silent in both states measures nothing.

| detector | fires on seeded defect | silent on real corpus | both-states |
|---|---|---|---|
| duplicate_id | YES | YES | PASS |
| missing_required_field | YES | YES | PASS |
| present_but_empty_field | YES | YES | PASS |
| id_format | YES | YES | PASS |
| dangling_dependency | YES | YES | PASS |
| dependency_cycle | YES | YES | PASS |
| exact_duplicate_content | YES | YES | PASS |
| zero_coverage_phase | YES | YES | PASS |
| unparseable_file | YES | YES | PASS |
| jaccard_near_duplicate | YES | YES | PASS |

- `duplicate_id`: seeded id ADV-0001; bad-state dup entries=1, real-state dup entries=0
- `missing_required_field`: field evidence_requirement: bad=1 real=0
- `present_but_empty_field`: field output_path: bad=1 real=0
- `id_format`: bad-state bad-format=['ZZ-77'], real-state bad-format=[]
- `dangling_dependency`: bad-state unresolved=['BLD-0001', 'BLD-0004', 'NOPE-9999', 'TST-0313'], real-state unresolved=0
- `dependency_cycle`: seeded cycle ['CC-0001', 'CC-0002']; bad-state cycles=[['CC-0001', 'CC-0002'], ['IMP-0023', 'IMP-0028', 'IMP-0029']], real-state cycles=[['IMP-0023', 'IMP-0028', 'IMP-0029']] (count=1 - these are GENUINE catalog defects, not control artifacts)
- `exact_duplicate_content`: seeded pair REL-0001==SYN-0001; bad-state exact clusters=1, real-state exact clusters=0
- `zero_coverage_phase`: bad-state zero phases=['16'], real-state zero phases=[]
- `unparseable_file`: bad-state parse failures=['BROKEN-SEED.json'], real-state parse failures=[]
- `jaccard_near_duplicate`: injected an exact clone of ADV-0001 as ZZZ-0001 into the real corpus: pairs>=threshold=1, clustered=True. Un-injected real corpus: pairs>=threshold=0, max pairwise J={'jaccard': 0.4286, 'ids': ['ADV-0091', 'IMP-0318'], 'titles': ['Instant-unanimity trigger: does suspiciously fast agreement force re-evaluation?', 'Instant-unanimity trigger with blind re-evaluation and forced dissent'], 'files': ['ADV-1.json', 'IMP-3.json']}

Seeded corpus unit count: 1995 (real 2007 minus the 12 phase-16 units removed to seed the zero-coverage case, plus 0 added).

## 11. Merge into WORK-UNIT-CATALOG.json

- **action**: PRESERVED (additive)
- **pristine_backup_comparison**: {'backup_present': True, 'backup_sha256': '6a43e6d48c9e69bec011978817590f7c345d4d306aa4fd13b046f42d539a7ef4', 'items_identical_to_pristine_backup': True, 'pristine_items': 103, 'all_pristine_keys_preserved': {'contract': True, 'defaults': True, 'items': True, 'owner_questions': True, 'provenance': True, 'schema_version': False, 'terminal_dispositions': True}}
- **pre_merge_sha256**: e245f529f4fef9c34e82cf58e70f8fcdfc78d05385fe44092c53b9c936848cfd
- **post_merge_sha256**: ef34e1561d86649b32924d064d73f05d940b71eb160ca3e77531dca35aa7f17c
- **items_before**: 103
- **items_after**: 103
- **items_identical**: True
- **other_preexisting_keys_identical**: True
- **work_units_after**: 2007
- **roundtrip_parses**: True