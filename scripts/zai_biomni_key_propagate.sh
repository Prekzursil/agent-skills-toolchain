#!/usr/bin/env bash
# Propagate the ACTIVE (failover-maintained) ZAI key into Biomni's .env and the
# CS connector registration; restart the web app; kill stale sandbox children.
set -e
KEY="${ZAI_API_KEY:?ZAI_API_KEY not forwarded}"
ENVF=/home/prekzursil/Biomni/.env
cp "$ENVF" "$ENVF.bak-keyrotate-$(date +%Y%m%d-%H%M)"
python3 - "$ENVF" "$KEY" <<'PYEOF'
import hashlib, sys
path, key = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().splitlines()
out, replaced = [], False
for l in lines:
    if l.startswith("BIOMNI_CUSTOM_API_KEY="):
        out.append("BIOMNI_CUSTOM_API_KEY=" + key); replaced = True
    else:
        out.append(l)
if not replaced:
    out.append("BIOMNI_CUSTOM_API_KEY=" + key)
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("env key set, sha8:", hashlib.sha256(key.encode()).hexdigest()[:8])
PYEOF
# re-inject into CS local-mcp.json (reads .env)
/home/prekzursil/miniforge3/envs/biomni_e1/bin/python /mnt/c/Users/Prekzursil/_local_mcp_envfix.py
# stale children out (fresh spawn reads new key)
for p in $(pgrep -f "biomni_mcp_stdio"); do kill "$p" 2>/dev/null || true; done
# web app restart so ITS .env read is fresh too
bash -lc "bm-stop >/dev/null 2>&1; bm-start" >/dev/null 2>&1 || true
sleep 3
pgrep -af "biomni.*_web" | head -1 || echo "(web down - bm-start will be retried)"
echo "SUCCESS:biomni-key-rotate"
