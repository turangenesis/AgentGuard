"""Worker tools and the mapping from a LangChain tool call to a ProposedAction.

Design (per the plan): ``read_file`` / ``list_dir`` return REAL content from the
bundled ``sample-target/`` repo (reads are safe, so the worker genuinely inspects
code). ``write_file`` / ``run_shell`` / ``git`` / ``create_pr`` / ``deploy`` are
SIMULATED — they return canned results and never touch the system.

The real read tools are sandboxed to ``sample-target/`` as defense-in-depth: even
if the guardian were to wave a read through, it can only ever read the sample repo.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from .types import ActionKind, ProposedAction

# Repo root -> the bundled target the worker operates on.
SAMPLE_TARGET = (Path(__file__).resolve().parent.parent / "sample-target").resolve()

_MAX_READ_CHARS = 4000


def _resolve_in_target(path: str) -> Path | None:
    """Resolve ``path`` inside SAMPLE_TARGET, or return None if it escapes the sandbox."""
    cleaned = path.strip()
    # Accept paths written either relative to the repo root ("sample-target/x")
    # or relative to the target itself ("x").
    if cleaned.startswith("sample-target/"):
        cleaned = cleaned[len("sample-target/") :]
    candidate = (SAMPLE_TARGET / cleaned).resolve()
    if candidate != SAMPLE_TARGET and SAMPLE_TARGET not in candidate.parents:
        return None
    return candidate


# --------------------------------------------------------------------------- #
# REAL tools (reads only) — sandboxed to sample-target/
# --------------------------------------------------------------------------- #
@tool
def read_file(path: str) -> str:
    """Read a text file from the target repository and return its contents.

    Args:
        path: File path relative to the target repo root (e.g. "src/index.ts").
    """
    resolved = _resolve_in_target(path)
    if resolved is None:
        return f"ERROR: path '{path}' is outside the target repository."
    if not resolved.is_file():
        return f"ERROR: no such file: {path}"
    text = resolved.read_text(encoding="utf-8", errors="replace")
    if len(text) > _MAX_READ_CHARS:
        text = text[:_MAX_READ_CHARS] + "\n... [truncated]"
    return text


@tool
def list_dir(path: str = ".") -> str:
    """List the entries of a directory in the target repository.

    Args:
        path: Directory path relative to the target repo root (e.g. "src").
    """
    resolved = _resolve_in_target(path)
    if resolved is None:
        return f"ERROR: path '{path}' is outside the target repository."
    if not resolved.is_dir():
        return f"ERROR: no such directory: {path}"
    entries = sorted(f"{e.name}/" if e.is_dir() else e.name for e in resolved.iterdir())
    return "\n".join(entries) if entries else "(empty)"


# --------------------------------------------------------------------------- #
# SIMULATED tools (side-effecting) — never actually run
# --------------------------------------------------------------------------- #
@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in the target repository (simulated).

    Args:
        path: File path relative to the target repo root.
        content: The full new file contents.
    """
    return f"[simulated] wrote {len(content)} bytes to {path}"


@tool
def run_shell(command: str) -> str:
    """Run a shell command in the target repository (simulated).

    Args:
        command: The shell command line to execute.
    """
    return f"[simulated] $ {command}\n(exit 0)"


@tool
def git(command: str) -> str:
    """Run a git command in the target repository (simulated).

    Args:
        command: The git subcommand and arguments, e.g. "push origin main".
    """
    return f"[simulated] git {command}\nok"


@tool
def create_pr(title: str, body: str = "") -> str:
    """Open a pull request for the current changes (simulated).

    Args:
        title: The pull request title.
        body: The pull request description.
    """
    return f"[simulated] opened pull request: {title} (#42)"


@tool
def deploy(target: str) -> str:
    """Deploy the service to an environment (simulated).

    Args:
        target: The deployment environment, e.g. "staging" or "production".
    """
    return f"[simulated] deployed to {target}"


# Tools exposed to the worker LLM, and a name -> callable map for execution.
TOOLS = [read_file, list_dir, write_file, run_shell, git, create_pr, deploy]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

# Tool name -> (ActionKind, name of the arg used as the rule/display "target").
_TOOL_KIND = {
    "read_file": (ActionKind.READ, "path"),
    "list_dir": (ActionKind.LIST, "path"),
    "write_file": (ActionKind.WRITE, "path"),
    "run_shell": (ActionKind.SHELL, "command"),
    "git": (ActionKind.GIT, "command"),
    "create_pr": (ActionKind.CREATE_PR, "title"),
    "deploy": (ActionKind.DEPLOY, "target"),
}


def action_from_tool_call(tool_call: dict) -> ProposedAction:
    """Convert a LangChain tool call ``{name, args, id}`` into a ProposedAction."""
    name = tool_call["name"]
    args = tool_call.get("args", {}) or {}
    kind, target_key = _TOOL_KIND.get(name, (ActionKind.SHELL, "command"))
    target = str(args.get(target_key, "")).strip()
    return ProposedAction(
        kind=kind,
        tool=name,
        args=args,
        target=target,
        tool_call_id=tool_call.get("id"),
    )
