import json, os, sys
repo = r'C:\Users\Prekzursil\p2-g1'
sys.path.insert(0, os.path.join(repo, 'platform', 'lib'))
os.environ['AST_INTEGRATE_ROOT'] = repo
import schema_resolver as sr
cat = json.load(open(os.path.join(repo, 'command-center', 'WORK-UNIT-CATALOG.json'), encoding='utf-8'))
wu = {u['id']: u for u in cat['work_units']}
mine = ['TST-0206','TST-0215','TST-0219','TST-0221','TST-0223','TST-0227','TST-0230','TST-0233']
for uid in mine:
    decl = wu[uid]['output_schema']
    try:
        rs = sr.resolve(decl)
        print(uid, '| resolves:', rs.resolves, '| kind:', rs.kind, '| fragment:', rs.fragment,
              '| shim:', rs.shim_exists, '| physical:', rs.physical_exists)
    except Exception as e:
        print(uid, '| RESOLVE FAIL:', type(e).__name__, str(e)[:150])
