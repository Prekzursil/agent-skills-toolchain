import json, hashlib, io, sys

def load_json(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def sha256_lf(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        data = f.read()
    data = data.replace(b'\r\n', b'\n')
    h.update(data)
    return h.hexdigest()
