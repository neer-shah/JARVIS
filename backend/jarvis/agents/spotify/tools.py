import difflib
import functools
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ...environments.base import Environment

DJ_URI = "spotify:playlist:37i9dQZF1EYkqdzj48dyYq"  # Spotify's AI DJ
SCOPES = (
    "user-modify-playback-state user-read-playback-state user-read-currently-playing "
    "user-library-read user-library-modify user-top-read user-read-recently-played "
    "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"
)
PLAY_KINDS = {"track": "track", "song": "track", "album": "album", "artist": "artist", "podcast": "show", "show": "show"}
LIKED_NAMES = ("liked", "liked songs", "my liked songs", "favourites", "favorites", "saved songs")


def _songs(n: int) -> str:
    return f"{n} song{'s' if n != 1 else ''}"


def _explain(e) -> str:
    """Turn a spotipy error into something the model can say out loud."""
    status, text = getattr(e, "http_status", None), str(e)
    if status == 403 and "premium" in text.lower():
        return "Spotify Premium is required to control playback."
    if status == 403 and "restriction" in text.lower():
        return "Spotify says that isn't possible right now, probably it's already in that state."
    if status == 404:
        return "Spotify couldn't find a device or item for that."
    if status == 429:
        return "Spotify is rate limiting me. Try again in a moment."
    return f"Spotify refused ({status}): {getattr(e, 'msg', text)}"


class Spotify(Environment):
    """Needs SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI in .env
    (the URI must match a Redirect URI in your Spotify developer app). Premium is required
    for playback control. Every tool launches the desktop app first if Spotify isn't open.

    Spotify has removed its recommendation/audio-feature endpoints for new apps, so moods and
    "something like X" work by the model choosing the songs itself; we only look them up here.
    """

    name = "spotify"

    def __init__(self):
        self._sp = None
        self._user_id = None
        self._dev = None  # device id for the tool call in progress, set by _guard

    def available(self):
        return all(os.getenv(k) for k in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"))

    @property
    def sp(self):
        if self._sp is None:  # lazy so startup stays fast
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth

            self._sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
                    scope=SCOPES,
                    cache_path=str(Path(__file__).resolve().parents[3] / ".spotify_cache"),
                )
            )
        return self._sp

    @property
    def user_id(self):
        if self._user_id is None:
            self._user_id = self.sp.current_user()["id"]
        return self._user_id

    # --- devices ---------------------------------------------------------------------------

    def _pick_device(self):
        """The active device, else this PC's Spotify app. Never an idle phone or speaker."""
        devices = self.sp.devices()["devices"]
        chosen = next((d for d in devices if d["is_active"]), None) or next((d for d in devices if d["type"] == "Computer"), None)
        return chosen["id"] if chosen else None

    def _ensure_open(self):
        """Device id to control. Launches the desktop app first if Spotify isn't open."""
        device = self._pick_device()
        if device:
            return device
        try:
            os.startfile("spotify:")  # Windows URI handler for the installed desktop app
        except OSError:
            raise RuntimeError("Spotify isn't open and I couldn't launch it. Is the desktop app installed?")
        for _ in range(20):  # wait up to ~20s for the app to register as a device
            time.sleep(1)
            device = self._pick_device()
            if device:
                return device
        raise RuntimeError("I opened Spotify but it didn't show up in time. Try again in a moment.")

    def _guard(self, fn):
        """Open Spotify before every tool (if needed) and translate API errors into plain text."""

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                self._dev = self._ensure_open()
                return fn(*args, **kwargs)
            except Exception as e:
                if hasattr(e, "http_status"):  # spotipy.SpotifyException
                    raise RuntimeError(_explain(e)) from None
                raise

        return wrapper

    def _play(self, **target):
        """start_playback on the chosen device. Retries a 404, which a just-launched app gives while still waking up."""
        for attempt in range(3):
            try:
                return self.sp.start_playback(device_id=self._dev, **target)
            except Exception as e:
                if getattr(e, "http_status", None) == 404 and attempt < 2:
                    time.sleep(1.5)
                    continue
                raise

    # --- lookups ---------------------------------------------------------------------------

    def _find(self, query, kind):
        items = self.sp.search(q=query, type=kind, limit=5)[kind + "s"]["items"]
        return next((i for i in items if i), None)

    def _resolve_tracks(self, songs):
        """'Title - Artist' strings -> (unique track URIs in order, strings that matched nothing)."""

        def lookup(song):
            title, _, artist = song.replace('"', "").rpartition(" - ")
            queries = [f'track:"{title}" artist:"{artist}"'] if title else []  # precise first, then loose
            queries.append(song.replace(" - ", " "))
            for q in queries:
                items = self.sp.search(q=q, type="track", limit=1)["tracks"]["items"]
                if items and items[0]:
                    return items[0]["uri"]
            return None

        with ThreadPoolExecutor(max_workers=5) as pool:
            uris = list(pool.map(lookup, songs))
        missing = [s for s, u in zip(songs, uris) if not u]
        return list(dict.fromkeys(u for u in uris if u)), missing

    def _my_playlists(self):
        mine, page = [], self.sp.current_user_playlists(limit=50)
        while page:
            mine += [p for p in page["items"] if p]
            page = self.sp.next(page) if page["next"] else None
        return mine

    @staticmethod
    def _best_playlist(want, playlists):
        """Exact name, else the shortest name containing it, else the closest spelling."""
        by_name = {p["name"].lower(): p for p in playlists}
        if want in by_name:
            return by_name[want]
        containing = [n for n in by_name if want in n]
        if containing:
            return by_name[min(containing, key=len)]
        close = difflib.get_close_matches(want, by_name, n=1, cutoff=0.6)
        return by_name[close[0]] if close else None

    def _current_track(self):
        playing = self.sp.current_playback()
        item = (playing or {}).get("item")
        if not item or item.get("type") != "track":
            raise RuntimeError("No song is playing right now.")
        return item

    @staticmethod
    def _label(item):
        artists = item.get("artists")
        return f"{item['name']} by {artists[0]['name']}" if artists else item["name"]

    # --- tools -----------------------------------------------------------------------------

    def tools(self):
        def spotify_play(query: str, kind: str = "track") -> str:
            """Search Spotify and play one specific song, album, artist or podcast. For the user's own
            playlists or Liked Songs use spotify_play_playlist, for the DJ use spotify_play_dj, and for a
            mood, activity or "something like X" use spotify_play_songs.

            Args:
                query: What to play, e.g. 'Bohemian Rhapsody by Queen', 'Dark Side of the Moon', 'Radiohead'.
                kind: 'track' (default, a single song), 'album', 'artist' or 'podcast'.
            """
            search_kind = PLAY_KINDS.get(kind.lower().strip())
            if not search_kind:
                return "kind must be track, album, artist or podcast."
            item = self._find(query, search_kind)
            if not item:
                return f"No {search_kind} found for '{query}'."
            if search_kind == "track":
                self._play(uris=[item["uri"]])
            else:
                self._play(context_uri=item["uri"])
            return f"Playing {self._label(item)}."

        def spotify_play_playlist(name: str) -> str:
            """Play a playlist by the name the user said: one of their own, Liked Songs, or any Spotify
            playlist. If there's no exact match it plays the closest one; the result says which, so tell the user.

            Args:
                name: The playlist name as the user said it, e.g. 'gym', 'liked songs'.
            """
            want = name.lower().strip()
            if want in LIKED_NAMES:
                items = self.sp.current_user_saved_tracks(limit=50)["items"]
                if items:
                    self.sp.shuffle(True, device_id=self._dev)
                    self._play(uris=[i["track"]["uri"] for i in items])
                    return "Playing your Liked Songs."
            match = self._best_playlist(want, self._my_playlists())
            from_library = match is not None
            if not match:
                match = self._find(name, "playlist")
            if not match:
                return f"I couldn't find any playlist like '{name}'."
            self._play(context_uri=match["uri"])
            if match["name"].lower() == want:
                return f"Playing {match['name']}."
            if from_library:
                return f"I couldn't find '{name}' exactly, so I'm playing your closest playlist, '{match['name']}'."
            return f"You have no playlist like '{name}', so I'm playing the Spotify playlist '{match['name']}'."

        def spotify_play_dj() -> str:
            """Start Spotify's AI DJ, the personalised voice-guided radio. Use for 'play DJ', 'put on the DJ'."""
            try:
                self._play(context_uri=DJ_URI)
                time.sleep(2)  # the API can accept the call yet not actually start the DJ, so check
                state = self.sp.current_playback() or {}
                if state.get("is_playing") and (state.get("context") or {}).get("uri") == DJ_URI:
                    return "The DJ is on."
            except Exception as e:
                print(f"[spotify] DJ via API failed: {e!r}")
            os.startfile(DJ_URI)
            return (
                "I asked Spotify to start the DJ but couldn't confirm it started, so I opened it in the app. "
                "The user may need to press play on the DJ card."
            )

        def spotify_play_songs(songs: list[str], description: str = "") -> str:
            """Play a set of songs YOU choose, in order. Use this for feelings, moods, activities, genres,
            eras or "something like X" ("I'm sad", "focus music", "90s hip hop", "songs like Daft Punk").
            Pick 15 to 20 real, well-known songs that fit; if the user wants their own taste, call
            spotify_my_taste first. To save them as a playlist use spotify_create_playlist instead.

            Args:
                songs: Songs as 'Title - Artist', e.g. ['Mr. Brightside - The Killers'].
                description: Short note of what the set is for, e.g. 'upbeat gym workout'.
            """
            uris, missing = self._resolve_tracks(songs)
            if not uris:
                return "I couldn't find any of those songs on Spotify."
            self._play(uris=uris[:100])
            note = f" ({len(missing)} I couldn't find: {', '.join(missing)})" if missing else ""
            return f"Playing {_songs(len(uris))}{' for ' + description if description else ''}.{note}"

        def spotify_create_playlist(name: str, songs: list[str], description: str = "", play: bool = False) -> str:
            """Create a new private playlist in the user's library, filled with songs YOU choose to fit the
            request ('make me a roadtrip playlist', 'a playlist for studying'). Pick 15 to 25 real songs
            unless the user names specific ones, or none for an empty playlist.

            Args:
                name: Playlist name.
                songs: Songs as 'Title - Artist'. May be empty.
                description: Optional short description.
                play: True to start playing it straight away.
            """
            uris, missing = self._resolve_tracks(songs)
            playlist = self.sp.current_user_playlist_create(name, public=False, description=description)
            for i in range(0, len(uris), 100):  # Spotify takes 100 items per request
                self.sp.playlist_add_items(playlist["id"], uris[i : i + 100])
            reply = f"Created '{name}' with {_songs(len(uris))}."
            if missing:
                reply += f" I couldn't find: {', '.join(missing)}."
            if play and uris:
                self._play(context_uri=playlist["uri"])
                reply += " Playing it now."
            return reply

        def spotify_add_to_playlist(playlist: str, songs: list[str] | None = None) -> str:
            """Add songs to one of the user's own playlists. With no songs, adds the song playing right now,
            e.g. 'add this to my gym playlist'.

            Args:
                playlist: Name of the playlist to add to, as the user said it.
                songs: Songs as 'Title - Artist'. Leave empty for the currently playing song.
            """
            editable = [p for p in self._my_playlists() if p["owner"]["id"] == self.user_id or p.get("collaborative")]
            match = self._best_playlist(playlist.lower().strip(), editable)
            if not match:
                return f"I couldn't find a playlist of yours like '{playlist}' that I can edit."
            if songs:
                uris, missing = self._resolve_tracks(songs)
            else:
                uris, missing = [self._current_track()["uri"]], []
            if not uris:
                return "I couldn't find any of those songs on Spotify."
            self.sp.playlist_add_items(match["id"], uris)
            reply = f"Added {_songs(len(uris))} to {match['name']}."
            return reply + (f" I couldn't find: {', '.join(missing)}." if missing else "")

        def spotify_list_playlists() -> str:
            """List the names of the user's playlists ('what playlists do I have?'). Also use it to pick one
            that suits a mood or to check what exists."""
            names = [p["name"] for p in self._my_playlists()]
            return ("Liked Songs, " + ", ".join(names[:100])) if names else "Liked Songs only; no playlists yet."

        def spotify_my_taste() -> str:
            """The user's top artists, top songs and recent plays. Use it to personalise picks for
            spotify_play_songs / spotify_create_playlist when they ask for 'my kind of music' or similar."""
            artists = self.sp.current_user_top_artists(limit=10, time_range="medium_term")["items"]
            tracks = self.sp.current_user_top_tracks(limit=10, time_range="medium_term")["items"]
            recent = self.sp.current_user_recently_played(limit=10)["items"]
            top_artists = "; ".join(a["name"] + (f" ({', '.join(a['genres'][:2])})" if a.get("genres") else "") for a in artists)
            return (
                f"Top artists: {top_artists}.\n"
                f"Top songs: {'; '.join(self._label(t) for t in tracks)}.\n"
                f"Recently played: {'; '.join(self._label(r['track']) for r in recent)}."
            )

        def spotify_now_playing() -> str:
            """Say what is playing right now (song, artist, whether it's paused, volume), e.g. 'what's playing?',
            'what song is this?'."""
            state = self.sp.current_playback()
            item = (state or {}).get("item")
            if not item:
                return "Nothing is playing."
            label = item["name"]
            if item.get("type") == "episode":
                label += f" ({item['show']['name']})"
            else:
                label = self._label(item)
            volume = state["device"].get("volume_percent")
            status = "Playing" if state["is_playing"] else "Paused on"
            return (
                f"{status} {label} on {state['device']['name']}"
                f"{'' if volume is None else f', volume {volume}%'}"
                f", shuffle {'on' if state.get('shuffle_state') else 'off'}, repeat {state.get('repeat_state')}."
            )

        def spotify_pause() -> str:
            """Pause Spotify playback, e.g. 'pause', 'stop the music'."""
            self.sp.pause_playback(device_id=self._dev)
            return "Paused."

        def spotify_resume() -> str:
            """Resume whatever was playing ('play', 'continue', 'play current')."""
            self._play()
            return "Resumed."

        def spotify_next() -> str:
            """Skip to the next track on Spotify, e.g. 'skip', 'next song'."""
            self.sp.next_track(device_id=self._dev)
            return "Skipped."

        def spotify_previous() -> str:
            """Go back to the previous track, or restart the current one if it has been playing a few seconds,
            e.g. 'go back', 'previous song', 'play that again'."""
            self.sp.previous_track(device_id=self._dev)
            return "Went back."

        def spotify_queue(query: str) -> str:
            """Add a song to the end of the queue so it plays after what's on now, e.g. 'queue Africa by Toto',
            'play Hey Jude after this'.

            Args:
                query: The song, e.g. 'Africa by Toto'.
            """
            track = self._find(query, "track")
            if not track:
                return f"No song found for '{query}'."
            self.sp.add_to_queue(track["uri"], device_id=self._dev)
            return f"Queued {self._label(track)}."

        def spotify_volume(percent: int, relative: bool = False) -> str:
            """Set or change the volume, e.g. 'volume 30', 'a bit louder', 'turn it down'.

            Args:
                percent: Target volume 0-100. With relative=True it is a change instead, e.g. 15 for
                    'a bit louder' or -15 for 'a bit quieter'.
                relative: True to add percent to the current volume instead of setting it.
            """
            level = percent
            if relative:
                device = (self.sp.current_playback() or {}).get("device") or {}
                level += device.get("volume_percent") or 50
            level = max(0, min(100, level))
            self.sp.volume(level, device_id=self._dev)
            return f"Volume {level}%."

        def spotify_shuffle(on: bool) -> str:
            """Turn shuffle on or off, e.g. 'shuffle on', 'stop shuffling'.

            Args:
                on: True for shuffle on, False for off.
            """
            self.sp.shuffle(on, device_id=self._dev)
            return f"Shuffle {'on' if on else 'off'}."

        def spotify_repeat(mode: str) -> str:
            """Set repeat mode, e.g. 'repeat this song', 'repeat the playlist', 'repeat off'.

            Args:
                mode: 'off', 'track' (repeat this song) or 'context' (repeat the whole playlist or album).
            """
            mode = {"one": "track", "song": "track", "all": "context", "playlist": "context", "album": "context"}.get(
                mode.lower().strip(), mode.lower().strip()
            )
            if mode not in ("off", "track", "context"):
                return "mode must be off, track or context."
            self.sp.repeat(mode, device_id=self._dev)
            return f"Repeat {mode}."

        def spotify_like_current(remove: bool = False) -> str:
            """Save the song playing now to Liked Songs ('like this song'), or remove it from them.

            Args:
                remove: True to remove it from Liked Songs instead ('unlike this').
            """
            track = self._current_track()
            if remove:
                self.sp.current_user_saved_tracks_delete([track["uri"]])
                return f"Removed {self._label(track)} from your Liked Songs."
            self.sp.current_user_saved_tracks_add([track["uri"]])
            return f"Added {self._label(track)} to your Liked Songs."

        def spotify_devices() -> str:
            """List the devices Spotify can play on (this PC, phone, speakers) and which is active,
            e.g. 'what devices can I play on?'."""
            devices = self.sp.devices()["devices"]
            return "; ".join(f"{d['name']} ({d['type']}){' [active]' if d['is_active'] else ''}" for d in devices) or "None."

        def spotify_switch_device(name: str) -> str:
            """Move playback to another device, e.g. 'play on my phone', 'switch to the kitchen speaker'.

            Args:
                name: Device name or type as the user said it, e.g. 'phone', 'kitchen'.
            """
            want = name.lower().strip()
            devices = self.sp.devices()["devices"]
            match = next((d for d in devices if want in d["name"].lower() or want == d["type"].lower()), None)
            if not match:
                return f"No device like '{name}'. Available: {', '.join(d['name'] for d in devices)}."
            self.sp.transfer_playback(match["id"], force_play=True)
            return f"Playing on {match['name']}."

        return [
            self._guard(fn)
            for fn in (
                spotify_play,
                spotify_play_playlist,
                spotify_play_dj,
                spotify_play_songs,
                spotify_create_playlist,
                spotify_add_to_playlist,
                spotify_list_playlists,
                spotify_my_taste,
                spotify_now_playing,
                spotify_pause,
                spotify_resume,
                spotify_next,
                spotify_previous,
                spotify_queue,
                spotify_volume,
                spotify_shuffle,
                spotify_repeat,
                spotify_like_current,
                spotify_devices,
                spotify_switch_device,
            )
        ]
