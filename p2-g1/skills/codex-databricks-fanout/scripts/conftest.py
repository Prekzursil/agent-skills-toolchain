# Present so pytest adds this directory to sys.path -> `import harness` resolves
# under pytest. tests/__init__.py currently makes pytest do the same insertion, so
# deleting this file alone does not break the suite -- but deleting BOTH does:
# 3 collection errors, "ModuleNotFoundError: No module named 'harness'".
