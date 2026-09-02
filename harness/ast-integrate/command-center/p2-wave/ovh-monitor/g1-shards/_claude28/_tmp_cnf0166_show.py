import json
import pathlib

REPO = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate')
p = REPO / 'command-center/receipts/CNF-0166.json'
doc = json.loads(p.read_text(encoding='utf-8'))
print('tests type:', type(doc.get('tests')).__name__)
print('tests:', json.dumps(doc.get('tests'))[:600])


def find_key(obj, key, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and path:
                print('nested', key, 'at', path, type(v).__name__, json.dumps(v)[:300])
            find_key(v, key, path + '/' + k)
    elif isinstance(obj, list):
        for i, it in enumerate(obj[:20]):
            find_key(it, key, path + '[%d]' % i)


find_key(doc, 'known_dead')
find_key(doc, 'both_states')
probes = sorted(x.name for x in (REPO / 'command-center/p2-wave/probes/CNF-0166').iterdir())
print('probes dir:', probes)
