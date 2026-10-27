import json, os, sys, hashlib
ROOT = os.path.expanduser('~/p2-g1')
os.chdir(ROOT)
MINE = ['TST-0032','TST-0057','TST-0060','TST-0066','TST-0067','TST-0068',
        'TST-0070','TST-0081','TST-0085','TST-0088','TST-0090','TST-0091']
sys.path.insert(0, os.path.join(ROOT, 'platform', 'lib'))
import schema_resolver

def jl(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def sha_norm(path):
    with open(path, 'rb') as f:
        b = f.read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

def raw_sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

cat = jl('command-center/WORK-UNIT-CATALOG.json')
byid = {u['id']: u for u in cat['work_units'] if isinstance(u, dict) and 'id' in u}
out = {}
for uid in MINE:
    row = {'checks': {}, 'detail': {}}
    e = byid.get(uid)
    row['checks']['catalog_entry'] = bool(e)
    if not e:
        out[uid] = row
        print('BATTERY', uid, 'NO-CATALOG-ENTRY')
        continue
    op, osch = e.get('output_path'), e.get('output_schema')
    row['detail']['output_path'] = op
    row['detail']['output_schema'] = osch
    row['detail']['owner_approval_required'] = e.get('owner_approval_required')
    row['detail']['dependencies'] = e.get('dependencies')

    ap = os.path.join(ROOT, op.replace('/', os.sep))
    art = None
    if not os.path.isfile(ap):
        row['checks']['artifact_exists'] = False
    else:
        row['checks']['artifact_exists'] = True
        size = os.path.getsize(ap)
        row['checks']['artifact_nonempty'] = size > 0
        row['detail']['bytes_on_disk'] = size
        try:
            art = jl(ap)
            row['checks']['artifact_parses'] = True
            st = art.get('state')
            row['detail']['state'] = st
            row['checks']['not_self_blocked'] = st not in ('BLOCKED', 'FAILED')
            rev = art.get('reviewer') or {}
            row['detail']['receipt_reviewer'] = {
                'verdict': rev.get('verdict'),
                'independent': rev.get('independent'),
                'id': rev.get('id') or rev.get('review_id'),
            }
            row['checks']['receipt_core_ok'] = (
                not (st == 'SUCCESS') or (rev.get('verdict') == 'PASS' and rev.get('independent') is True))
        except Exception as ex:
            row['checks']['artifact_parses'] = False
            row['detail']['parse_err'] = str(ex)[:200]

    mp = os.path.join(ROOT, 'command-center', 'p2-wave', 'probes', uid, 'UNIT-ARTIFACT-MANIFEST.json')
    try:
        man = jl(mp)
        rows = []
        for a in man.get('artifacts', []):
            rp = os.path.join(ROOT, a['path'].replace('/', os.sep))
            if not os.path.isfile(rp):
                rows.append({'path': a['path'], 'present_on_disk': False,
                             'role': a.get('role'), 'match': False})
                continue
            live = sha_norm(rp)
            raw = raw_sha(rp)
            rows.append({'path': a['path'], 'role': a.get('role'),
                         'match': live == a['sha256'],
                         'match_raw': raw == a['sha256'],
                         'live_sha': live, 'manifest_sha': a['sha256'],
                         'bytes_manifest': a.get('bytes'),
                         'bytes_on_disk': os.path.getsize(rp)})
        row['detail']['manifest_rows'] = rows
        prim = [r for r in rows if r.get('role') == 'primary']
        row['checks']['manifest_primary_sha_match'] = bool(prim) and prim[0].get('match') is True
        row['checks']['manifest_all_rows_match'] = bool(rows) and all(r.get('match') is True for r in rows)
    except Exception as ex:
        row['checks']['manifest_readable'] = False
        row['detail']['manifest_err'] = str(ex)[:200]

    if art is not None:
        try:
            errs = schema_resolver.validate_artifact(art, osch)
            row['detail']['schema_violations_n'] = len(errs)
            row['detail']['schema_violations_sample'] = errs[:3]
            row['checks']['output_schema_valid'] = len(errs) == 0
        except Exception as ex:
            row['checks']['output_schema_valid'] = False
            row['detail']['schema_resolver_err'] = str(ex)[:250]

    try:
        sr = jl('command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json' % uid)
        row['detail']['sr_status'] = sr.get('status')
        row['detail']['sr_state'] = sr.get('state')
        row['detail']['sr_sentinel'] = sr.get('sentinel')
        row['detail']['named_probes_n'] = len(sr.get('named_probes') or [])
    except Exception as ex:
        row['detail']['sr_err'] = str(ex)[:150]

    out[uid] = row
    fails = [k for k, v in row['checks'].items() if v is not True]
    print('BATTERY', uid, '| checks:', row['checks'], '| FAILING:' if fails else 'ALL-HOLD', fails, flush=True)

with open(os.path.join(ROOT, '_p2-shard17-w4-review', 'battery_results.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1)
print('BATTERY COMPLETE')
