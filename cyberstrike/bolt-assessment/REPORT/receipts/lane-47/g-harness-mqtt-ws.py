#!/usr/bin/env python3
"""Lane-47 re-test set (subtask 107) — Bolt Technology OU authorized red-team continuation.
Operator directive 2026-10-03: "proceed with the rest of the lines, full attack, authorized".
Standing riders: NEVER-ROTATE, no OOB, no subscription, single-attempt per endpoint/shape.
Budget: <=25 counted HTTP/WS calls; gateway sentinel (2) logged separately.
Methodology replicated verbatim from /work/lane35/p_c.py (item a) and lane-35 curl receipts.
"""
import base64, hashlib, json, os, secrets, socket, ssl, struct, subprocess, sys, time

WORK = "/work/lane47"
REC  = "/work/bolt/REPORT/receipts/lane-47"
BUDGET_FILE = os.path.join(WORK, "budget.jsonl")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

os.makedirs(REC, exist_ok=True)

def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".%03dZ" % (int(time.time() * 1000) % 1000)

def sha8(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()[:8]

def budget_log(entry):
    with open(BUDGET_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

CALL_COUNT = 0
def pace():
    global CALL_COUNT
    CALL_COUNT += 1
    budget_log({"n": CALL_COUNT, "ts": now_iso(), **{k: v for k, v in [("label", _LBL[0])] if _LBL[0]}} if False else {"n": CALL_COUNT, "ts": now_iso()})
    time.sleep(1.2)

_LBL = [None]
def set_label(lbl):
    _LBL[0] = lbl

# ---------------------------------------------------------------- item (a)
def mqtt_connect_pkt(client_id):
    vh = b"\x00\x04MQTT\x04\x02\x00\x3c"          # name, v3.1.1, clean-session, ka=60
    cid = client_id.encode()
    payload = struct.pack(">H", len(cid)) + cid
    body = vh + payload
    rem = len(body); remenc = b""
    while True:
        d = rem % 128; rem //= 128
        if rem: remenc += bytes([d | 0x80])
        else:   remenc += bytes([d]); break
    return b"\x10" + remenc + body

def ws_frame(opcode, payload, mask=True):
    b = bytes([0x80 | opcode]); n = len(payload)
    if n < 126:   b += bytes([(0x80 if mask else 0) | n]); ext = b""
    elif n < 65536:
        b += bytes([(0x80 if mask else 0) | 126]); ext = struct.pack(">H", n)
    else:
        b += bytes([(0x80 if mask else 0) | 127]); ext = struct.pack(">Q", n)
    b += ext
    if mask:
        mk = os.urandom(4)
        masked = bytes(c ^ mk[i % 4] for i, c in enumerate(payload))
        b += mk + masked
    else:
        b += payload
    return b

def ws_read(sock, timeout=6.0, maxbytes=4096):
    sock.settimeout(timeout); buf = b""
    try:
        while len(buf) < maxbytes:
            chunk = sock.recv(4096)
            if not chunk:
                return buf, "TCP-CLOSED"
            buf += chunk
            if buf.startswith(b"HTTP") and b"\r\n\r\n" in buf:
                return buf, "HTTP-RESPONSE"
    except socket.timeout:
        return buf, "TIMEOUT-SILENCE"
    except Exception as e:
        return buf, f"ERR {type(e).__name__}: {e}"
    return buf, "OK"

def mqtt_ws_probe(host, client_id, path="/mqtt"):
    out = {"ts": now_iso(), "host": host, "path": path, "client_id": client_id}
    t0 = time.monotonic()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        raw = socket.create_connection((host, 443), timeout=10)
        ss = ctx.wrap_socket(raw, server_hostname=host)
        out["tls"] = ss.version(); out["cipher"] = ss.cipher()[0]
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
               f"Sec-WebSocket-Protocol: mqtt\r\nOrigin: https://bolt.eu\r\nUser-Agent: {UA}\r\n\r\n")
        ss.sendall(req.encode())
        buf, state = ws_read(ss, timeout=6.0)
        hdr = buf.split(b"\r\n\r\n")[0].decode("utf-8", "replace")
        out["upgrade_status_line"] = hdr.splitlines()[0] if hdr else "(empty)"
        out["upgrade_state"] = state
        if b" 101 " not in buf.split(b"\r\n")[0]:
            out["verdict"] = f"WS-UPGRADE-REFUSED ({state})"; out["raw_head"] = hdr[:300]
            ss.close(); out["elapsed_ms"] = int((time.monotonic() - t0) * 1000); return out
        # send exactly ONE MQTT CONNECT — fresh synthetic client-id, no SUBSCRIBE
        ss.sendall(ws_frame(0x2, mqtt_connect_pkt(client_id)))
        buf2, state2 = ws_read(ss, timeout=7.0)   # same 7 s read window as lane-35
        out["post_connect_state"] = state2
        out["post_connect_bytes"] = len(buf2)
        if buf2:
            out["post_connect_sha8"] = sha8(buf2)
            if len(buf2) >= 2 and (buf2[0] & 0x0F) == 0x8:
                code = struct.unpack(">H", buf2[2:4])[0] if len(buf2) >= 4 else None
                out["ws_close_code"] = code
                out["verdict"] = f"WS-CLOSED code={code} after CONNECT ({state2})"
            elif len(buf2) >= 2 and (buf2[0] & 0x0F) == 0x2:
                pl = buf2[2:]
                if len(pl) >= 4 and pl[0] == 0x20:
                    rc = pl[4] if len(pl) > 4 else None
                    out["CONNACK_return_code"] = rc
                    out["verdict"] = f"CONNACK rc={rc} ({'ACCEPTED' if rc == 0 else 'REJECTED'})"
                else:
                    out["verdict"] = f"WS-frame non-CONNACK ({state2})"
            else:
                out["verdict"] = f"non-binary/no CONNACK ({state2})"
        else:
            out["verdict"] = f"FAIL-SILENT: no bytes after CONNECT ({state2})"
        try: ss.close()
        except Exception: pass
    except Exception as e:
        out["verdict"] = f"ERROR {type(e).__name__}: {e}"
    out["elapsed_ms"] = int((time.monotonic() - t0) * 1000)
    return out

# ---------------------------------------------------------------- curl helper
def http_probe(url, method="GET", data=None, ctype=None, resolve=None, extra=None, max_time=10):
    """One curl call. Returns dict with status/time/headers/body-sha8/body-head."""
    hdrf = os.path.join(WORK, "h.txt"); bodyf = os.path.join(WORK, "b.txt")
    cmd = ["curl", "-sS", "--max-time", str(max_time), "-o", bodyf, "-D", hdrf,
           "-w", "%{http_code} %{time_total} %{http_version} %{remote_ip}", "-X", method,
           "-A", UA, url]
    if data is not None:
        cmd += ["--data-binary", "@" + data] if isinstance(data, str) and data.startswith("@") \
               else ["--data-binary", data]
    if ctype:
        cmd += ["-H", f"Content-Type: {ctype}"]
    if resolve:
        cmd += ["--resolve", resolve]
    if extra:
        for h in extra:
            cmd += ["-H", h]
    set_label(url)
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=max_time + 5)
        wout = r.stdout.strip()
    except subprocess.TimeoutExpired:
        return {"ts": now_iso(), "url": url, "method": method, "error": "CURL-TIMEOUT"}
    parts = wout.rsplit(" ", 3)
    res = {"ts": now_iso(), "method": method, "url": url, "curl_ok": r.returncode == 0}
    if len(parts) == 4:
        res["status"], res["time_s"], res["http_ver"], res["remote_ip"] = parts
    else:
        res["curl_w"] = wout
    try:
        raw = open(hdrf, "rb").read()
        res["headers_raw"] = raw.decode("utf-8", "replace")
        body = open(bodyf, "rb").read()
    except FileNotFoundError:
        body = b""
    res["body_len"] = len(body); res["body_sha8"] = sha8(body)
    res["body_head"] = body[:200].decode("utf-8", "replace").replace("\n", "\\n")
    res["curl_stderr"] = r.stderr.strip()[:200]
    res["wall_ms"] = int((time.monotonic() - t0) * 1000)
    pace()
    return res

def fmt_http(res):
    lines = [f"[{res.get('ts')}] {res.get('method')} {res.get('url')}"]
    if "status" in res:
        lines.append(f"  -> {res['status']} HTTP/{res.get('http_ver')} in {res.get('time_s')}s "
                     f"remote={res.get('remote_ip')} body={res['body_len']}B sha8={res['body_sha8']}")
        for h in res.get("headers_raw", "").splitlines():
            hl = h.lower()
            if any(k in hl for k in ("content-type:", "content-length:", "server:", "www-authenticate:",
                                     "allow:", "x-envoy", "etag:", "last-modified:", "cf-ray:",
                                     "cf-cache-status:", "strict-transport", "content-security-policy",
                                     "x-amz", "x-robots")):
                lines.append("     " + h.strip()[:300])
        lines.append(f"     body[:200]: {res.get('body_head','')}")
    else:
        lines.append(f"  -> ERROR {res.get('error') or res.get('curl_stderr') or res.get('curl_w')}")
    return "\n".join(lines)

# ---------------------------------------------------------------- phases
def phase_sentinel():
    out = ["# LANE-47 PRE-STEP gateway health sentinel (CONVENTIONS.md) — 2 calls, NOT counted in 25-call budget",
           f"# generated {now_iso()}"]
    for path, expect in [("/", "404"), ("/mcp", "406")]:
        r = http_probe("http://172.17.0.1:31100" + path, max_time=5)
        out.append(f"[{r.get('ts')}] GET http://172.17.0.1:31100{path}  expected={expect}")
        out.append(f"  -> status={r.get('status','ERR')} body_len={r.get('body_len')} body_sha8={r.get('body_sha8')} curl_stderr={r.get('curl_stderr','')}")
        out.append(f"  VERDICT: {'OK' if r.get('status') == expect else 'DEVIATION'}")
    # undo the 2 sentinel entries from the counted budget log
    with open(BUDGET_FILE) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    with open(BUDGET_FILE, "w") as f:
        for e in entries[:-2]:
            f.write(json.dumps(e) + "\n")
    txt = "\n".join(out) + "\n"
    open(os.path.join(REC, "00-sentinel.txt"), "w").write(txt)
    print(txt)

def phase_mqtt():
    hx = secrets.token_hex(3)
    out = [f"# LANE-47 ITEM (a) MQTT-over-WS CONNECT gate re-test — one CONNECT per broker, fresh synthetic client-ids, no SUBSCRIBE",
           f"# baseline lane-35 (2026-10-01): WS 101 -> CONNECT -> 0 bytes ~7.17s TIMEOUT-SILENCE (fail-silent) both brokers",
           f"# generated {now_iso()}"]
    for host, cid in [("rider-broker.ws.bolt.eu", f"l47probe-{hx}-rider"),
                      ("driver-broker.ws.bolt.eu", f"l47probe-{hx}-driver")]:
        res = mqtt_ws_probe(host, cid)
        pace()
        out.append(json.dumps(res, indent=2, sort_keys=False))
    txt = "\n".join(out) + "\n"
    open(os.path.join(REC, "a-mqtt-ws-gate.txt"), "w").write(txt)
    print(txt)

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "sentinel":  phase_sentinel()
    elif mode == "mqtt":    phase_mqtt()
    else: print("usage: l47.py sentinel|mqtt  (http phases via l47http.py)")
