import json


def parse(text, fmt):
    if fmt != "json":
        raise ValueError("unsupported format: " + str(fmt))
    return json.loads(text)
