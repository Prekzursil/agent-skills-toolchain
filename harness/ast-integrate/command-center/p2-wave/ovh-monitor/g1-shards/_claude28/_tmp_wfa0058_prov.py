import hashlib
import json
import pathlib
import sys

PROBE = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\WFA-0058')
sys.path.insert(0, str(PROBE))
import corpus as C  # noqa: E402

data = C.load_corpus()
print('n_candidates:', data['n_candidates'], 'path:', data['path'])

art = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\wfa\WFA-0058-mechanism-vocabulary.json')
doc = json.loads(art.read_text(encoding='utf-8'))
for root in (doc, doc.get('extensions', {}).get('legacy_root', {})):
    ls = root.get('live_source') if isinstance(root, dict) else None
    if isinstance(ls, dict) and ls.get('live_present') is True:
        ls['n_candidates'] = data['n_candidates']
        ls['absent_reason'] = None
        ls['path'] = '~/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json'

out = json.dumps(doc, indent=1, ensure_ascii=False) + '\n'
art.write_text(out, encoding='utf-8', newline='\n')
b = art.read_bytes().replace(b'\r\n', b'\n')
print('sha256', hashlib.sha256(b).hexdigest(), 'bytes', len(b))
