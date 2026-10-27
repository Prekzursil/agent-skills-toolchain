import json
from pathlib import Path
ART = Path('command-center/adversarial/ADV-0124-monitor-liveness-four-state-matrix.json')
doc = json.loads(ART.read_text(encoding='utf-8'))
mr = doc.get('manifest_registration') or {}
mr.pop('derivation', None)
doc['manifest_registration'] = mr
for nc in doc['negative_controls']:
    if 'description' not in nc:
        nc['description'] = (nc.get('id') or 'control') + ': single-signal ablation monitor must MISCLASSIFY the constructed states (fires on bad state) while the full monitor stays correct on the plainly-running good state.'
pb = doc.get('produced_by') or {}
if pb.get('vendor') == 'xai/cursor':
    pb['vendor'] = 'xai'
    pb['extensions_note'] = 'built under cursor on a gpt-5-codex assignment; model/vendor tokens normalized to registry ids'
ART.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
print('patched, bytes:', ART.stat().st_size)
