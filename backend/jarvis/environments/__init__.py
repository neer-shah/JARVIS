import importlib
import inspect
import pkgutil

from .base import Environment


def discover() -> list[Environment]:
    """Import every module in this package and instantiate each Environment subclass found."""
    found = []
    for mod in pkgutil.iter_modules(__path__):
        if mod.name.startswith("_") or mod.name == "base":
            continue
        try:
            module = importlib.import_module(f"{__name__}.{mod.name}")
        except Exception as e:  # a broken/missing dependency shouldn't kill JARVIS
            print(f"[env] skipped '{mod.name}': failed to import ({e})")
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Environment) and cls is not Environment and cls.__module__ == module.__name__:
                try:
                    env = cls()
                    if env.available():
                        found.append(env)
                    else:
                        print(f"[env] skipped '{env.name}': not available (check credentials)")
                except Exception as e:
                    print(f"[env] skipped '{cls.__name__}': {e}")
    return found
