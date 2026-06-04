"""AgentGuard — a human-in-the-loop execution firewall for AI coding agents.

A worker LLM agent proposes tool calls; a guardian (deterministic rules + LLM
judgment) classifies each as safe / approval-required / blocked; risky actions
pause the LangGraph run via ``interrupt()`` and wait for human approval; every
decision is written to an append-only audit log.
"""

__version__ = "0.1.0"
