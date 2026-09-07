# P2 loop-to-green orchestration

## Hard bar
`python command-center/p2-loop/census.py` must report `owner_hard_bar_met: true`
(green_SUCCESS == catalog_units == 2007). No WARN-as-green. No placeholder reviewer PASS.

## Loop
1. `python command-center/ready_units.py`
2. `python command-center/p2-loop/rank_ready.py --limit 40`
3. Dispatch implementers on top OQ-2 READY units (phase then unblocking power)
4. Independent fresh-context review (cross-vendor when catalog requires)
5. Promote BLOCKED→SUCCESS only after review PASS + admission (`receipt_validate.py`)
6. Re-census; refresh READY; repeat

## Anti-patterns (banned)
- Nesting `harness/ast-integrate/`
- Minting SUCCESS with fake reviewer / invented probe output
- Weakening schema or census predicates to get green

## Wave 1
High-leverage phase-0: IMP-0434 (atomic writer), CC-0003 (completion predicate packaging),
AUD measurement units. See WAVE-STATE.json.
