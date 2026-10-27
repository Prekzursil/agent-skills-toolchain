from __future__ import annotations

import json
import unittest

from marketplace.disclosure import DisclosureRegistry, State
from marketplace.public_api import get_json, list_json

CANARY = "TEST-EMBARGO-CANARY-DO-NOT-LEAK"


class EmbargoLeakTests(unittest.TestCase):
    def test_withheld_until_disclose(self) -> None:
        reg = DisclosureRegistry()
        rec = reg.create("pkg.t", CANARY, actor="reporter")
        reg.transition(rec.id, State.TRIAGED, actor="triager")
        reg.transition(rec.id, State.EMBARGOED, actor="triager")
        self.assertNotIn(CANARY, get_json(reg, rec.id))
        self.assertNotIn(CANARY, list_json(reg))
        self.assertNotIn(CANARY, reg.log.dump_text())
        withheld = json.loads(get_json(reg, rec.id))
        self.assertEqual(set(withheld), {"id", "package_id", "disclosed"})
        reg.transition(rec.id, State.DISCLOSED, actor="owner", owner_approved=True)
        self.assertIn(CANARY, get_json(reg, rec.id))
        self.assertIn(CANARY, list_json(reg))


if __name__ == "__main__":
    unittest.main()
