import json, os, sys
sys.path.insert(0, os.path.abspath('platform/lib'))
import schema_resolver as SR

IDS=['AUD-0043','AUD-0044','AUD-0047','AUD-0053','AUD-0055','AUD-0057','AUD-0064','AUD-0066','AUD-0069','AUD-0071','AUD-0072','AUD-0075']
cat=json.load(open('command-center/WORK-UNIT-CATALOG.json',encoding='utf-8'))
wu={u.get('id'):u for u in cat['work_units'] if isinstance(u,dict)}
out={}
for uid in IDS:
    e=wu[uid]; declared=e['output_schema']
    art=json.load(open(e['output_path'],encoding='utf-8'))
    try:
        res=SR.resolve(declared, SR.load_registry())
        resinfo=res.as_dict()
    except SR.SchemaResolutionError as ex:
        out[uid]={'resolve_error':str(ex)}; print(uid,'RESOLVE-ERROR',str(ex)[:120]); continue
    errs=SR.validate_artifact(art, declared)
    out[uid]={'resolved':resinfo,'error_count':len(errs),'errors_first5':errs[:5]}
    print(uid,'errors:',len(errs))
    for m in errs[:5]: print('   ',m[:200])
json.dump(out,open('_rev-w2-shard4-r2/schema_results.json','w',encoding='utf-8'),indent=1)
