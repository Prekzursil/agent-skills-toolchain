"""The lane registry fails closed per lane and never takes the hub down."""

from __future__ import annotations

import sys
import types

import lanes


def _install_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


def _uninstall(*names: str) -> None:
    for name in names:
        sys.modules.pop(name, None)


def test_registry_lists_only_lanes_that_import_and_build_cleanly():
    built, degraded = lanes.extra_adapters({})
    assert degraded == {}, degraded
    platforms = {ad.platform for ad in built}
    # Every registered lane is default-ON and keyless, so an empty environment
    # wires all of them; a lane that is opt-in must not appear here.
    assert platforms == {"repohealth", "grounding"}


def test_every_registered_lane_can_be_killed_to_nothing():
    kill = {
        "ENABLE_REPO_HEALTH": "0",
        "ENABLE_WIKIPEDIA": "0",
        "ENABLE_WAYBACK": "0",
        "ENABLE_HN": "0",
    }
    built, degraded = lanes.extra_adapters(kill)
    assert built == [] and degraded == {}


def test_build_lane_returns_the_module_list():
    _install_module("lane_fake_ok", build=lambda environ: [environ["marker"]])
    try:
        assert lanes.build_lane("lane_fake_ok", {"marker": "A"}) == ["A"]
        built, degraded = lanes.extra_adapters(
            {"marker": "A"}, modules=("lane_fake_ok",)
        )
        assert built == ["A"] and degraded == {}
    finally:
        _uninstall("lane_fake_ok")


def test_missing_module_is_reported_not_raised():
    built, degraded = lanes.extra_adapters({}, modules=("lane_does_not_exist",))
    assert built == []
    assert list(degraded) == ["lane:lane_does_not_exist"]
    assert degraded["lane:lane_does_not_exist"].startswith("ModuleNotFoundError")


def test_module_without_build_is_reported():
    _install_module("lane_fake_nobuild")
    try:
        built, degraded = lanes.extra_adapters({}, modules=("lane_fake_nobuild",))
        assert built == []
        assert degraded["lane:lane_fake_nobuild"].startswith("TypeError")
    finally:
        _uninstall("lane_fake_nobuild")


def test_builder_exception_drops_only_that_lane():
    def boom(environ):
        raise RuntimeError("upstream config missing")

    _install_module("lane_fake_boom", build=boom)
    _install_module("lane_fake_ok", build=lambda environ: ["ok"])
    try:
        built, degraded = lanes.extra_adapters(
            {}, modules=("lane_fake_boom", "lane_fake_ok")
        )
        assert built == ["ok"]
        assert degraded == {
            "lane:lane_fake_boom": "RuntimeError: upstream config missing"
        }
    finally:
        _uninstall("lane_fake_boom", "lane_fake_ok")


def test_non_list_build_result_is_a_type_error():
    _install_module("lane_fake_tuple", build=lambda environ: ("not", "a", "list"))
    try:
        built, degraded = lanes.extra_adapters({}, modules=("lane_fake_tuple",))
        assert built == []
        assert degraded["lane:lane_fake_tuple"].startswith("TypeError")
    finally:
        _uninstall("lane_fake_tuple")


def test_empty_build_means_flag_off_not_degraded():
    _install_module("lane_fake_off", build=lambda environ: [])
    try:
        built, degraded = lanes.extra_adapters({}, modules=("lane_fake_off",))
        assert built == [] and degraded == {}
    finally:
        _uninstall("lane_fake_off")
