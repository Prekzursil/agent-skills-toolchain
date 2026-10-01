#!/usr/bin/env python3
"""verify.py - health + one-token completion against the deployed Modal bench endpoint."""
import json
import os
import sys
import urllib.request

cfg = json.load(open(os.path.join(os.path.dirname(__file__), "providers-modal-qwen3-4b.json")))
base = cfg["base_url"]
if base.startswith("DEPLOY_AND_FILL"):
    sys.exit("provider URL not filled yet - deploy first (see README)")
tid = os.environ.get("MODAL_TOKEN_ID_474a0e") or os.environ.get("MODAL_TOKEN_ID")
sec = os.environ.get("MODAL_TOKEN_SECRET_3d3c42") or os.environ.get("MODAL_TOKEN_SECRET")
req = urllib.request.Request(
    base.rstrip("/") + cfg["endpoint"],
    data=json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 4}).encode(),
    headers={"Authorization": "Modal-Key {}, {}".format(tid, sec), "Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=120) as r:
    print("HTTP", r.status, json.loads(r.read())["choices"][0]["message"]["content"][:40])
print("VERIFY OK")
