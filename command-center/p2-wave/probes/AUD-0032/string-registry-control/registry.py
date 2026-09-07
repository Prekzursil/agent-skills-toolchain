PLUGIN_REGISTRY = {
    "planted": "command-center.p2-wave.probes.AUD-0032.string-registry-control.planted_registry_only_mod",
}

def load(name):
    import importlib
    return importlib.import_module(PLUGIN_REGISTRY[name])
