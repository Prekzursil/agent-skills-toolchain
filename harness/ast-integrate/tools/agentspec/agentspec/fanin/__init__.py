"""Seven production fan-in consider() sites."""
from __future__ import annotations

from .local_runner import consider as local_runner_consider
from .cloud_dispatcher import consider as cloud_dispatcher_consider
from .monitor import consider as monitor_consider
from .harvester import consider as harvester_consider
from .workflow_fanin import consider as workflow_fanin_consider
from .cross_vendor_adapter import consider as cross_vendor_adapter_consider
from .final_synthesis import consider as final_synthesis_consider

CONSIDER_FNS = [
  local_runner_consider,
  cloud_dispatcher_consider,
  monitor_consider,
  harvester_consider,
  workflow_fanin_consider,
  cross_vendor_adapter_consider,
  final_synthesis_consider,
]
EXPECTED_ROLES = {
    "local-runner",
    "cloud-dispatcher",
    "monitor",
    "harvester",
    "workflow-fan-in",
    "cross-vendor-adapter",
    "final-synthesis",
}
__all__ = ['CONSIDER_FNS', 'EXPECTED_ROLES']
