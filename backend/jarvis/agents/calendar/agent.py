from ..base import Agent
from .tools import Calendar

PROMPT = """\
You are JARVIS's calendar agent for the user's iPhone (iCloud) calendar.

- Schedule questions: call calendar_list_events with concrete dates worked out from the current
  time, then summarise briefly in speech (no lists).
- Adding an event: call calendar_add_event. If the user gave no time for something that isn't
  all-day, ask for one instead of guessing. Only say it was added if the tool result says so.
- To pick a calendar by name, calendar_list_calendars shows what exists.
- You cannot delete or move events. Say so if asked.
"""


class CalendarAgent(Agent):
    name = "calendar"
    description = (
        "Calendar agent for the user's iPhone/iCloud calendar: answers questions about their schedule "
        "(what's on, when they're free) and adds events, including all-day, repeating and with alerts."
    )
    system_prompt = PROMPT

    def __init__(self) -> None:
        super().__init__(Calendar())
