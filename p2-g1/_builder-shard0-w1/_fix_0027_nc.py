"""ADV-0027: swap the unfireable naive NC for the nested-dotdot NC that fires
on python 3.14; keep the naive world recorded in matrix fields + residual."""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/matrix.py"
src = p.read_text(encoding="utf-8")

old = '''                {
                    "id": "NC-NAIVE-TAR-EXTRACTALL",
                    "kind": "known-broken-fixture",
                    "description": (
                        "stdlib tarfile.extractall writes ../ outside dest; import path "
                        "does not. On python >= 3.14 the default 'data' filter refuses "
                        "the ../ member outright - the naive bad state is unrepresentable "
                        "there and this control records that world instead of firing."
                    ),
                    "fired_on_bad_state": naive_red,
                    "silent_on_good_state": benign_ok,
                    "bad_state_output": json.dumps(
                        {"refused_by_stdlib_data_filter": naive_filter_refused}
                    ),
                }'''
new = '''                {
                    "id": "NC-NESTED-DOTDOT-BYPASS",
                    "kind": "adversarial-payload",
                    "description": (
                        "pkg/../../escape.beacon bypasses a naive "
                        "startswith('..') pre-normalisation check. The production "
                        "import path must reject it post-normpath while the benign "
                        "control still extracts. Fires on every python: the "
                        "crafted adversarial member is runtime-independent, unlike "
                        "the stdlib-naive extractall world (py < 3.12 only), which "
                        "is recorded in naive_tar_extractall_* fields and the "
                        "residual_unknowns entry instead."
                    ),
                    "fired_on_bad_state": nested_ok,
                    "silent_on_good_state": benign_ok,
                    "bad_state_output": json.dumps(
                        {
                            "bypass_member": "pkg/../../escape.beacon",
                            "import_ok": nested["ok"],
                            "escaped": nested["escaped"],
                            "written": nested["written"],
                            "rejected": nested["rejected"],
                        }
                    ),
                }'''
assert old in src, "NC row anchor missing"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("NC swapped to nested-dotdot bypass")
