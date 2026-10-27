def probe_verdict(rc: int, so: str, se: str) -> tuple[bool, str]:
    """Terminal-state signal for one live probe run.

    Accepts (a) a literal SUCCESS: marker (optionally after a JSON document,
    e.g. `json\\nSUCCESS:ID-probeN ...`), or (b) a pure structured-JSON
    verdict with pass==true and red empty (the TST probes' design). Fails on
    rc!=0, FAILED: markers, pass!=true, or non-empty red[].
    """
    if rc != 0:
        return False, f"rc={rc}"
    if "FAILED:" in so or "FAILED:" in se:
        return False, "FAILED-marker"
    marker = "SUCCESS:" in so
    tail = so.strip()
    if tail.startswith("{"):
        doc = None
        try:
            doc = json.loads(tail)
        except json.JSONDecodeError as e:
            if e.pos and tail[: e.pos].rstrip().endswith("}"):
                try:
                    doc = json.loads(tail[: e.pos])
                except Exception:
                    doc = None
        if isinstance(doc, dict):
            if doc.get("pass") is not True:
                return False, f"probe-pass={doc.get('pass')!r}"
            if doc.get("red") not in (None, []):
                return False, f"red={json.dumps(doc.get('red'))[:160]}"
            if marker:
                return True, "json-pass+SUCCESS-marker"
            return True, "json-pass (structured verdict; no SUCCESS: text marker by design)"
        if marker:
            return True, "SUCCESS-marker (json head unparseable)"
        return False, "no SUCCESS: marker and no structured json verdict"
    if marker:
        return True, "SUCCESS-marker"
    return False, "no SUCCESS: marker and no structured json verdict"
