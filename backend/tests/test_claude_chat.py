from types import SimpleNamespace

from jarvis.claude_chat import ClaudeChat


def text(value, stop_reason="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=value)], stop_reason=stop_reason)


def tool_use(name, input, id="tool_1"):
    block = SimpleNamespace(type="tool_use", id=id, name=name, input=input)
    return SimpleNamespace(content=[SimpleNamespace(type="text", text="One moment."), block], stop_reason="tool_use")


class FakeMessages:
    """Stands in for client.messages: returns scripted responses and records each request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **kwargs):
        self.requests.append(dict(kwargs, messages=list(kwargs["messages"])))  # snapshot: history keeps growing
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_chat(*responses):
    def get_time(zone: str = "local") -> str:
        """Current time.

        Args:
            zone: Time zone name.
        """
        return f"noon in {zone}"

    chat = ClaudeChat("You are JARVIS.", [get_time], "claude-opus-5-5")
    chat.client = SimpleNamespace(messages=FakeMessages(*responses))
    return chat


def test_tool_call_is_run_and_its_result_sent_back():
    chat = make_chat(tool_use("get_time", {"zone": "Paris"}), text("It is noon in Paris."))
    assert chat.send("what time is it in Paris?") == "It is noon in Paris."

    first, second = chat.client.messages.requests
    assert first["model"] == "claude-opus-5-5"
    assert first["system"] == "You are JARVIS."
    assert first["tools"][0]["name"] == "get_time"
    result = second["messages"][-1]["content"][0]
    assert result == {"type": "tool_result", "tool_use_id": "tool_1", "content": "noon in Paris"}


def test_history_is_kept_between_messages():
    chat = make_chat(text("Hello."), text("Still here."))
    chat.send("hi")
    chat.send("are you there?")
    sent = chat.client.messages.requests[1]["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]


def test_echoed_time_stamp_is_not_spoken():
    chat = make_chat(text("[20:27] You have nothing on tomorrow."))
    assert chat.send("what's on?") == "You have nothing on tomorrow."


def test_failed_request_is_spoken_and_leaves_no_dangling_tool_call():
    chat = make_chat(RuntimeError("boom"))
    assert chat.send("hello") == "Sorry, I hit a problem: boom"
    assert chat.messages == []


def test_bad_tool_arguments_are_reported_back_to_the_model():
    chat = make_chat(tool_use("get_time", {"zone": 5, "extra": True}), text("Sorry, I got that wrong."))
    chat.send("time?")
    result = chat.client.messages.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True


def test_unknown_tool_is_reported_back_to_the_model():
    chat = make_chat(tool_use("launch_rockets", {}), text("I can't do that."))
    chat.send("launch")
    result = chat.client.messages.requests[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    assert "unknown tool" in result["content"]
