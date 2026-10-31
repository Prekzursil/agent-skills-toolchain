import sys, json
sys.path.insert(0, 'C:/Users/Prekzursil/p2-g1/platform/lib')
import schema_resolver as sr
v = sr.validator_for('command-center/schema/audit-inventory.schema.json')
sch = v.schema
DEFSKEY = chr(36) + 'defs'
def walk(s, path=''):
    if isinstance(s, dict):
        if 'required' in s:
            print('required at', path or '<root>', ':', s['required'])
        props = s.get('properties')
        if isinstance(props, dict):
            for k in ('state', 'timestamps', 'status'):
                if k in props:
                    print(k, 'spec at', path, ':', json.dumps(props[k])[:280])
        for kk, vv in s.items():
            if kk in ('properties', 'defs', DEFSKEY) and isinstance(vv, dict):
                for name, sub in vv.items():
                    walk(sub, path + '/' + name)
            elif kk in ('allOf', 'anyOf', 'oneOf') and isinstance(vv, list):
                for i, sub in enumerate(vv):
                    walk(sub, path + '/' + kk + str(i))
            elif kk == 'items' and isinstance(vv, dict):
                walk(vv, path + '/items')
            elif kk in ('if', 'then', 'else') and isinstance(vv, dict):
                walk(vv, path + '/' + kk)
walk(sch)
print('---top keys:', sorted(sch.keys()))
