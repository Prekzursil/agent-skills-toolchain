# Network forensics — tshark / Zeek / Suricata (pcap FILE mode, 0 daemon)

Analyze captured traffic that you are authorized to hold. Every command reads a
saved `.pcap`/`.pcapng` with a file flag (`-r`). **No live capture, no span-port
sensor, no IDS daemon** — capture is a separate, authorized acquisition step.

## tshark (Wireshark CLI, GPL-2.0 — wrap, do not vendor)

Fast slicing, field extraction, and protocol stats over a pcap.

```
# Protocol/endpoint/DNS overviews:
tshark -r cap.pcapng -q -z io,phs
tshark -r cap.pcapng -q -z conv,tcp
tshark -r cap.pcapng -Y 'dns' -T fields -e frame.time -e dns.qry.name

# HTTP requests + TLS SNI (beacon/exfil hunting):
tshark -r cap.pcapng -Y 'http.request' -T fields -e ip.dst -e http.host -e http.request.uri
tshark -r cap.pcapng -Y 'tls.handshake.extensions_server_name' -T fields -e tls.handshake.extensions_server_name

# Carve transferred objects (read-only export):
tshark -r cap.pcapng --export-objects http,./out/http_objs
```

## Zeek (BSD — wrap, do not vendor), file mode

Turn a pcap into rich protocol logs (`conn`, `dns`, `http`, `ssl`, `files`, `x509`).

```
zeek -r cap.pcapng LogAscii::use_json=T      # writes *.log in CWD
# Then grep/JQ the logs, e.g. long-lived or repeated connections (beacon signal):
cat conn.log | zeek-cut id.orig_h id.resp_h duration | sort -k3 -n | tail
```

## Suricata (GPL-2.0 — wrap, do not vendor), offline pcap scan

Run rules over a pcap once and read `eve.json` — not the live IDS service.

```
suricata -r cap.pcapng -S ./rules/suricata.rules -l ./out/    # writes eve.json
jq -c 'select(.event_type=="alert") | {ts,alert:.alert.signature,src:.src_ip,dst:.dest_ip}' ./out/eve.json
```

## Notes / stop rules

- **`-r` file mode only.** No `-i <iface>` capture, no `af-packet`/nfqueue daemon,
  no persistent sensor. Acquire captures under separate authorization.
- Extracted files/objects are **evidence copies** — hash them into the manifest and
  hand any executables to `capa-triage` (never run them).
- Suricata rule authoring/validation lives in `detection-as-code`; here you only run
  rules to triage a capture. Record the ruleset version with the output.
