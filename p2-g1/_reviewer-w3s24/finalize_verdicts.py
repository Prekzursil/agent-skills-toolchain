import json
p = 'C:/Users/Prekzursil/p2-g1/_reviewer-w3s24/verdicts.json'
out = json.load(open(p, encoding='utf-8'))
fr = ('receipt contradicts its own SUCCESS state: open P1 defect TST0215-F1 '
      '(router steerable by planted capability prose; live probe1 today shows planted_capability_selected=true, so the defect is live-true, not stale); '
      '3 tests recorded result=FAIL (routing-invariance, tool-sequence-invariance, condition-11); '
      'manifest_registration.registered=false; sole downstream consumer executed=false/read_ok=false; '
      'embedded reviewer notes record blocking conditions c1,c3,c5,c7,c10,c11 UNSATISFIED at closure while verdict=PASS. '
      'Fails receipt_core allOf[0] not-contains rules (open P0/P1 defect, FAIL test rows, executed=false consumer, registered=false) '
      'and completion conditions 7/10/11/12. Receipt left byte-unchanged per FAIL contract.')
out['verdicts']['TST-0215']['fail_reason'] = fr
out['method'] = ('two mechanically independent instruments per check: (1) program canonical measure '
                 '_measure_one_delivered.py (artifact/parse/not-blocked/sentinel + named probes re-run exit 0 + manifest sha CRLF-normalized match) -> SUCCESS:delivered on all 8; '
                 '(2) direct native probe re-execution outside the wrapper (16/16 exit 0) + independent sha256 recomputation + receipt field audit; '
                 'schema lane: program resolver resolve() (all 8 declared output_schemas resolve, canonical-receipt; fragments security_report x6, benchmark_result x2) '
                 '+ jsonschema Draft2020-12 validation via receipt_schema_gate --schema-only, errors classified per the live-gate policy')
out['policy_basis'] = ('tools/command-center/receipt_gate.py: C2 schema-invalid on known-id historical receipts is reported as schema_drift census '
                       '(the live gate schema tightened after the historical receipts were closed), NOT gating; gating classes C1/C3/C4. '
                       'Wave-2 shard-24 r2 reviewer precedent: envelope drift recorded-not-gating, content (open P0/P1, registered=false, FAIL test rows) gating FAIL. '
                       'Wave-3 sibling PASS closures (e.g. w3s4 AUD-0044, which is C2-invalid today) ride the same drift census.')
json.dump(out, open(p, 'w', encoding='utf-8'), indent=1)
print('final patch done; bytes:', len(open(p, encoding='utf-8').read()))
