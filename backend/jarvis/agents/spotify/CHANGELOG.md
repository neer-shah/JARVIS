# Changelog

## Unreleased
- Moved from `jarvis/environments/` into its own agent with a dedicated prompt and chat history.
  JARVIS now calls it through a single `spotify_agent(request)` tool.
- Pause, resume, skip, back, volume and now-playing stay direct tools on JARVIS for speed.
