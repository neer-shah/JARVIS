# Calendar agent

Reads and adds events on the user's iPhone (iCloud) calendar over CalDAV.

**Entry point for JARVIS:** `calendar_agent(request)`. No fast tools.

**Internal tools** (in `tools.py`): `calendar_list_events`, `calendar_add_event`, `calendar_list_calendars`.
It cannot delete or move events.

## Setup
`APPLE_ACCOUNT_EMAIL` and `APPLE_CALENDAR_PASSWORD` in `backend/.env`. The password is an
app-specific password from appleid.apple.com, not the Apple ID password.
