@dataclass
class DeliberationSession:
    risk_class: str = ""
    allow_late_reclassification: bool = False
    events: list = field(default_factory=list)
    started: bool = False
    bound_config: dict = field(default_factory=dict)

    def start(self, config: dict | None = None) -> Result:
        cls = str(self.risk_class or "").upper()
        if not cls:
            self.events.append(EVENT_START_WITHOUT_CLASS)
            return Result(ok=False, accepted=False, blocked=True,
                          state="BLOCKED", verdict="FAIL",
                          reason="no risk class declared before start",
                          event=EVENT_START_WITHOUT_CLASS)
        map_risk_class(cls)
        self.started = True
        if config is None:
            return Result(bound_class=cls)
        res = at_floor(config, cls)
        if res.blocked:
            self.events.append("EVENT_CONFIG_BELOW_FLOOR")
            return res
        self.bound_config = dict(config)
        return Result(bound_class=cls)

    def reclassify(self, new_class: str) -> Result:
        new = str(new_class).upper()
        if not self.started:
            self.risk_class = new
            return Result(bound_class=new)
        if self.allow_late_reclassification:
            self.risk_class = new
            return Result(ok=False, accepted=True, blocked=False,
                          state="BLOCKED", verdict="FAIL",
                          reason="late reclassification permitted: immutability OFF",
                          bound_class=new)
        self.events.append(EVENT_RISK_CLASS_MUTATION_REFUSED)
        return Result(ok=False, accepted=False, blocked=True,
                      state="BLOCKED", verdict="FAIL",
                      reason="risk class immutable after start",
                      event=EVENT_RISK_CLASS_MUTATION_REFUSED,
                      bound_class=str(self.risk_class).upper())

    def bind_decision(self, config: dict) -> Result:
        cls = str(self.risk_class).upper()
        res = at_floor(config, cls)
        if res.blocked:
            return Result(ok=False, accepted=False, blocked=True,
                          state="BLOCKED", verdict="FAIL",
                          reason="decision on sub-floor config",
                          deficits=res.deficits, bound_class=cls)
        self.bound_config = dict(config)
        return Result(bound_class=cls)


def high_under_low_attack() -> dict:
    session = DeliberationSession(risk_class="LOW")
    session.start(dict(FLOORS["LOW"]))
    mut = session.reclassify("HIGH")
    landed = bool(mut.accepted and not mut.blocked)
    sub_floor = at_floor(dict(FLOORS["LOW"]), "HIGH")
    if sub_floor.accepted:
        landed = True
    return {
        "bound_class": str(session.risk_class),
        "event": mut.event or "",
        "high_under_low": landed,
        "immutability_holds": not landed,
    }


def immutability_holds(session: DeliberationSession) -> bool:
    if not session.started:
        return False
    before = session.risk_class
    other = "CRITICAL"
    if before == "CRITICAL":
        other = "LOW"
    res = session.reclassify(other)
    if res.blocked and session.risk_class == before:
        return True
    return False


def late_declaration_attack() -> dict:
    session = DeliberationSession(risk_class="")
    session.started = True
    res = session.reclassify("HIGH")
    return {
        "event": res.event or "",
        "refused": bool(res.blocked),
        "bound_class": str(session.risk_class),
    }


__all__ = [
    "DeliberationSession", "EVENT_MUTATION_REFUSED",
    "EVENT_RISK_CLASS_MUTATION_REFUSED", "EVENT_START_WITHOUT_CLASS",
    "EVIDENCE_TIERS", "FLOORS", "RISK_CLASSES", "RiskError", "Result",
    "at_floor", "evaluate_config", "floor_enforcement_matrix",
    "high_under_low_attack", "immutability_holds", "late_declaration_attack",
    "map_risk_class", "matrix_is_sound",
]
