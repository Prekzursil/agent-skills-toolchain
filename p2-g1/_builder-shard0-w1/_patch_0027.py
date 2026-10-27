"""ADV-0027 platform adaptation: Python 3.14 tarfile data-filter hardening.

The naive-arm negative control (NC-NAIVE-TAR-EXTRACTALL) required stdlib
tarfile.extractall to write ../naive.beacon OUTSIDE the destination - true on
the python the unit was authored on, unrepresentable on python >= 3.14 where
the 'data' filter is the default and raises tarfile.OutsideDestinationError.
The exception previously propagated unhandled and killed the whole matrix.

Adaptation: catch the filter refusal, RECORD the hardened-stdlib world
explicitly (never silently), require the production import path to stay
fail-closed in that world, and let the probes accept either world with its
evidence recorded. Detector-vs-bad-state calibration in the other world is
unchanged.
"""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/matrix.py"
src = p.read_text(encoding="utf-8")

old = """        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with tarfile.open(fileobj=io.BytesIO(naive_blob), mode="r:") as tf:
                tf.extractall(naive_dest)
        naive_landed = (dest / "naive.beacon").is_file()"""
new = """        naive_filter_refused = False
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with tarfile.open(fileobj=io.BytesIO(naive_blob), mode="r:") as tf:
                try:
                    tf.extractall(naive_dest)
                except tarfile.FilterError:
                    # python >= 3.14: the 'data' filter is the DEFAULT and
                    # refuses ../ members. Record this world explicitly; the
                    # naive bad state is unrepresentable on this runtime.
                    naive_filter_refused = True
        naive_landed = (dest / "naive.beacon").is_file()"""
assert old in src, "naive arm anchor missing"
src = src.replace(old, new, 1)

old2 = """        passed = (
            benign_ok
            and all_refuted
            and nested_ok
            and nul_ok
            and naive_red
            and naive_import_closed
            and ratio > 10000.0
        )"""
new2 = """        passed = (
            benign_ok
            and all_refuted
            and nested_ok
            and nul_ok
            and (naive_red or (naive_filter_refused and naive_import_closed))
            and naive_import_closed
            and ratio > 10000.0
        )"""
assert old2 in src, "passed anchor missing"
src = src.replace(old2, new2, 1)

old3 = '''            "naive_tar_extractall_landed_outside": naive_red,'''
new3 = '''            "naive_tar_extractall_landed_outside": naive_red,
            "naive_tar_extractall_refused_by_stdlib_filter": naive_filter_refused,'''
assert old3 in src, "return fields anchor missing"
src = src.replace(old3, new3, 1)

old4 = '''                {
                    "id": "NC-NAIVE-TAR-EXTRACTALL",
                    "fired_on_bad_state": naive_red,
                    "silent_on_good_state": benign_ok,
                    "note": "stdlib tarfile.extractall writes ../ outside dest; import path does not.",
                }'''
new4 = '''                {
                    "id": "NC-NAIVE-TAR-EXTRACTALL",
                    "fired_on_bad_state": naive_red,
                    "silent_on_good_state": benign_ok,
                    "refused_by_stdlib_data_filter": naive_filter_refused,
                    "note": (
                        "stdlib tarfile.extractall writes ../ outside dest; import path "
                        "does not. On python >= 3.14 the default 'data' filter refuses "
                        "the ../ member outright - the naive bad state is unrepresentable "
                        "there and this control records that world instead of firing."
                    ),
                }'''
assert old4 in src, "NC row anchor missing"
src = src.replace(old4, new4, 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("matrix.py patched")

# ---- probe1: accept the hardened-stdlib world with its evidence recorded ----
p2 = Path(__file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/probe1_extract_matrix.py"
src2 = p2.read_text(encoding="utf-8")
old5 = '''    if not live["naive_tar_extractall_landed_outside"]:
        return fail("naive extractall did not land outside (detector inert)")'''
new5 = '''    if not live["naive_tar_extractall_landed_outside"] and not live.get(
        "naive_tar_extractall_refused_by_stdlib_filter"
    ):
        return fail("naive extractall did not land outside (detector inert)")
    if live.get("naive_tar_extractall_refused_by_stdlib_filter") and not live[
        "naive_import_fail_closed"
    ]:
        return fail("stdlib hardened but import path not fail-closed")'''
assert old5 in src2, "probe1 naive anchor missing"
src2 = src2.replace(old5, new5, 1)
old6 = 'f"benign_ok=True naive_red=True ratio={live[\'ratio_observed\']:.1f}:1 "'
new6 = (
    'f"benign_ok=True naive_red={live[\'naive_tar_extractall_landed_outside\']} '
    'stdlib_filter_refused={live.get(\'naive_tar_extractall_refused_by_stdlib_filter\')} '
    "ratio={live['ratio_observed']:.1f}:1 \""
)
assert old6 in src2, "probe1 success line anchor missing"
src2 = src2.replace(old6, new6, 1)
p2.write_text(src2, encoding="utf-8")
ast.parse(src2)
print("probe1_extract_matrix.py patched")
