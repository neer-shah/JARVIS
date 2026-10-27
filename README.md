# JARVIS
A voice and chat assistant powered by Google Gemini.

## How it's structured
JARVIS's main model routes each request to a **domain agent**. Each agent is a smaller model with
its own prompt, chat history and tools. JARVIS only sees one tool per agent.

```
JARVIS (backend/jarvis/brain.py, JARVIS_MODEL)
 ├─ spotify_agent(request)   backend/jarvis/agents/spotify/
 ├─ calendar_agent(request)  backend/jarvis/agents/calendar/
 ├─ fast tools: spotify_pause, spotify_resume, spotify_next, spotify_previous,
 │              spotify_volume, spotify_now_playing  (no second model call)
 └─ plain tools: web_search, get_current_time        backend/jarvis/environments/
```

Fuzzy, multi-step requests such as "make me a study playlist from my taste" go to an agent, which
can call several of its tools in a row. Simple commands such as "pause" go straight to a fast tool.

| Agent | What it does | Needs |
|---|---|---|
| spotify | Playback, mood picks, playlists, queue, devices | Spotify app + Premium |
| calendar | Read and add iCloud calendar events | iCloud app-specific password |

To add an agent, create `backend/jarvis/agents/<name>/agent.py` with a subclass of `Agent`
(see `backend/jarvis/agents/base.py`) and a `tools.py`. It is discovered automatically.

## Setup
```
cd backend
pip install -r requirements.txt
cp .env.example .env   # then fill it in
```

Environment variables, all in `backend/.env`:
- `GOOGLE_GENAI_API_KEY`, `JARVIS_MODEL`: required.
- `JARVIS_AGENT_MODEL`: optional model for the agents. It defaults to `JARVIS_MODEL`.
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`: for the Spotify agent.
- `APPLE_ACCOUNT_EMAIL`, `APPLE_CALENDAR_PASSWORD`: for the calendar agent.

## Run
Frontend:
```
cd frontend
python -m streamlit run app.py
```

Backend only, from `backend/`:
```
python main.py            # voice, with wake word
python main.py --text     # type instead of speaking
```

## Develop
From `backend/`:
```
pip install -r requirements-dev.txt
pytest
ruff check . && ruff format .
mypy
```
