import functools
import time
from datetime import datetime

from google import genai
from google.genai import errors
from google.genai import types

from . import config
from .environments import discover
from .environments.base import Environment


def _safe(fn):
    """Log each tool call and turn exceptions into text the model can relay."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        print(f"[tool] {fn.__name__}({kwargs or args})")
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            print(f"[tool] {fn.__name__} failed: {e!r}")
            return f"Error: {e}"

    return wrapper


class Brain:
    """Gemini with all discovered environments' tools attached.

    Gemini decides which tool(s) to call; the SDK executes them and feeds results back
    (automatic function calling), then returns the final spoken-style reply.
    """

    def __init__(self, environments: list[Environment] | None = None):
        if not config.GEMINI_API_KEY:
            raise ValueError("GOOGLE_GENAI_API_KEY is not set (see .env).")
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.environments = environments if environments is not None else discover()

        tools, seen = [], set()
        for env in self.environments:
            for fn in env.tools():
                if fn.__name__ in seen:
                    raise ValueError(f"Duplicate tool name '{fn.__name__}' in environment '{env.name}'")
                seen.add(fn.__name__)
                tools.append(_safe(fn))
        print(f"[brain] environments: {[e.name for e in self.environments]}, tools: {sorted(seen)}")

        self.chat = self.client.chats.create(
            model=config.MODEL,
            config=types.GenerateContentConfig(
                system_instruction=config.SYSTEM_PROMPT,
                tools=tools or None,
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # faster replies,
                temperature=0.4
            ),
        )

    @staticmethod
    def _stamp(text: str) -> str:
        """Models don't know the time, so tell it with every message (saves a tool call)."""
        return f"[Current local time: {datetime.now():%A %d %B %Y, %H:%M}]\n{text}"

    def ask(self, text: str) -> str:
        """Send one user utterance; returns the reply to speak. Conversation history is kept."""
        for attempt in range(4):
            try:
                return (self.chat.send_message(self._stamp(text)).text or "Done.").strip()
            except errors.APIError as e:
                if e.code == 429 and "PerDay" in str(e):  # retrying can't help until the quota resets
                    return "I've used up today's free Gemini quota, so I can't think until it resets."
                # 503 = Google overloaded, 429 = free-tier rate limit: both usually clear up quickly
                if e.code in (429, 503) and attempt < 3:
                    wait = 2 ** attempt
                    print(f"[brain] {e.code}, retrying in {wait}s")
                    time.sleep(wait)
                    continue
                if e.code in (429, 503):
                    return "Google's servers are overloaded right now. Please try again in a moment."
                return f"Sorry, I hit a problem: {e}"
            except Exception as e:
                return f"Sorry, I hit a problem: {e}"
