import json, hashlib, os, sys
REPO=os.path.dirname(os.path.abspath(os.path.dirname(os.path.abspath(__file__))))  # p2-g1 root
REPO=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
IDS=['AUD-0043','AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075']
cat=json.load(open(os.path.join(REPO,'command-center','WORK-UNIT-CATALOG.json'),encoding='utf-8'))
wu={u.get('id'):u for u in cat['work_units'] if isinstance(u,dict)}

def norm(b): return b.replace(b'\r\n',b'\n')

results={}
for uid in IDS:
    e=wu[uid]
    out=e['output_path']; schema=e['output_schema']
    p=os.path.join(REPO,out.replace('/',os.sep))
    checks={'output_path':out,'schema':schema}
    checks['exists']=os.path.isfile(p)
    if checks['exists']:
        raw=open(p,'rb').read()
        checks['bytes']=len(raw); checks['nonempty']=len(raw)>0
        try:
            art=json.loads(raw.decode('utf-8'))
            checks['parses']=True
        except Exception as ex:
            art=None; checks['parses']=False; checks['parse_err']=str(ex)
        if art is not None:
            st=art.get('state'); vd=art.get('verdict')
            checks['artifact_state']=st; checks['artifact_verdict']=vd
            checks['not_self_blocked']=not (st in ('BLOCKED','FAILED') or vd in ('BLOCKED','FAILED'))
            checks['completion_sentinel_present']=bool(art.get('completion_sentinel'))
    # manifest sha
    mp=os.path.join(REPO,'command-center','p2-wave','probes',uid,'UNIT-ARTIFACT-MANIFEST.json')
    mf=json.load(open(mp,encoding='utf-8'))
    prim=[a for a in mf['artifacts'] if a.get('role')=='primary' and a.get('path')==out]
    checks['manifest_primary_rows']=len(prim)
    if prim:
        checks['manifest_sha']=prim[0]['sha256']
    if checks.get('exists') and checks.get('parses'):
        live=hashlib.sha256(norm(raw)).hexdigest()
        rawsha=hashlib.sha256(raw).hexdigest()
        checks['recomputed_sha_norm']=live

        checks['recomputed_sha_raw']=rawsha
        checks['sha_match_manifest_norm']=(live==checks.get('manifest_sha'))
        checks['sha_match_manifest_raw']=(rawsha==checks.get('manifest_sha'))
    # receipt artifact sha claim
    rp=os.path.join(REPO,'command-center','receipts',uid+'.json')
    r=json.load(open(rp,encoding='utf-8'))
    rarts=r.get('artifacts') or []
    ra=[a for a in rarts if a.get('path')==out and a.get('role')=='primary']
    checks['receipt_primary_rows']=len(ra)
    if ra: checks['receipt_sha']=ra[0].get('sha256'); checks['receipt_bytes']=ra[0].get('bytes')
    if checks.get('exists') and ra:
        checks['sha_match_receipt']=((checks.get('receipt_sha')==checks.get('manifest_sha')) )
    results[uid]=checks
json.dump(results,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'static_sha_results.json'),'w'),indent=1)
for uid in IDS:
    c=results[uid]
    ok=c['exists'] and c.get('nonempty') and c.get('parses') and c.get('not_self_blocked') and c.get('sha_match_manifest_norm') and c.get('sha_match_receipt', c.get('manifest_sha')==c.get('receipt_sha'))
    print(uid,'PASS' if ok else 'FAIL', '| state=%s bytes=%s sha_norm_match=%s receipt_sha_match=%s'%(c.get('artifact_state'),c.get('bytes'),c.get('sha_match_manifest_norm'),c.get('receipt_sha')==c.get('manifest_sha')))
