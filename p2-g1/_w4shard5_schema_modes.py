import json
import sys
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import jsonschema
from jsonschema import RefResolver

REPO = Path("C:/Users/Prekzursil/p2-g1")
uid = "BLD-0001"
wrapper = REPO / "command-center/schema/blindspot-register.schema.json"
sd = json.loads(wrapper.read_text(encoding="utf-8"))
doc = json.loads((REPO / "command-center/receipts/BLD-0001.json").read_text(encoding="utf-8"))

print("py:", sys.version.split()[0], "| jsonschema:", end=" ")
import importlib.metadata as md
print(md.version("jsonschema"))

resolver = RefResolver(base_uri=wrapper.resolve().as_uri(), referrer=sd)
v = jsonschema.Draft202012Validator(sd, resolver=resolver)
errs = list(v.iter_errors(doc))
print("errors:", len(errs))
for e in errs[:12]:
    print(" instance:", "/".join(str(x) for x in e.absolute_path) or "<root>")
    print("   schema_path:", "/".join(str(x) for x in e.schema_path)[:160])
    print("   msg:", str(e.message)[:160])
