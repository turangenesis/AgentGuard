"""A scripted, key-free worker that drives a deterministic demo run.

The dashboard's "Run demo" button starts a graph with this worker instead of the
real LLM, so the full SAFE / BLOCKED / APPROVAL_REQUIRED flow — including a real
``interrupt()`` pause for human approval — can be watched without an ANTHROPIC_API_KEY.

It is stateless on purpose: each worker turn is chosen from the message history
(how many tool results have come back), never an internal counter — so it behaves
correctly even though the API rebuilds a fresh worker on every resume.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

DEMO_TASK = "Inspect the service, clean up the workspace, and deploy the build to production."

# Ordered (tool, args) — one per worker turn, chosen to hit all three verdicts:
#   1. read a normal source file   -> SAFE     (executes; real read of sample-target/)
#   2. a destructive shell command -> BLOCKED  (denied outright, never runs)
#   3. deploy to production        -> APPROVAL (pauses for a human at interrupt())
_SCRIPT: list[tuple[str, dict]] = [
    ("read_file", {"path": "src/index.ts"}),
    ("run_shell", {"command": "rm -rf / --no-preserve-root"}),
    ("deploy", {"target": "production"}),
]

_DONE = (
    "Demo complete. You just watched Headroom execute a SAFE file read, BLOCK a "
    "destructive shell command outright, and PAUSE a production deploy for your approval."
)


class _ScriptedWorker:
    """Mimics the bound ChatAnthropic worker: ``.invoke(messages) -> AIMessage``."""

    def invoke(self, messages: list, config: Any = None) -> AIMessage:  # noqa: ARG002
        # One tool result per resolved action, so the count is our position in the script.
        n = sum(1 for m in messages if isinstance(m, ToolMessage))
        if n < len(_SCRIPT):
            name, args = _SCRIPT[n]
            return AIMessage(
                content="",
                tool_calls=[{"name": name, "args": args, "id": f"demo-{n}", "type": "tool_call"}],
            )
        return AIMessage(content=_DONE)


def demo_worker() -> _ScriptedWorker:
    """Return a fresh scripted worker for a demo run (no API key required)."""
    return _ScriptedWorker()
