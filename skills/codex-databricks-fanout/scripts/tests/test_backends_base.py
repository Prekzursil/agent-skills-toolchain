import dataclasses

from backends import base


def test_all_types_frozen_and_serializable():
    objs = [
        base.Job(backend="databricks", ref="r1", meta={"n": 2}),
        base.MatrixVerdict(
            repo="r",
            branch="b",
            head_sha="s",
            platforms={"ubuntu": True},
            all_green=True,
        ),
        base.Result(unit_id="u", ok=True, reason="ok", size=1200),
        base.MintedToken(token="ghs_x", repo="o/r", expires_at="2026-07-24T13:00:00Z"),
    ]
    for o in objs:
        assert dataclasses.is_dataclass(o) and o.__dataclass_params__.frozen
        assert type(o)(**dataclasses.asdict(o)) == o  # serializable round-trip (R8)


def test_protocols_are_role_split():
    assert set(dir(base.BuildBackend)) >= {
        "submit",
        "poll",
        "harvest",
        "cancel",
        "teardown",
    }
    assert "verify" in dir(base.VerifyBackend)
    assert "harvest" not in dir(
        base.VerifyBackend
    )  # R6: verify tier returns a verdict, not artifacts
