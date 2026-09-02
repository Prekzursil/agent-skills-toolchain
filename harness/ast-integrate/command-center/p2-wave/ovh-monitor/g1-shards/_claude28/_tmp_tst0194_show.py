import json
import pathlib
import unicodedata

REPO = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate')
HERE = REPO / 'command-center/p2-wave/probes/TST-0194'


def posix_rel(p):
    t = str(p).replace('\\', '/')
    if t.startswith('./'):
        t = t[2:]
    return t.lstrip('/')


data = json.loads((HERE / 'fixtures/colliding/manifest.json').read_text(encoding='utf-8'))
paths = [posix_rel(str(x)) for x in (data.get('files') or [])]
raw = [posix_rel(p) for p in paths if posix_rel(p)]
folded = {unicodedata.normalize('NFC', posix_rel(p)).casefold() for p in raw}
print('colliding raw_count:', len(raw), 'folded_count:', len(folded))

doc = json.loads((REPO / 'command-center/receipts/TST-0194.json').read_text(encoding='utf-8'))
for e in doc.get('evidence') or []:
    print(json.dumps(e)[:400])
    print('~~~~')
print('report_kind:', doc.get('report_kind'), '| overall_verdict:', doc.get('overall_verdict'))
