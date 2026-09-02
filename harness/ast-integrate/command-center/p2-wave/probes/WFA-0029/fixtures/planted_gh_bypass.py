import subprocess

# Planted bypass: gh api without acquire.credentialed_call.
subprocess.run(["gh", "api", "repos/example/workflow"], check=False)
