from pathlib import Path
p = Path('_refresh_manifest_receipt.py')
t = p.read_text(encoding='utf-8')
# extract manifest block and move it before the predicate run block
man_start = t.index('# --- manifest refresh')
man_end = t.index('# --- receipt refresh')
man_block = t[man_start:man_end]
pred_start = t.index('P1 = sorted(pdir.glob')
pred_end = t.index("# --- manifest refresh")
pred_block = t[pred_start:pred_end]
t = t[:pred_start] + man_block + pred_block + t[man_end:]
p.write_text(t, encoding='utf-8', newline=chr(10))
print('reordered: manifest refresh now precedes predicate runs')
