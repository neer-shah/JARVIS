# Spotify agent

Controls the user's Spotify: playback, music picked for a mood, and playlists.

**Entry point for JARVIS:** `spotify_agent(request)`.

**Fast tools** also given straight to JARVIS, so simple commands skip the agent's model call:
`spotify_pause`, `spotify_resume`, `spotify_next`, `spotify_previous`, `spotify_volume`, `spotify_now_playing`.

**Internal tools** (in `tools.py`): play, play_playlist, play_dj, play_songs, create_playlist,
add_to_playlist, list_playlists, my_taste, queue, shuffle, repeat, like_current, devices,
switch_device, plus the fast tools above.

The agent keeps its own chat history, so follow-ups like "add five more songs to it" work.

## Setup
`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_REDIRECT_URI` in `backend/.env`.
Premium is required for playback control. The OAuth token is cached in `backend/.spotify_cache`.

Spotify has removed its recommendation endpoints for new apps, so the agent's model picks songs
itself and the tools only look them up.
