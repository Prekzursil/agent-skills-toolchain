import json
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
doc = json.loads(p.read_text(encoding='utf-8'))
key = sys.argv[2] if len(sys.argv) > 2 else 'headline'
print(json.dumps(doc.get(key), indent=1)[:1200])
t = p.read_text(encoding='utf-8')
i = t.find('"%s"' % key)
print('raw:', repr(t[i:i + 500]))
