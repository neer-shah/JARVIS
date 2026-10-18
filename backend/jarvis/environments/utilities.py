from datetime import datetime

from .base import Environment


class Utilities(Environment):
    """Smallest possible example environment."""

    name = "utilities"

    def tools(self):
        def get_current_time() -> str:
            """Get the current local date and time."""
            return datetime.now().strftime("%A %d %B %Y, %H:%M")

        return [get_current_time]
