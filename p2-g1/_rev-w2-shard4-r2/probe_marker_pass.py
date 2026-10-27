import json, os, glob
D='_rev-w2-shard4-r2/probe_rerun'
out={}
for log in sorted(glob.glob(D+'/*.log')):
    name=os.path.basename(log)[:-4]
    lines=[l.rstrip() for l in open(log,encoding='utf-8',errors='replace') if l.strip()]
    if not lines: out[name]={'rc_log':'EMPTY','terminal':'NONE'}; continue
    terminal=lines[-1]
    out[name]={'terminal':terminal[:120],
               'terminal_success':terminal.startswith('SUCCESS:'),
               'any_failed_terminal':any(l.startswith('FAILED:') for l in lines[-3:])}
json.dump(out,open(D+'/marker_check.json','w'),indent=1)
bad=[k for k,v in out.items() if not v.get('terminal_success')]
print('logs:',len(out),'| non-SUCCESS-terminal:',bad if bad else 'none')
for k,v in list(out.items())[:4]: print(k,'->',v['terminal'][:100])
