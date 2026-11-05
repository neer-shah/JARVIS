"""Claude as JARVIS's brain: a tool-use loop over plain Python functions.

The domain agents still use Gemini (see llm.py). Claude has no automatic function calling in the SDK,
so this loop runs each tool the model asks for and sends the results back until it answers.
"""

import re
from collections.abc import Callable
from typing import Any

import anthropic
from anthropic import beta_tool

from . import config
from .llm import stamp

_ECHOED_STAMP = re.compile(r"^\s*\[[^\]]*\d{1,2}:\d{2}[^\]]*\]\s*")  # models sometimes copy our time stamp
_BUSY_STATUS = (429, 500, 503, 529)  # rate limited or overloaded: usually clears up in a moment
MAX_STEPS = 8  # tool rounds per request, so a confused model can't loop forever


class ClaudeChat:
    """One conversation with Claude that runs the given tools itself. History is kept between calls."""

    def __init__(self, system_prompt: str, tools: list[Callable[..., str]], model: str):
        self.system_prompt = system_prompt
        self.model = model
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.tools = {tool.name: tool for tool in (beta_tool(fn) for fn in tools)}
        self.schemas = [tool.to_dict() for tool in self.tools.values()]
        self.messages: list[dict[str, Any]] = []

    def send(self, text: str) -> str:
        """Send one utterance; returns the reply to speak. Always returns speakable text."""
        start = len(self.messages)  # on failure, drop this turn so the next request starts clean
        self.messages.append({"role": "user", "content": stamp(text)})
        try:
            for _ in range(MAX_STEPS):
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    system=self.system_prompt,
                    tools=self.schemas or anthropic.omit,
                    messages=self.messages,
                    output_config={"effort": "low"},  # spoken replies are short; low effort keeps them quick
                )
                self.messages.append({"role": "assistant", "content": response.content})
                calls = [block for block in response.content if block.type == "tool_use"]
                if not calls:
                    return _speak(response)
                self.messages.append({"role": "user", "content": [self._run(call) for call in calls]})
        except anthropic.APIStatusError as e:
            del self.messages[start:]
            if e.status_code in _BUSY_STATUS:
                return "Anthropic's servers are busy right now. Please try again in a moment."
            return f"Sorry, I hit a problem: {e}"
        except Exception as e:  # any failure is spoken, never raised into the voice loop
            del self.messages[start:]
            return f"Sorry, I hit a problem: {e}"
        del self.messages[start:]
        return "Sorry, that took too many steps."

    def _run(self, call: Any) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "tool_result", "tool_use_id": call.id}
        tool = self.tools.get(call.name)
        if tool is None:
            return result | {"content": f"Error: unknown tool {call.name}", "is_error": True}
        try:
            return result | {"content": str(tool.call(call.input))}
        except Exception as e:  # bad arguments; the tools themselves already catch their own errors
            return result | {"content": f"Error: {e}", "is_error": True}


def _speak(response: Any) -> str:
    if response.stop_reason == "refusal":
        return "Sorry, I can't help with that."
    text = "".join(block.text for block in response.content if block.type == "text")
    return _ECHOED_STAMP.sub("", text).strip() or "Done."
