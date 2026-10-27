"""Shared Gemini helpers used by JARVIS's brain and by every domain agent."""

import functools
import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from google import genai
from google.genai import errors, types

from . import config

_client: genai.Client | None = None
_ECHOED_STAMP = re.compile(r"^\s*\[[^\]]*\d{1,2}:\d{2}[^\]]*\]\s*")  # models sometimes copy our time stamp


def client() -> genai.Client:
    """One Gemini client for the whole process."""
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise ValueError("GOOGLE_GENAI_API_KEY is not set (see .env).")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def safe(fn: Callable[..., str], label: str = "tool") -> Callable[..., str]:
    """Log each tool call and turn exceptions into text the model can relay."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        started = time.perf_counter()
        print(f"[{label}] {fn.__name__}({kwargs or args})")
        try:
            result = fn(*args, **kwargs)
            print(f"[{label}] {fn.__name__} ok in {time.perf_counter() - started:.2f}s")
            return result
        except Exception as e:
            print(f"[{label}] {fn.__name__} failed in {time.perf_counter() - started:.2f}s: {e!r}")
            return f"Error: {e}"

    return wrapper


def make_chat(system_prompt: str, tools: list[Callable[..., str]], model: str | None, temperature: float = 0.4) -> Any:
    """A Gemini chat that runs the given Python tools itself (automatic function calling)."""
    model = model or config.MODEL
    if not model:
        raise ValueError("JARVIS_MODEL is not set (see .env).")
    # Turning thinking off makes replies faster, but "lite" models reject that setting with a 400.
    thinking = None if "lite" in model else types.ThinkingConfig(thinking_budget=0)
    return client().chats.create(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=list(tools) or None,
            thinking_config=thinking,
            temperature=temperature,
        ),
    )


def stamp(text: str) -> str:
    """Models don't know the time, so tell them with every message (saves a tool call)."""
    return f"[Current local time: {datetime.now():%A %d %B %Y, %H:%M}]\n{text}"


def send(chat: Any, text: str, who: str = "brain", retries: int = 3) -> str:
    """Send one message, retrying transient Gemini errors. Always returns speakable text.

    Sub-agents use fewer retries: the brain's own retry would otherwise multiply theirs.
    """
    for attempt in range(retries + 1):
        try:
            reply = _ECHOED_STAMP.sub("", chat.send_message(stamp(text)).text or "")
            return reply.strip() or "Done."
        except errors.APIError as e:
            if e.code == 429 and "PerDay" in str(e):  # retrying can't help until the quota resets
                return "I've used up today's free Gemini quota, so I can't think until it resets."
            # 503 = Google overloaded, 429 = free-tier rate limit: both usually clear up quickly
            if e.code in (429, 503) and attempt < retries:
                wait = 2**attempt
                print(f"[{who}] {e.code}, retrying in {wait}s")
                time.sleep(wait)
                continue
            if e.code in (429, 503):
                return "Google's servers are overloaded right now. Please try again in a moment."
            return f"Sorry, I hit a problem: {e}"
        except Exception as e:
            return f"Sorry, I hit a problem: {e}"
    return "Sorry, I couldn't get an answer."
