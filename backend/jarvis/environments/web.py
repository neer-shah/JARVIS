from .. import config
from ..claude_chat import client
from .base import Environment


class Web(Environment):
    """Live web lookups via Anthropic's web search tool, run by a small Claude model.

    Done as a separate, search-only model call so the search tool is never mixed with our own function tools.
    """

    name = "web"

    def available(self):
        return bool(config.ANTHROPIC_API_KEY)

    def tools(self):
        def web_search(query: str) -> str:
            """Search the web for current or factual information the assistant doesn't reliably
            know: news, weather, sports scores, prices, recent events, facts about people or places.
            Not needed for the current date/time or for questions about JARVIS itself.

            Args:
                query: A self-contained search question, e.g. 'weather in London today'.
            """
            messages = [{"role": "user", "content": f"Answer briefly (two sentences max) using web search: {query}"}]
            for _ in range(3):  # a long search can pause; resend the turn so the server carries on
                response = client().messages.create(
                    model=config.AGENT_MODEL,
                    max_tokens=2048,
                    output_config={"effort": "low"},
                    tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                    messages=messages,
                )
                if response.stop_reason != "pause_turn":
                    break
                messages.append({"role": "assistant", "content": response.content})
            text = "".join(block.text for block in response.content if block.type == "text").strip()
            return text or "I couldn't find anything."

        return [web_search]
