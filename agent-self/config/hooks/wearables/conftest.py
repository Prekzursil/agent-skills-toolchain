"""Make ``wearables`` importable as a top-level package during tests.

pytest is invoked from inside the ``wearables/`` directory (so the pyproject
gate applies), but ``from wearables.x import y`` needs the PARENT directory
(``hooks/``) on ``sys.path``. Add it here.
"""

import sys
from pathlib import Path

_PARENT = Path(__file__).resolve().parent.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))
