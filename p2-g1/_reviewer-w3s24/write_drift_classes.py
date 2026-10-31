import json
drift = {
 'TST-0206': ['envelope: evidence[2],evidence[3] legacy shape (missing anchor/confidence/probes, extra id prop); rows are detector-name bookkeeping'],
 'TST-0215': [
   'CONTENT: open P1 defect TST0215-F1 attached to SUCCESS receipt (gate c10); live probe1 today still shows planted_capability_selected=true so the defect is real, not stale',
   'CONTENT: tests carry 3 result=FAIL rows: TST0215-ROUTING-INVARIANCE, TST0215-TOOL-SEQUENCE-INVARIANCE, TST0215-CONDITION-11 (gate c7)',
   'CONTENT: manifest_registration.registered=false (gate c11); own live condition-11 check row result=FAIL',
   'CONTENT: sole downstream_consumer recorded executed=false/read_ok=false (gate c12)',
   'CONTENT: embedded reviewer.notes record blocking conditions c1,c3,c5,c7,c10,c11 UNSATISFIED at closure, yet verdict=PASS'],
 'TST-0219': ['envelope: downstream_consumers[0] executed=false/read_ok=false; canonical consumer _measure_one_delivered.py re-executed green by this reviewer 2026-10-26'],
 'TST-0221': ['envelope: evidence[0]/evidence[1] probe arrays single-role (source/verifier split across rows; tightened schema wants both per CONFIRMED row)',
              'envelope: downstream_consumers[0] missing probe field'],
 'TST-0223': ['envelope: receipt predates tightened envelope - negative_controls/downstream_consumers/manifest_registration/residual_unknowns sections absent, schema_version absent',
              'note: substance re-verified live instead - probe1 bad_mutant 5000-violation red, probe2 deep-refusal red, manifest sha live-matched, canonical consumer executed green'],
 'TST-0227': ['envelope: negative_controls[0].kind=both-states not in tightened enum',
              'envelope: downstream_consumers[0] executed=false/read_ok=false (canonical consumer re-executed green by this reviewer)',
              'envelope: manifest_registration extra prop derivation'],
 'TST-0230': ['envelope: evidence[0]/evidence[2] probe arrays single-role (source/verifier split across rows)'],
 'TST-0233': ['envelope: negative_controls kinds detector-control/false-positive-control/regression-seed not in tightened enum',
              'envelope: negative_controls[1] false-positive-control fired_on_bad_state=false - correct control behavior rejected by blanket tightened not-contains rule',
              'envelope: downstream_consumers[0] executed=false/read_ok=false (canonical consumer re-executed green by this reviewer)',
              'envelope: manifest_registration extra prop global_unit_manifest_write'],
}
json.dump(drift, open('C:/Users/Prekzursil/.claude/temp_drift.json', 'w', encoding='utf-8'), indent=1)
print('drift written')
