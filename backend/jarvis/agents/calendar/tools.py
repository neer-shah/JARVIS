import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import tzlocal
from dateutil import tz

from ...environments.base import Environment

URL = "https://caldav.icloud.com/"
LOCAL_TZ = tzlocal.get_localzone()  # a real IANA zone (e.g. Europe/London), so iCloud reads it and DST is handled
REPEATS = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY", "yearly": "YEARLY"}


def _parse(value: str, field: str) -> datetime:
    """'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM' -> naive datetime."""
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        raise RuntimeError(f"{field} must look like 2026-10-19 or 2026-10-19T14:30, not '{value}'.") from None


def _as_local(d) -> datetime:
    """An event's DTSTART/DTEND (date, naive or aware datetime) -> aware local datetime."""
    if not isinstance(d, datetime):  # all-day: a plain date
        return datetime.combine(d, datetime.min.time(), tzinfo=LOCAL_TZ)
    return d.replace(tzinfo=LOCAL_TZ) if d.tzinfo is None else d.astimezone(LOCAL_TZ)


def _describe(summary, start, end, all_day, location, calendar_name) -> str:
    day = f"{start:%A %d %B}"
    if all_day:
        last = end - timedelta(days=1)  # all-day DTEND is exclusive
        when = day + (f" to {last:%A %d %B}" if last.date() > start.date() else "") + ", all day"
    else:
        when = (
            f"{day}, {start:%H:%M} to {end:%H:%M}"
            if end.date() == start.date()
            else f"{day} {start:%H:%M} to {end:%A %d %B %H:%M}"
        )
    extra = (f" at {location}" if location else "") + (f" [{calendar_name}]" if calendar_name else "")
    return f"{summary}: {when}{extra}"


class Calendar(Environment):
    """Your iCloud calendars over CalDAV. Needs APPLE_ACCOUNT_EMAIL and APPLE_CALENDAR_PASSWORD in .env
    (an app-specific password from appleid.apple.com, not your real Apple password)."""

    name = "calendar"

    def __init__(self):
        self._principal = None
        self._calendars = None  # cached: discovering them costs several round trips to iCloud
        self._lock = threading.Lock()

    def available(self):
        return bool(os.getenv("APPLE_ACCOUNT_EMAIL") and os.getenv("APPLE_CALENDAR_PASSWORD"))

    def _event_calendars(self):
        """Calendars that hold events (iCloud also lists Reminders lists, which hold tasks). Cached."""
        with self._lock:
            if self._calendars is None:
                import caldav

                client = caldav.DAVClient(
                    URL, username=os.getenv("APPLE_ACCOUNT_EMAIL"), password=os.getenv("APPLE_CALENDAR_PASSWORD")
                )
                self._principal = client.principal()

                def holds_events(cal):
                    try:
                        return "VEVENT" in cal.get_supported_components()
                    except Exception:
                        return True

                cals = self._principal.calendars()
                with ThreadPoolExecutor(max_workers=8) as pool:
                    self._calendars = [c for c, ok in zip(cals, pool.map(holds_events, cals)) if ok]
            return self._calendars

    def _warm(self):
        try:
            self._event_calendars()
        except Exception as e:
            print(f"[calendar] warm-up failed: {e!r}")

    def tools(self):
        threading.Thread(target=self._warm, daemon=True).start()  # log in while JARVIS starts, not on first question

        def calendar_list_events(start_date: str, end_date: str = "") -> str:
            """List the user's calendar events in a date range, e.g. 'what's on my calendar this week?',
            'am I free tomorrow afternoon?', 'what do I have on Friday?'. Resolve relative dates
            ('today', 'this week', 'next Monday') from the time in square brackets at the start of the message.

            Args:
                start_date: First day, YYYY-MM-DD (or YYYY-MM-DDTHH:MM to start mid-day).
                end_date: Last day inclusive, YYYY-MM-DD. Leave empty for just the start day.
                    'This week' means today through the coming Sunday.
            """
            start = _parse(start_date, "start_date")
            end = _parse(end_date, "end_date") if end_date else start
            if "T" not in end_date:  # a bare date means the end of that whole day
                end = datetime.combine(end.date(), datetime.min.time()) + timedelta(days=1)
            start, end = start.replace(tzinfo=LOCAL_TZ), end.replace(tzinfo=LOCAL_TZ)

            calendars = self._event_calendars()
            with ThreadPoolExecutor(max_workers=8) as pool:
                found = list(pool.map(lambda c: (c, c.search(start=start, end=end, event=True, expand=True)), calendars))
            rows = []
            for cal, events in found:
                for ev in events:
                    for comp in ev.icalendar_instance.walk("VEVENT"):
                        s = comp.decoded("DTSTART")
                        all_day = not isinstance(s, datetime)
                        s_local = _as_local(s)
                        e_raw = comp.decoded("DTEND") if "DTEND" in comp else None
                        e_local = _as_local(e_raw) if e_raw else s_local + timedelta(days=1 if all_day else 0)
                        rows.append(
                            (
                                s_local,
                                _describe(
                                    str(comp.get("SUMMARY", "Untitled")),
                                    s_local,
                                    e_local,
                                    all_day,
                                    str(comp.get("LOCATION", "")),
                                    cal.name,
                                ),
                            )
                        )
            if not rows:
                return "Nothing on the calendar in that range."
            return "\n".join(text for _, text in sorted(rows, key=lambda r: r[0]))

        def calendar_add_event(
            title: str,
            start: str,
            end: str = "",
            all_day: bool = False,
            location: str = "",
            notes: str = "",
            calendar: str = "",
            alert_minutes_before: int = -1,
            repeat: str = "",
            repeat_until: str = "",
        ) -> str:
            """Add an event to the user's iPhone/iCloud calendar, e.g. 'add dentist tomorrow at 3pm',
            'put Mum's birthday on 4 March, all day, repeating yearly'. Resolve relative dates from the time in
            square brackets at the start of the message. If the user gave no time for a non-all-day event, ask
            for one rather than guessing.

            Args:
                title: Event title.
                start: Start as YYYY-MM-DDTHH:MM (24h, local time), or YYYY-MM-DD for an all-day event.
                end: End in the same format. Leave empty for a 1 hour event (or a single day if all-day).
                    For a multi-day all-day event give the last day itself, inclusive.
                all_day: True for all-day events (birthdays, holidays, trips).
                location: Optional place or address.
                notes: Optional notes/description.
                calendar: Optional calendar name, e.g. 'Work' or 'Home'. Empty uses the first writable one.
                alert_minutes_before: Minutes before the start to notify, e.g. 15, 60, 1440 for a day before.
                    -1 for no alert; 0 for at the time of the event.
                repeat: Optional 'daily', 'weekly', 'monthly' or 'yearly'.
                repeat_until: Optional last day of the repeat, YYYY-MM-DD. Empty repeats forever.
            """
            from icalendar import Alarm, Event
            from icalendar import Calendar as ICal

            s = _parse(start, "start")
            all_day = all_day or "T" not in start
            if all_day:
                s_val = s.date()
                e_val = (_parse(end, "end").date() if end else s.date()) + timedelta(days=1)  # DTEND is exclusive
            else:
                s_val = s.replace(tzinfo=LOCAL_TZ)
                e_val = _parse(end, "end").replace(tzinfo=LOCAL_TZ) if end else s_val + timedelta(hours=1)
                if e_val <= s_val:
                    return "The end time must be after the start time."

            ev = Event()
            ev.add("uid", str(uuid.uuid4()))
            ev.add("dtstamp", datetime.now(tz.UTC))
            ev.add("summary", title)
            ev.add("dtstart", s_val)
            ev.add("dtend", e_val)
            if location:
                ev.add("location", location)
            if notes:
                ev.add("description", notes)
            if repeat:
                freq = REPEATS.get(repeat.lower().strip())
                if not freq:
                    return "repeat must be daily, weekly, monthly or yearly."
                rule: dict[str, object] = {"freq": freq}
                if repeat_until:
                    until = _parse(repeat_until, "repeat_until").date()
                    rule["until"] = (
                        until if all_day else datetime.combine(until, datetime.max.time(), tzinfo=LOCAL_TZ).astimezone(tz.UTC)
                    )
                ev.add("rrule", rule)
            if alert_minutes_before >= 0:
                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("description", title)
                alarm.add("trigger", -timedelta(minutes=alert_minutes_before))
                ev.add_component(alarm)

            cal = ICal()
            cal.add("prodid", "-//JARVIS//EN")
            cal.add("version", "2.0")
            cal.add_component(ev)

            calendars = self._event_calendars()
            if not calendars:
                return "I couldn't find any calendars on the account."
            target = None
            if calendar:
                want = calendar.lower().strip()
                target = next((c for c in calendars if (c.name or "").lower() == want), None) or next(
                    (c for c in calendars if want in (c.name or "").lower()), None
                )
                if not target:
                    return f"No calendar named '{calendar}'. Available: {', '.join(c.name or '?' for c in calendars)}."
            target = target or calendars[0]
            target.save_event(cal.to_ical().decode())

            summary = _describe(title, _as_local(s_val), _as_local(e_val), all_day, location, target.name)
            extras = (f", repeating {repeat.lower()}" if repeat else "") + (
                f", alert {alert_minutes_before} minutes before" if alert_minutes_before >= 0 else ""
            )
            return f"Added {summary}{extras}."

        def calendar_list_calendars() -> str:
            """List the names of the user's calendars (e.g. Home, Work), to choose where an event goes."""
            return ", ".join(c.name or "unnamed" for c in self._event_calendars()) or "None."

        return [calendar_list_events, calendar_add_event, calendar_list_calendars]
