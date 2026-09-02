import json

H = r"C:/Users/Prekzursil/source/ast-integrate/command-center/harvest/harvest-wf_18aa91e4-3c1-wf_9cb1a66a-36f.json"
with open(H, "r", encoding="utf-8") as f:
    d = json.load(f)

print("TOP TYPE:", type(d).__name__)
if isinstance(d, dict):
    for k, v in d.items():
        print(
            f"  KEY {k!r} -> {type(v).__name__} len={len(v) if hasattr(v, '__len__') else 'NA'}"
        )
        if isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    keys = list(item.keys())
                    rl = item.get("result")
                    rlen = (
                        len(rl)
                        if isinstance(rl, str)
                        else (len(json.dumps(rl)) if rl is not None else 0)
                    )
                    print(
                        f"    [{i}] keys={keys} agentId={item.get('agentId')!r} label={item.get('label')!r} phase={item.get('phase')!r} result_len={rlen}"
                    )
                else:
                    print(f"    [{i}] {type(item).__name__}")
