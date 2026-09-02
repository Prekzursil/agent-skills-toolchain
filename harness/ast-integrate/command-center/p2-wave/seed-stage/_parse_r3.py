import json
import pathlib

files = {
    "GRA11": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-90df2641-fb0a-4db4-9516-499ff7116534-26.json",
    "WAW1": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-bb7bddf4-b8fe-41ef-8a1c-068998704c9c-28.json",
    "DE1": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-cd15a93f-35c5-43f7-839e-2b32076325e5-64.json",
    "GRA9": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-cd15a93f-35c5-43f7-839e-2b32076325e5-65.json",
    "RBX-A": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-cd15a93f-35c5-43f7-839e-2b32076325e5-66.json",
    "EU-WEST-PAR": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-cd15a93f-35c5-43f7-839e-2b32076325e5-67.json",
    "UK1": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-d377e961-b274-40fd-8e5a-8a944d949c88-74.json",
    "GRA7": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-1d025396-398a-4319-8f48-1e000beb548d-91.json",
    "SBG5": r"C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\mcp\call-1d025396-398a-4319-8f48-1e000beb548d-92.json",
}
for region, path in files.items():
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    items = d["items"]
    for name in ("r3-256", "r3-512", "r3-128"):
        hits = [f for f in items if f["name"] == name]
        if not hits:
            print(f"{region:12s} {name:8s} MISSING")
            continue
        f = hits[0]
        print(
            f"{region:12s} {name:8s} avail={f['available']} quota={f['quota']} "
            f"{f['vcpus']}c/{f['ram']}G id={f['id']} hourly={f['planCodes'].get('hourly')}"
        )
