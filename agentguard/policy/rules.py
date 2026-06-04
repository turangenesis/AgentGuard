"""The deterministic policy ruleset — ordered, first-match-wins (policy-as-data).

Each rule is a small data record: which action kinds it applies to, a regex matched
case-insensitively against the action's ``target`` string, the verdict it yields, and
a human-readable reason. The list order IS the precedence — dangerous patterns are
matched before permissive catch-alls.

Rules deliberately do NOT cover every case. When no rule matches, the guardian falls
through to a single LLM judge call (the ambiguous middle), and if that is unavailable
it defaults to APPROVAL_REQUIRED (fail-safe). See guardian.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..types import ActionKind, Verdict


@dataclass(frozen=True)
class Rule:
    """A single policy rule. ``pattern=None`` means "match any target of these kinds"."""

    id: str
    kinds: tuple[ActionKind, ...]
    pattern: str | None
    verdict: Verdict
    reason: str

    def matches(self, kind: ActionKind, target: str) -> bool:
        if self.kinds and kind not in self.kinds:
            return False
        if self.pattern is None:
            return True
        return re.search(self.pattern, target, re.IGNORECASE) is not None


# Ordered, first-match-wins. ~12 rules.
RULES: list[Rule] = [
    # --- BLOCKED: never execute --------------------------------------------- #
    Rule(
        id="read-secret",
        kinds=(ActionKind.READ,),
        pattern=r"(^|/)\.env($|\.)|\.pem$|\.key$|/?secrets?/|credentials?|id_rsa",
        verdict=Verdict.BLOCKED,
        reason="Reading secret, credential, or key material is blocked.",
    ),
    Rule(
        id="destructive-shell",
        kinds=(ActionKind.SHELL,),
        pattern=r"rm\s+-rf|\bmkfs\b|\bdd\s+if=|:\(\)\s*\{|>\s*/dev/sd|chmod\s+-R\s+777\s+/",
        verdict=Verdict.BLOCKED,
        reason="Destructive shell command (mass delete / disk overwrite / fork bomb) is blocked.",
    ),
    Rule(
        id="push-protected",
        kinds=(ActionKind.GIT,),
        pattern=r"push\b.*\b(main|master)\b|push\b.*(--force|-f\b)|--force\b",
        verdict=Verdict.BLOCKED,
        reason="Pushing to a protected branch or force-pushing is blocked.",
    ),
    # --- APPROVAL_REQUIRED: pause for a human ------------------------------- #
    Rule(
        id="edit-auth",
        kinds=(ActionKind.WRITE,),
        pattern=r"auth|middleware|security|/login|password|token",
        verdict=Verdict.APPROVAL_REQUIRED,
        reason="Editing authentication / security-sensitive code requires approval.",
    ),
    Rule(
        id="privileged-shell",
        kinds=(ActionKind.SHELL,),
        pattern=r"\bsudo\b|curl\b.*\|\s*(sh|bash)|wget\b.*\|\s*(sh|bash)",
        verdict=Verdict.APPROVAL_REQUIRED,
        reason="Privileged (sudo) or pipe-to-shell command requires approval.",
    ),
    Rule(
        id="git-push",
        kinds=(ActionKind.GIT,),
        pattern=r"\bpush\b",
        verdict=Verdict.APPROVAL_REQUIRED,
        reason="Pushing commits to a remote requires approval.",
    ),
    Rule(
        id="create-pr",
        kinds=(ActionKind.CREATE_PR,),
        pattern=None,
        verdict=Verdict.APPROVAL_REQUIRED,
        reason="Opening a pull request requires approval.",
    ),
    Rule(
        id="deploy-prod",
        kinds=(ActionKind.DEPLOY,),
        pattern=r"prod",
        verdict=Verdict.APPROVAL_REQUIRED,
        reason="Deploying to production requires approval.",
    ),
    # --- SAFE: execute immediately ----------------------------------------- #
    Rule(
        id="read-safe",
        kinds=(ActionKind.READ,),
        pattern=None,
        verdict=Verdict.SAFE,
        reason="Reading non-secret source files is safe.",
    ),
    Rule(
        id="list-safe",
        kinds=(ActionKind.LIST,),
        pattern=None,
        verdict=Verdict.SAFE,
        reason="Listing directory contents is safe.",
    ),
    Rule(
        id="write-docs-test",
        kinds=(ActionKind.WRITE,),
        pattern=r"\.(md|txt|rst)$|(^|/)(docs|tests?|__tests__|spec)/|\.(test|spec)\.|readme",
        verdict=Verdict.SAFE,
        reason="Writing documentation or test files is safe.",
    ),
    Rule(
        id="git-local-safe",
        kinds=(ActionKind.GIT,),
        pattern=r"^\s*(status|diff|log|show|add|fetch|pull|branch|checkout|stash|commit)\b",
        verdict=Verdict.SAFE,
        reason="Standard local git operations are safe.",
    ),
]


def match_rules(kind: ActionKind, target: str) -> Rule | None:
    """Return the first rule that matches, or None if the action falls to the LLM judge."""
    for rule in RULES:
        if rule.matches(kind, target):
            return rule
    return None
