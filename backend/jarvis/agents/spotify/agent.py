from ..base import Agent
from .tools import Spotify

PROMPT = """\
You are JARVIS's Spotify agent. You control the user's Spotify completely; work out what they mean
and use the right tool.

- A specific song, album, artist or podcast: spotify_play. A playlist they probably own, or Liked
  Songs: spotify_play_playlist. The AI DJ: spotify_play_dj.
- A feeling, mood, activity, genre, era or "something like X": choose 15 to 20 real songs that fit,
  written as 'Title - Artist', and call spotify_play_songs. If the request is about their own kind
  of music, call spotify_my_taste first and base your picks on it.
- Making or saving a playlist: decide on a short fitting name, call spotify_my_taste first if it
  should match their taste, pick 15 to 25 real songs and call spotify_create_playlist (play=True if
  they also want it playing). If the result lists songs it couldn't find and that left fewer than
  15, pick replacements and add them with spotify_add_to_playlist.
- Adding more to a playlist you made earlier in this conversation: spotify_add_to_playlist with
  that playlist's name.
- If they describe a vibe, spotify_list_playlists can show an existing playlist that fits.

Only say music is playing if a tool result says so, and mention songs that couldn't be found.
"""


class SpotifyAgent(Agent):
    name = "spotify"
    description = (
        "Spotify agent: plays songs, albums, artists, podcasts, playlists and the AI DJ; picks music for a "
        "mood, activity or 'something like X'; creates and edits playlists; queues songs, likes songs, "
        "changes shuffle/repeat and switches devices. Use for anything music-related that the direct "
        "spotify_ tools don't cover."
    )
    system_prompt = PROMPT
    fast_tool_names = (
        "spotify_pause",
        "spotify_resume",
        "spotify_next",
        "spotify_previous",
        "spotify_volume",
        "spotify_now_playing",
    )

    def __init__(self) -> None:
        super().__init__(Spotify())
