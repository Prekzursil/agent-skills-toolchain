import json
import pathlib
import sys

PROBE = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\CNF-0110')
sys.path.insert(0, str(PROBE))
import schema_check as SC  # noqa: E402

art = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\confirmation\CNF-0110-signature-negative-control.json')
doc = json.loads(art.read_text(encoding='utf-8'))
errs = SC.error_messages(doc)
print('artifact errors n=', len(errs), errs[:3])
print('rejects_garbage:', SC.rejects_garbage())
v = SC.validator()
for i, g in enumerate(SC.GARBAGE):
    print(f'garbage[{i}] n_errors=', len(list(v.iter_errors(g))))
