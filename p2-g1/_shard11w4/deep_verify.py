import json, os, hashlib
repo = r'C:\Users\Prekzursil\p2-g1'
BS = chr(92)
ids = ['IMP-0261','IMP-0264','IMP-0269','IMP-0270','IMP-0271','IMP-0272','IMP-0273','IMP-0274','IMP-0275','IMP-0279','IMP-0303','IMP-0304']

def sha_lf(p):
    raw = open(p,'rb').read().replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()

def norm(p):
    return p.replace(BS, '/')

with open(os.path.join(repo,'command-center','WORK-UNIT-CATALOG.json'), encoding='utf-8') as f:
    cat = json.load(f)
units = {u['id']: u for u in cat['work_units'] if u.get('id') in ids}

summary = {}
for uid in ids:
    rcpt_p = os.path.join(repo,'command-center','receipts',uid+'.json')
    with open(rcpt_p, encoding='utf-8') as f:
        d = json.load(f)
    u = units[uid]
    issues = []
    gated = u.get('owner_approval_required', False)
    rv = d.get('reviewer') or {}
    rv_ok = isinstance(rv, dict) and rv.get('verdict')=='PASS' and rv.get('independent') is True
    if not rv_ok: issues.append('reviewer-closure-missing')
    missing_art = []
    for ap in d.get('artifact_paths') or []:
        p = ap if os.path.isabs(ap) else os.path.join(repo, ap)
        if not os.path.isfile(p): missing_art.append(ap)
    if missing_art: issues.append('artifact-paths-missing:'+repr(missing_art))
    man_p = os.path.join(repo,'command-center','p2-wave','probes',uid,'UNIT-ARTIFACT-MANIFEST.json')
    with open(man_p, encoding='utf-8') as f:
        man = json.load(f)
    rows = { norm(a.get('path') or ''): a for a in man.get('artifacts',[]) if isinstance(a,dict)}
    sha_bad = []
    for ap in d.get('artifact_paths') or []:
        rel = norm(ap)
        row = rows.get(rel)
        if row is None:
            sha_bad.append(rel+':NO-ROW'); continue
        p = ap if os.path.isabs(ap) else os.path.join(repo, ap)
        if os.path.isfile(p) and row.get('sha256') != sha_lf(p):
            sha_bad.append(rel+':SHA-MISMATCH')
    if sha_bad: issues.append('manifest:'+repr(sha_bad))
    summary[uid] = {'gated': gated, 'rv_ok': rv_ok, 'rv_fields': sorted(rv.keys()) if isinstance(rv,dict) else [], 'artifacts': d.get('artifact_paths'), 'issues': issues}
    print(uid, '| gated=', gated, '| reviewer_ok=', rv_ok, '| rv_fields=', sorted(rv.keys()) if isinstance(rv,dict) else None)
    print('    artifacts:', d.get('artifact_paths'))
    print('    issues:', issues if issues else 'NONE')

with open(os.path.join(repo,'_shard11w4','deep_verify_summary.json'),'w',encoding='utf-8') as f:
    json.dump(summary, f, indent=1)
