# G-1 until-green census (handoff)

Date: 26.08.2026  
Status: **NOT GREEN**. Full catalog remesured this turn. `complete()` requires n==2007 and ok==2007 and fail==0.

## Literal fields (copy these)

Source files:
- `command-center/p2-wave/ovh-monitor/g1-local-full.json`
- `command-center/p2-wave/ovh-monitor/g1-shards/classes.json`

| field | value |
|---|---|
| n | 2007 |
| ok | 1053 |
| fail | 954 |
| remaining_n | 954 |
| remaining_fp | 0c83903632558beea8a3c7f8f3142ef5131e20a39f57db21a420b9258b508cc4 |
| remaining_path | C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\remaining_ids.txt |

## Dual-signal verification (this turn)

Python recount of `g1-local-full.jsonl` vs `WORK-UNIT-CATALOG.json` vs remaining_ids SHA256:

- catalog work_units = 2007
- jsonl lines = 2007, unique ids = 2007, missing from catalog = 0, extra = 0
- jsonl ok = 1053, jsonl fail = 954
- summary json n/ok/fail = 2007/1053/954, ts = 2026-08-26T04:08:30Z, resume = true, jsonl_unique = 2007
- heartbeat done = 2007, resume_finished = 565
- remaining_ids.txt lines = 954
- SHA256(remaining_ids.txt) = 0c83903632558beea8a3c7f8f3142ef5131e20a39f57db21a420b9258b508cc4 (equals remaining_fp)
- remaining id set equals jsonl fail id set
- shard sizes sum = 954 (18 shards of 40 + 6 shards of 39)

File hashes at verification:

- g1-local-full.json sha256 445dbd61addd8cd496ac72b2ade89cafa81ae7cc255ce4e904347e7ca60e9ce9 (1674 bytes, 2026-08-26T07:08:30)
- g1-local-full.jsonl sha256 a7f31dd1866fef570086241790edfeb738bb713d765e3503ddfc52f185abc0ea (2158934 bytes)
- classes.json sha256 18ef2d87749f29c406da8cd49057f431dc695e3cfd7c390569fdc75ff36f2749 (846 bytes, 2026-08-26T07:14:08)
- remaining_ids.txt sha256 0c83903632558beea8a3c7f8f3142ef5131e20a39f57db21a420b9258b508cc4 (9534 bytes)

Ok detector is live, not silent. Jsonl last-lines include:

- SUCCESS:delivered ADV-0007
- SUCCESS:delivered ADV-0008
- SUCCESS:delivered ADV-0013
- SUCCESS:delivered ADV-0005
- SUCCESS:delivered ADV-0016

## How remesure ran (not a skip)

1. `wsl.exe bash -lc 'bash /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/seed-stage/_g1_rsync.sh'` → RSYNC-OK, 4.4G `/home/prekzursil/p2-g1`.
2. `export AST_INTEGRATE_ROOT=$HOME/p2-g1; python3 $HOME/p2-g1/command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py` → SUCCESS:schema-file-ids files=246 replacements=816 base=file:///home/prekzursil/p2-g1/.
3. `export G1_WORKERS=16; cd $HOME/p2-g1; python3 -u command-center/p2-wave/seed-stage/g1_remeasure_all.py`. Wrapper killed at 1442 unique jsonl rows (no summary yet).
4. Resume without wiping jsonl: remaining 565 catalog ids measured and appended. Heartbeat resume_todo=565 resume_finished=565. Then summary written.
5. In REPO: `python command-center/p2-wave/seed-stage/_g1_mod_census.py` then `python command-center/p2-wave/seed-stage/_write_g1_classes.py`.

Windows python cannot run G-1 (Unix `resource`). Measure ran in WSL. G-1 unit SUCCESS is only last line `SUCCESS:delivered <ID>` from `_measure_one_delivered.py`. This census does not invent that for remaining units.

## classes.json buckets (copy)

```json
{
  "mod": 17,
  "probe-missing": 4,
  "probe-exit": 919,
  "schema": 4,
  "sha": 3,
  "sentinel": 1,
  "predicate": 5,
  "output": 0,
  "env": 1,
  "other": 0
}
```

## measure cls (g1-local-full.json / jsonl / g1-mod-census.json)

```json
{
  "SUCCESS": 1053,
  "probe-exit": 924,
  "ModuleNotFoundError": 17,
  "probe-file-missing": 4,
  "schema-ref": 4,
  "manifest-sha-mismatch": 3,
  "predicate": 2
}
```

`_write_g1_classes.py` rebuckets some probe-exit rows (924 → 919) into sentinel/predicate/env/probe-missing.

## Fail evidence (first jsonl row per measure cls)

- probe-exit n=924 first=ADV-0009 last=`FAILED:delivered ADV-0009 probe-exit:1` tail=`AttributeError: 'dict' object has no attribute 'flagged'`
- ModuleNotFoundError n=17 first=IMP-0038 last=`FAILED:delivered IMP-0038 probe-exit:1` tail=`ModuleNotFoundError: No module named 'registration_reconciler'`
- probe-file-missing n=4 first=ADV-0041 last=`FAILED:delivered ADV-0041 probe-exit:1` tail=`FileNotFoundError: .../probes/ADV-0041/scratch/real-plugin.zip` (fixture, not missing probe .py)
- schema-ref n=4 first=ARC-0102 last=`FAILED:delivered ARC-0102 probe-exit:1` tail=`https://ast-integrate.invalid/schema/common/identity.json` → `/home/prekzursil/p2-g1/schema/common/identity.json`
- manifest-sha-mismatch n=3 first=ARC-0024 last=`FAILED:delivered ARC-0024 manifest-sha-mismatch` (probe printed `SUCCESS:ARC-0024-probe2 budget REFUSE` then envelope failed sha)
- predicate n=2 first=ARC-0052 last=`FAILED:delivered ARC-0052 predicate:absent`

## Missing modules (17, one unit each)

registration_reconciler, foundry.stage_extract, foundry.oracle, workflow_foundry.blueprint_contract, council.participants.select_adversarial, crossvendor.divergence, vendor_adapter.negotiate, worktree_shard.provisioner, detectors.campaign, synthesis.digest_loss, lib.completion_reducer, monitorcore.operator_surface, records, lib.codex_invocation, tools.cross_vendor.parity_bench, testinfra.test_entry_parity, wfa_compat.check

## Shards

n_shards: 24  
sizes: [40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 39, 39, 39, 39, 39, 39]
