from abc import ABC, abstractmethod
from typing import Callable


class Environment(ABC):
    """A capability JARVIS can use (Spotify, calendar, smart home, ...).

    To add one: drop a new file in jarvis/environments/ with a subclass of this.
    It is discovered automatically; nothing else needs editing.
    """

    #: Short unique id, used for logging.
    name: str

    def available(self) -> bool:
        """Return False (e.g. missing credentials) to skip loading this environment."""
        return True

    @abstractmethod
    def tools(self) -> list[Callable]:
        """Plain Python functions Gemini may call.

        Gemini builds the tool schema from each function's name, type hints and docstring,
        so write a clear docstring (what it does, what each arg means) and use globally
        unique names, e.g. `spotify_play`, not `play`. Return a short string describing
        the outcome; it is passed back to the model.
        """
