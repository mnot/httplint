import importlib
import pkgutil

__path__ = pkgutil.extend_path(__path__, __name__)
for imp, module, ispackage in pkgutil.walk_packages(
    path=__path__, prefix=f"{__name__}."
):
    importlib.import_module(module)
