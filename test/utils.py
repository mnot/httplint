import importlib
import pkgutil


def checkSubClasses(cls, module_paths, check):
    """
    Run a check(subclass) function on all subclasses of cls.

    Returns how many subclasses were checked.
    """
    for module_path in module_paths:
        loadModules(module_path, f"{module_path.replace('/', '.')}.")
    count = 0
    errors = 0
    for subcls in cls.__subclasses__():
        errors += check(subcls)
        count += 1
    return count, errors


def loadModules(path, prefix):
    [
        importlib.import_module(name)
        for finder, name, ispkg in pkgutil.iter_modules([path], prefix=prefix)
    ]
