import dataclasses
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "p2-g1" / "tools"))
from council.antifail.unanimity import Vote, plurality
print("Vote", Vote)
print("dataclass", hasattr(Vote, "__dataclass_fields__"))
print("fields", [f.name for f in dataclasses.fields(Vote)])
