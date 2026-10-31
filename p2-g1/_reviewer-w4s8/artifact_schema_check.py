import json, os, sys
os.chdir(os.path.expanduser('~/p2-g1'))
import jsonschema
mine = ['IMP-0002','IMP-0006','IMP-0022','IMP-0031','IMP-0035','IMP-0036','IMP-0037','IMP-0038','IMP-0041','IMP-0044','IMP-0051','IMP-0068']
cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}
BS = chr(92)
BAD_STATES = {'BLOCKED','FAILED','SEVERED','TIMEOUT'}
fails = {}
for uid in mine:
    e = byid[uid]
    op = str(e['output_path']).replace(BS,'/')
    probs = []
    art = None
    try:
        size = os.path.getsize(op)
        if size == 0: probs.append('artifact empty')
        art = json.load(open(op, encoding='utf-8'))
    except Exception as ex:
        probs.append(f'parse: {ex}')
        art = None
    if isinstance(art, dict):
        st = art.get('state')
        if st in BAD_STATES: probs.append(f'self-declared state={st}')
        # any nested self-block markers
        s = json.dumps(art)
        for marker in ('"state": "BLOCKED"', '"verdict": "BLOCKED"', '"status": "BLOCKED"'):
            if marker in s: probs.append(f'nested marker {marker}')
        if art.get('unit_id') != uid: probs.append(f"unit_id mismatch: {art.get('unit_id')}")
        rv = art.get('reviewer') or {}
        if not (rv.get('verdict') == 'PASS'): probs.append(f"reviewer.verdict={rv.get('verdict')!r}")
        if rv.get('independent') is not True: probs.append('reviewer.independent != true')
        if st != 'SUCCESS': probs.append(f'state={st} (expected SUCCESS)')
        if art.get('sentinel') != e.get('completion_sentinel'):
            probs.append(f"sentinel mismatch: {art.get('sentinel')!r}")
        # schema validation: primary schema = first path before ' + '
        sch_field = str(e['output_schema'])
        primary = sch_field.split(' + ')[0].replace(BS,'/')
        try:
            schema = json.load(open(primary, encoding='utf-8'))
            jsonschema.validate(art, schema)
        except jsonschema.ValidationError as ex:
            probs.append(f'schema-FAIL({os.path.basename(primary)}): {str(ex.message)[:160]}')
        except Exception as ex:
            probs.append(f'schema-unreadable({primary}): {str(ex)[:120]}')
        # secondary schema if present
        if ' + ' in sch_field:
            sec = sch_field.split(' + ', 1)[1].split(' ')[0].replace(BS,'/')
            try:
                schema2 = json.load(open(sec, encoding='utf-8'))
                jsonschema.validate(art, schema2)
            except jsonschema.ValidationError as ex:
                probs.append(f'schema2-FAIL({os.path.basename(sec)}): {str(ex.message)[:160]}')
            except Exception as ex:
                probs.append(f'schema2-unreadable({sec}): {str(ex)[:120]}')
    else:
        probs.append('artifact not a JSON object')
    print(f"{uid}: {'ALL-HOLD' if not probs else 'ISSUES: ' + ' | '.join(probs)}")
    if probs: fails[uid] = probs
print()
print('ARTIFACT/SCHEMA/RECEIPT RESULT:', 'ALL 12 ALL-HOLD' if not fails else f'{len(fails)} units with issues: {list(fails)}')
json.dump(fails, open('_reviewer-w4s8/artifact_schema_issues.json','w'), indent=1)
