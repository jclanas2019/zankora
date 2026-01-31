from gateway.tools.registry import builtins_registry
from gateway.plugins.registry import PluginRegistry
from gateway.plugins.loader import load_plugins

def test_plugin_loads_sample(tmp_path):
    # create a temp plugin
    pdir = tmp_path / "plugins"
    (pdir / "p1").mkdir(parents=True)
    (pdir / "p1" / "plugin.py").write_text(
        "from gateway.plugins.registry import PluginRegistry\n"
        "from gateway.domain.models import ToolSpec, ToolPermission\n"
        "def register(registry: PluginRegistry):\n"
        "  async def h(args): return {'ok':True}\n"
        "  registry.tools.register(ToolSpec(name='p1.t', permission=ToolPermission.read), h)\n"
    )
    reg = PluginRegistry(tools=builtins_registry())
    loaded = load_plugins(str(pdir), reg)
    assert loaded and reg.tools.get("p1.t") is not None
