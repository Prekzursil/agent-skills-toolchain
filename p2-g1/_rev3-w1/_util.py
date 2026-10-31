import json, hashlib, io, os, sys

REPO = r'C:/Users/Prekzursil/p2-g1'
UNITS = ["BLD-0001","BLD-0002","BLD-0006","BLD-0010","BLD-0023","BLD-0024",
         "BLD-0031","BLD-0037","BLD-0041","BLD-0044","BLD-0045","BLD-0051"]

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

def repo(*parts):
    return os.path.join(REPO, *parts)
