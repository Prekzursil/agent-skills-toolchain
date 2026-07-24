"""Ephemeral policy-path jobs submit (singleNode). Payload from the proven submit_fanout.py."""

from __future__ import annotations
import json
from harness.contract import RAIL


def build_payload(n, batch_dbfs, result_dir, extra_env=None) -> dict:
    conc = min(RAIL["concurrency"], max(1, n))
    env = {
        "BATCH_CONCURRENCY": str(conc),
        "BATCH_STAGGER_S": RAIL["stagger_s"],
        "JFROG_USERNAME": "{{secrets/jfrog-artifactory-secrets/artifactory-username}}",
        "JFROG_PASSWORD": "{{secrets/jfrog-artifactory-secrets/artifactory-password}}",
    }
    if extra_env:
        env.update(extra_env)
    return {
        "run_name": f"codex-fanout-n{n}-c{conc}",
        "timeout_seconds": 6 * 3600,
        "tasks": [
            {
                "task_key": "fanout",
                "notebook_task": {
                    "notebook_path": RAIL["notebook"],
                    "source": "WORKSPACE",
                    "base_parameters": {
                        "batch_json": batch_dbfs,
                        "result_dir": result_dir,
                        "scope": RAIL["scope"],
                        "stagger_s": RAIL["stagger_s"],
                    },
                },
                "new_cluster": {
                    "policy_id": RAIL["policy_id"],
                    "spark_version": RAIL["spark_version"],
                    "node_type_id": RAIL["node_type_id"],
                    "driver_node_type_id": RAIL["node_type_id"],
                    "num_workers": 0,
                    "spark_conf": {
                        "spark.master": "local[*]",
                        "spark.databricks.cluster.profile": "singleNode",
                    },
                    "custom_tags": {
                        "ResourceClass": "SingleNode",
                        "CostCenter": "ENG-DATA-PLATFORM",
                        "project": "codex-databricks-fanout-harness",
                    },
                    "aws_attributes": {
                        "availability": "ON_DEMAND",
                        "zone_id": "auto",
                        "instance_profile_arn": RAIL["instance_profile"],
                    },
                    "spark_env_vars": env,
                    "data_security_mode": "LEGACY_SINGLE_USER_STANDARD",
                    "enable_elastic_disk": True,
                    "cluster_log_conf": {
                        "s3": {
                            "destination": RAIL["s3_log_dest"],
                            "region": RAIL["s3_region"],
                        },
                    },
                },
                "timeout_seconds": 5 * 3600,
            }
        ],
    }


def submit(payload_path, run_cmd) -> int | None:
    rc, out, _ = run_cmd(
        [
            "databricks",
            "jobs",
            "submit",
            "--json",
            f"@{payload_path}",
            "--no-wait",
            "--profile",
            RAIL["profile"],
        ]
    )
    if rc != 0:
        return None
    try:
        return json.loads(out).get("run_id")
    except json.JSONDecodeError:
        for line in (out or "").splitlines():
            if "run_id" in line.lower():
                digits = "".join(ch for ch in line if ch.isdigit())
                if digits:
                    return int(digits)
    return None
