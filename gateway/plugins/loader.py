from __future__ import annotations
import importlib.util, os, sys, pathlib
from dataclasses import dataclass
from typing import Any
from gateway.plugins.registry import PluginRegistry
from gateway.observability.logging import get_logger

log = get_logger("plugins")

@dataclass
class LoadedPlugin:
    name: str
    path: str
    module_name: str

def load_plugins(plugin_dir: str, registry: PluginRegistry) -> list[LoadedPlugin]:
    loaded: list[LoadedPlugin] = []
    pdir = pathlib.Path(plugin_dir)
    if not pdir.exists():
        log.info("plugin_dir_missing", plugin_dir=str(pdir))
        return loaded

    for child in sorted(pdir.iterdir()):
        if not child.is_dir():
            continue
        plugin_py = child / "plugin.py"
        if not plugin_py.exists():
            continue
        name = child.name
        module_name = f"agw_plugin_{name}"
        spec = importlib.util.spec_from_file_location(module_name, str(plugin_py))
        if spec is None or spec.loader is None:
            log.warning("plugin_spec_failed", name=name)
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)  # type: ignore
            if not hasattr(mod, "register"):
                log.warning("plugin_no_register", name=name)
                continue
            mod.register(registry)
            loaded.append(LoadedPlugin(name=name, path=str(plugin_py), module_name=module_name))
            log.info("plugin_loaded", name=name)
        except Exception as e:
            log.exception("plugin_load_failed", name=name, err=str(e))
    return loaded
