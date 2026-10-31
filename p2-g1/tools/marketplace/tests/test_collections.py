"""IMP-0104: collection single-lock and all-or-nothing install (stdlib runner)."""
import shutil
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tools"))
from marketplace.collections import (  # noqa: E402
    CollectionDefinitionError,
    build_demo_index,
    define_collection,
    dumps_lockfile,
    install_collection,
    re_toolchain_collection,
    resolve_lockfile,
)


def test_one_lockfile_member_set_and_order_independence():
    index = build_demo_index()
    c = re_toolchain_collection(index)
    lock = resolve_lockfile(c, index)
    assert set(lock["members"]) == {"binwalk", "ghidra", "radare2"}
    c2 = re_toolchain_collection(index)
    c2.members = ("radare2", "ghidra", "binwalk")
    assert dumps_lockfile(resolve_lockfile(c2, index)) == dumps_lockfile(lock)


def test_rollback_leaves_zero_files_and_no_lock():
    index = build_demo_index()
    target = Path(tempfile.mkdtemp(prefix="testcoll-"))
    try:
        c = re_toolchain_collection(index)
        install_collection(c, index, target)
        assert len(list(target.glob("*.pkg"))) == 3
        try:
            install_collection(c, index, target, crash_after_first_write=True)
        except Exception:
            pass
        assert len(list(target.glob("*.pkg"))) == 0
        assert len(list(target.glob("collection-lock.json"))) == 0
    finally:
        shutil.rmtree(target, ignore_errors=True)


def test_incompatible_pair_fails_at_definition():
    index = build_demo_index()
    try:
        define_collection(index, ["capstone", "keystone"])
    except CollectionDefinitionError:
        return
    raise AssertionError("incompatible pair accepted at definition time")


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS:" + name)
            except Exception as exc:
                failed += 1
                print("FAIL:" + name + " " + str(exc))
    print("SUCCESS:test_collections" if not failed else "FAILED:test_collections")
    sys.exit(1 if failed else 0)
