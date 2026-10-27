import importlib
import inspect
import pkgutil

from .base import Agent


def discover() -> list[Agent]:
    """Import every jarvis/agents/<name>/agent.py and instantiate each Agent subclass found."""
    found = []
    for pkg in pkgutil.iter_modules(__path__):
        if not pkg.ispkg or pkg.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"{__name__}.{pkg.name}.agent")
        except Exception as e:  # a broken/missing dependency shouldn't kill JARVIS
            print(f"[agents] skipped '{pkg.name}': failed to import ({e})")
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Agent) and cls is not Agent and cls.__module__ == module.__name__:
                try:
                    agent = cls()  # type: ignore[call-arg]  # subclasses build their own toolset
                    if agent.available():
                        found.append(agent)
                    else:
                        print(f"[agents] skipped '{agent.name}': not available (check credentials)")
                except Exception as e:
                    print(f"[agents] skipped '{cls.__name__}': {e}")
    return found
