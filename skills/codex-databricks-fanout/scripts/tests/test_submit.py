import json
from harness import submit


def test_payload_caps_concurrency_at_48():
    p = submit.build_payload(100, "/dbfs/x/batch.json", "/dbfs/x/results")
    env = p["tasks"][0]["new_cluster"]["spark_env_vars"]
    assert env["BATCH_CONCURRENCY"] == "48" and env["BATCH_STAGGER_S"] == "3.0"


def test_payload_singlenode_and_policy():
    p = submit.build_payload(3, "/dbfs/x/batch.json", "/dbfs/x/results")
    nc = p["tasks"][0]["new_cluster"]
    assert nc["policy_id"] == "0002189219BF8EF3" and nc["num_workers"] == 0
    assert nc["node_type_id"] == "r5d.2xlarge"
    bp = p["tasks"][0]["notebook_task"]["base_parameters"]
    assert (
        bp["batch_json"] == "/dbfs/x/batch.json"
        and bp["scope"] == "codex-harness-prekzursil"
    )


def test_extra_env_merges_github_token():
    p = submit.build_payload(
        1, "/d/b.json", "/d/r", extra_env={"GITHUB_TOKEN": "{{secrets/s/k}}"}
    )
    assert (
        p["tasks"][0]["new_cluster"]["spark_env_vars"]["GITHUB_TOKEN"]
        == "{{secrets/s/k}}"
    )


def test_smoke_payload_has_no_github_token():
    p = submit.build_payload(2, "/d/b.json", "/d/r")
    assert "GITHUB_TOKEN" not in p["tasks"][0]["new_cluster"]["spark_env_vars"]


def test_submit_parses_run_id_json():
    def run(argv):
        return 0, json.dumps({"run_id": 555}), ""

    assert submit.submit("payload.json", run) == 555


def test_submit_parses_run_id_text_fallback():
    def run(argv):
        return 0, "run_id: 777", ""

    assert submit.submit("payload.json", run) == 777


def test_submit_returns_none_on_failure():
    def run(argv):
        return 1, "", "boom"

    assert submit.submit("payload.json", run) is None
