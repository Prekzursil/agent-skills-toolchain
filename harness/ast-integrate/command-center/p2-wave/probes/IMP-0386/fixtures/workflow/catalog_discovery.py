#!/usr/bin/env python3
"""catalog-discovery workflow module header.

name: catalog-discovery
description: Discover catalog-class workflows without executing them.
version: 0.4.0
id: wf.catalog-class.discovery-only
stages: discover,record
stopping: halt-on-error
planted_extra_workflow: PLANTED-WORKFLOW-0386
"""


def main() -> None:
    raise SystemExit("discovery-only")


if __name__ == "__main__":
    main()
