import json, hashlib, os, sys
from jsonschema import Draft202012Validator, Draft7Validator

ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
IDS = ["ADV-0127","ADV-0128","ARC-0001","ARC-0012","ARC-0013","ARC-0015","ARC-0019","ARC-0020","ARC-0021","ARC-0047","ARC-0048","ARC-0054"]

cat = json.load(open('command-center/WORK-UNIT-CATALOG.json', encoding='utf-8'))
byid = {u['id']: u for u in cat['work_units']}

def sha_lf(path):
    b = open(path,'rb').read()
    b = b.replace(b'\r\n', b'\n')
    return hashlib.sha256(b).hexdigest(), len(b)

def sha_raw(path):
    b = open(path,'rb').read()
    return hashlib.sha256(b).hexdigest(), len(b)

def load_schema(p):
    s = json.load(open(p, encoding='utf-8'))
    return s

results = {}
for uid in IDS:
    u = byid[uid]
    res = {'id': uid, 'checks': {}}
    op = u['output_path']
    # 1. artifact exists / non-empty / parses / not self-blocked
    try:
        if not os.path.exists(op):
            raise AssertionError(f'artifact missing: {op}')
        raw = open(op,'rb').read()
        if len(raw) == 0:
            raise AssertionError('artifact empty')
        art = json.loads(raw.decode('utf-8'))
        res['checks']['artifact_exists_nonempty_parses'] = True
        # self-declared BLOCKED/FAILED scan
        bad = []
        def scan(node, path=''):
            if isinstance(node, dict):
                for k,v in node.items():
                    if k in ('state','verdict','status') and isinstance(v,str) and v.upper() in ('BLOCKED','FAILED'):
                        bad.append(f'{path}{k}={v}')
                    scan(v, path+k+'.')
            elif isinstance(node, list):
                for i,v in enumerate(node): scan(v, path)
        scan(art)
        res['checks']['self_block_fields'] = bad
        res['artifact_bytes'] = len(raw)
    except Exception as e:
        res['checks']['artifact_exists_nonempty_parses'] = False
        res['artifact_error'] = str(e)
        results[uid] = res
        continue
    # 2. schema validation
    sp = u.get('output_schema')
    try:
        schema = load_schema(sp)
        try:
            v = Draft202012Validator(schema)
            errs = sorted(v.iter_errors(art), key=lambda e: list(e.path))
        except Exception:
            v = Draft7Validator(schema)
            errs = sorted(v.iter_errors(art), key=lambda e: list(e.path))
        if errs:
            res['checks']['schema_valid'] = False
            res['schema_errors'] = [f"{list(e.path)}: {e.message[:220]}" for e in errs[:8]]
        else:
            res['checks']['schema_valid'] = True
    except Exception as e:
        res['checks']['schema_valid'] = False
        res['schema_errors'] = [f'schema-load-failed: {e}']
    # 3. manifest sha match (CRLF->LF normalized)
    mp = f'command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json'
    try:
        man = json.load(open(mp, encoding='utf-8'))
        rows = man.get('artifacts', [])
        mism, okn = [], 0
        primary_ok = False
        for row in rows:
            rp = row['path']
            if not os.path.exists(rp):
                mism.append(f'{rp}: MISSING')
                continue
            h_raw, _ = sha_raw(rp)
            h_lf, _ = sha_lf(rp)
            if row.get('sha256') in (h_lf, h_raw):
                okn += 1
                if row.get('role') == 'primary' and rp == op and row.get('sha256') == h_lf:
                    primary_ok = True
            else:
                mism.append(f"{rp}: manifest={row.get('sha256','')[:16]} live_lf={h_lf[:16]} live_raw={h_raw[:16]} role={row.get('role')}")
        res['checks']['manifest_rows_total'] = len(rows)
        res['checks']['manifest_rows_ok'] = okn
        res['checks']['manifest_primary_lf_match'] = primary_ok
        res['checks']['manifest_mismatches'] = mism
    except Exception as e:
        res['checks']['manifest_error'] = str(e)
    results[uid] = res

json.dump(results, open('_reviewer-w4s2/static_results.json','w', encoding='utf-8'), indent=1)
for uid, r in results.items():
    c = r['checks']
    line = f"{uid}: artifact={c.get('artifact_exists_nonempty_parses')} schema={c.get('schema_valid')} primary_lf={c.get('manifest_primary_lf_match')} rows={c.get('manifest_rows_ok')}/{c.get('manifest_rows_total')} selfblock={c.get('self_block_fields')}"
    print(line)
    for m in (c.get('manifest_mismatches') or [])[:4]:
        print('   MISMATCH:', m)
    for e in (r.get('schema_errors') or [])[:4]:
        print('   SCHEMA:', e)
