import json
from pathlib import Path

from .base import Environment

STORE = Path(__file__).resolve().parents[2] / "calendar.json"


class Calendar(Environment):
    """Placeholder calendar backed by a local JSON file.

    Swap the bodies of these functions for Google Calendar API calls later; the
    names, signatures and docstrings are all the brain sees.
    """

    name = "calendar"

    def tools(self):
        def calendar_add_event(title: str, date: str, time: str = "") -> str:
            """Add an event to the user's calendar.

            Args:
                title: Event title.
                date: Date in YYYY-MM-DD format. Resolve relative dates like 'tomorrow'
                    first using get_current_time.
                time: Optional start time in 24h HH:MM format.
            """
            events = json.loads(STORE.read_text()) if STORE.exists() else []
            events.append({"title": title, "date": date, "time": time})
            STORE.write_text(json.dumps(events, indent=2))
            return f"Added '{title}' on {date} {time}".strip() + "."

        def calendar_list_events(date: str = "") -> str:
            """List calendar events, optionally only for one date.

            Args:
                date: Optional date in YYYY-MM-DD format. Empty means all events.
            """
            events = json.loads(STORE.read_text()) if STORE.exists() else []
            events = [e for e in events if not date or e["date"] == date]
            return json.dumps(events) if events else "No events."

        return [calendar_add_event, calendar_list_events]
