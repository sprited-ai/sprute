import importlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "custom_nodes" / "sprute"


def node_module(name):
    """Import a module of the node package without its __init__, which needs ComfyUI."""
    if "sprute_nodes" not in sys.modules:
        package = importlib.util.module_from_spec(importlib.util.spec_from_loader("sprute_nodes", loader=None, is_package=True))
        package.__path__ = [str(NODES)]
        sys.modules["sprute_nodes"] = package
    return importlib.import_module(f"sprute_nodes.{name}")
