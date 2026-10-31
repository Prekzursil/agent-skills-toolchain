@dataclass
class Result:
    ok: bool = True
    accepted: bool = True
    blocked: bool = False
    refusals: list = field(default_factory=list)
    deficits: list = field(default_factory=list)
    state: str = "SUCCESS"
    verdict: str = "PASS"
    reason: str = ""
    event: str = ""
    bound_class: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "accepted": self.accepted, "blocked": self.blocked,
            "deficits": list(self.deficits), "event": self.event,
            "bound_class": self.bound_class,
        }


def map_risk_class(cls: str) -> dict:
    cls = str(cls).upper()
    if cls not in FLOORS:
        raise RiskError(f"unknown risk class: {cls}")
    return dict(FLOORS[cls])


def _deficits(config: dict, floor: dict) -> list[str]:
    out = []
    for key, need in floor.items():
        have = config.get(key)
        if key == "evidence_standard":
            if EVIDENCE_TIER_RANK.get(str(have), -1) < EVIDENCE_TIER_RANK[str(need)]:
                out.append(key)
        else:
            if not isinstance(have, (int, float)) or have < need:
                out.append(key)
    return out


def at_floor(config: dict, cls: str) -> Result:
    floor = map_risk_class(cls)
    deficits = _deficits(config or {}, floor)
    return Result(ok=not deficits, accepted=not deficits, blocked=bool(deficits),
                  deficits=deficits, bound_class=str(cls).upper())


def evaluate_config(config: dict, cls: str) -> Result:
    return at_floor(config, cls)
