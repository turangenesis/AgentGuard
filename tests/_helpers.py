"""Shared test helpers: a scripted fake worker (no API key needed) + message builders."""

from __future__ import annotations

from langchain_core.messages import AIMessage


class FakeWorker:
    """A stand-in for the bound ChatAnthropic worker: returns scripted AIMessages.

    Stateful — each ``invoke`` returns the next message in the script, so a single
    instance can drive a run across the start call and a later resume call.
    """

    def __init__(self, script: list[AIMessage]):
        self._script = list(script)
        self._i = 0

    def invoke(self, messages, config=None) -> AIMessage:  # noqa: ARG002 - matches Runnable
        if self._i < len(self._script):
            msg = self._script[self._i]
            self._i += 1
            return msg
        return AIMessage(content="[fake worker done]")


def ai_tool(name: str, args: dict, call_id: str = "c1") -> AIMessage:
    """An assistant turn proposing one tool call."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def ai_final(text: str = "done") -> AIMessage:
    """An assistant turn with no tool call — the worker is finished."""
    return AIMessage(content=text)
