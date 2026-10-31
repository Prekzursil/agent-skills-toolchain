import json

s = json.load(open('platform/schema/artifact-class-profiles.schema.json', encoding='utf-8'))
defs = s.get('$defs') or {}
d = defs.get('supply-chain-attestation') or {}
print('def keys:', list(d.keys()))
print('required:', d.get('required'))
props = d.get('properties') or {}
print('props:', sorted(props.keys()))
# find nested requireds
def walk(node, path=""):
    if isinstance(node, dict):
        req = node.get('required')
        if req:
            print(f'REQUIRED at {path}:', req)
        for k, v in node.items():
            walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]")
walk(d)
