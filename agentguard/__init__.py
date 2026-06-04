"""AgentGuard — a human-in-the-loop execution firewall for AI coding agents.

A worker LLM agent proposes tool calls; a guardian (deterministic rules + LLM
judgment) classifies each as safe / approval-required / blocked; risky actions
pause the LangGraph run via ``interrupt()`` and wait for human approval; every
decision is written to an append-only audit log.
"""

# Load .env on import so `uvicorn agentguard.api:app` and the eval pick up
# ANTHROPIC_API_KEY / LANGSMITH_* without an explicit export. Never overrides a
# variable already set in the real environment; a no-op if there's no .env (CI).
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # python-dotenv is a declared dep; degrade gracefully if absent
    pass

__version__ = "0.1.0"
