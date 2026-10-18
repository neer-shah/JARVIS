from google import genai
from google.genai import types

from .. import config
from .base import Environment


class Web(Environment):
    """Live web lookups via Gemini's built-in Google Search grounding.

    Done as a separate, search-only model call because Gemini can't always mix the search
    tool with our own function tools in a single request.
    """

    name = "web"

    def available(self):
        return bool(config.GEMINI_API_KEY)

    def tools(self):
        def web_search(query: str) -> str:
            """Search the web for current or factual information the assistant doesn't reliably
            know: news, weather, sports scores, prices, recent events, facts about people or places.
            Not needed for the current date/time or for questions about JARVIS itself.

            Args:
                query: A self-contained search question, e.g. 'weather in London today'.
            """
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            resp = client.models.generate_content(
                model=config.MODEL,
                contents=f"Answer briefly (two sentences max) using web search: {query}",
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return resp.text or "I couldn't find anything."

        return [web_search]
