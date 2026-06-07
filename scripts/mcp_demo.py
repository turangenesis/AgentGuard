"""Demo: act as an EXTERNAL agent plugging into Headroom over MCP.

Launches the Headroom MCP server (stdio) and, as a separate "host agent", submits three actions
through it — a safe read, a destructive shell command, and a production deploy — printing the
guard's verdict for each. This is exactly what a real client (Claude Code / Cursor) does after a
~4-line config change; here we prove the loop end-to-end with no real client needed.

Run:  python scripts/mcp_demo.py
The deploy lands as 'pending' — approve it on the dashboard (uvicorn headroom.api:app) and the
agent's next check_review would see 'approved'. Uses a throwaway DB so nothing is touched.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

# Make `headroom` importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ACTIONS = [
    {"kind": "read", "tool": "read_file", "target": "src/index.ts"},
    {"kind": "shell", "tool": "run_shell", "target": "rm -rf /"},
    {"kind": "deploy", "tool": "deploy", "target": "production"},
]


def _unwrap(result) -> dict:
    """Pull the structured dict out of an MCP tool-call result, across SDK shapes."""
    data = getattr(result, "structuredContent", None)
    if isinstance(data, dict):
        return data.get("result", data)
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}
    return {"raw": str(result)}


async def main() -> None:
    db_path = os.path.join(tempfile.mkdtemp(), "mcp_demo.db")
    env = {
        **os.environ,
        "HEADROOM_DB": db_path,
        "ANTHROPIC_API_KEY": "",
    }  # key-free: rules + fail-safe
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "headroom.mcp_server"], env=env
    )

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        print(f"connected to Headroom MCP server. tools: {tools}\n")

        for a in ACTIONS:
            res = _unwrap(await session.call_tool("submit_action_for_review", a))
            status = res.get("status", "?").upper()
            print(f"  {a['kind']:7} {a['target']:28} -> {status:8} {res.get('reason', '')}")
            if res.get("status") == "pending":
                poll = _unwrap(
                    await session.call_tool("check_review", {"action_id": res["action_id"]})
                )
                print(
                    f"          (action_id={res['action_id']} — check_review: {poll['status']}; "
                    f"approve it on the dashboard to flip this to 'approved')"
                )

    print("\nThat is the whole integration: a host agent asks before it acts; the guard answers.")


if __name__ == "__main__":
    asyncio.run(main())
