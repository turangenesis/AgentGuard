"""Core data models shared across the guardian, graph, tools, and API.

Kept dependency-free (only Pydantic + stdlib) so any module can import it without
pulling in LangGraph or the LLM client.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class ActionKind(StrEnum):
    """The category of side effect a proposed tool call would have."""

    READ = "read"  # read a file (real, against sample-target/)
    LIST = "list"  # list a directory (real)
    WRITE = "write"  # write/edit a file (simulated)
    SHELL = "shell"  # run a shell command (simulated)
    GIT = "git"  # run a git command (simulated)
    CREATE_PR = "create_pr"  # open a pull request (simulated)
    DEPLOY = "deploy"  # deploy to an environment (simulated)


class Verdict(StrEnum):
    """The guardian's classification of a proposed action."""

    SAFE = "SAFE"  # execute immediately
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"  # pause and wait for a human
    BLOCKED = "BLOCKED"  # deny outright, never execute


class DecisionSource(StrEnum):
    """Where a verdict came from — for transparency in the audit log."""

    RULE = "rule"  # a deterministic rule matched first
    LLM = "llm"  # the LLM judge decided the ambiguous middle
    FAIL_SAFE = "fail-safe"  # no rule, no confident judgment -> default to review


class ProposedAction(BaseModel):
    """A single tool call the worker wants to make, awaiting classification."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: ActionKind
    tool: str
    args: dict = Field(default_factory=dict)
    # A normalized, human-readable string the rules match against and the UI shows
    # (a path for file ops, the command for shell/git, the env for deploy).
    target: str = ""
    tool_call_id: str | None = None

    def summary(self) -> str:
        return f"{self.kind.value}: {self.target}".strip()


class GuardianDecision(BaseModel):
    """The guardian's verdict on a proposed action, with its reasoning."""

    verdict: Verdict
    reason: str
    rule_id: str | None = None
    source: DecisionSource = DecisionSource.RULE
