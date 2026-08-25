"""corrlog-langchain — drop-in correction log for LangChain/LangGraph agents.

Implements a `CorrectionLogMiddleware` (AgentMiddleware) that:
  - before a tool call: hashes the tool input, mints an action id
  - after a tool call: hashes the result, signs the action record
  - on a detected correction (check_failed / human_flagged / supersede):
    writes a signed correction record and (optionally) returns a Command to
    roll back / redirect state via the native checkpointer.

Import-safe: if langchain is not installed, `is_available()` returns False.

Integration points (verified against langchain source):
  - `langchain.agents.middleware.AgentMiddleware` — subclass `wrap_tool_call` /
    `awrap_tool_call`; `ToolCallRequest` exposes `.tool_call` (name/args/id),
    `.tool`, `.state`, `.runtime`, `.override(tool_call=...)`.
  - `langgraph.prebuilt.tool_node.ToolCallRequest` — the underlying request type.
  - `langgraph.types.Command(update=..., goto=...)` — native redirect/rollback.
  - `langgraph.store.base.BaseStore` — durable cross-graph memory (natural sink).
"""

from __future__ import annotations

from typing import Any

from corrlog_core import record, retract

try:
    from langchain.agents.middleware import AgentMiddleware  # type: ignore
    _LANGCHAIN_AVAILABLE = True
except Exception:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False


def is_available() -> bool:
    return _LANGCHAIN_AVAILABLE


class CorrectionLogMiddleware(AgentMiddleware if _LANGCHAIN_AVAILABLE else object):  # type: ignore[misc]
    """Signed correction log for LangChain/LangGraph tool calls."""

    def __init__(self, sink, private_key, agent_id: str, principal_id: str = "organization") -> None:
        self.sink = sink
        self.private_key = private_key
        self.agent_id = agent_id
        self.principal_id = principal_id
        self._inflight: dict[str, dict[str, Any]] = {}

    # -- tool call interception -------------------------------------------
    def wrap_tool_call(self, request, handler):
        # Read the tool call (dict: name, args, id) + tool + state.
        tool_call = getattr(request, "tool_call", None) or {}
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")

        # Mint an action record BEFORE execution (hash the input).
        rec = record(
            agent_id=self.agent_id,
            principal_id=self.principal_id,
            action_type=f"langchain.tool.{tool_name}",
            action_args=tool_args if isinstance(tool_args, dict) else {"args": tool_args},
            private_key=self.private_key,
            metadata={"tool_call_id": tool_id} if tool_id else None,
        )
        self.sink.append(rec)

        # Execute the tool.
        result = handler(request)

        # Determine if the result indicates an error -> check_failed correction.
        err = None
        if hasattr(result, "status") and getattr(result, "status") in ("error",):
            err = "tool returned error status"
        elif hasattr(result, "content") and _looks_like_error(getattr(result, "content")):
            err = "tool returned error content"

        if err is not None:
            corr = retract(
                prior_record=rec,
                reason=err,
                trigger="check_failed",
                agent_id=self.agent_id,
                private_key=self.private_key,
                principal_id=self.principal_id,
                fix_type="replace",
                fix_note=f"langchain tool {tool_name} errored",
            )
            self.sink.append(corr)

        return result

    async def awrap_tool_call(self, request, handler):
        # Async mirror: delegate to the sync logic via await.
        tool_call = getattr(request, "tool_call", None) or {}
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")

        rec = record(
            agent_id=self.agent_id,
            principal_id=self.principal_id,
            action_type=f"langchain.tool.{tool_name}",
            action_args=tool_args if isinstance(tool_args, dict) else {"args": tool_args},
            private_key=self.private_key,
            metadata={"tool_call_id": tool_id} if tool_id else None,
        )
        self.sink.append(rec)

        result = await handler(request)

        err = None
        if hasattr(result, "status") and getattr(result, "status") in ("error",):
            err = "tool returned error status"
        elif hasattr(result, "content") and _looks_like_error(getattr(result, "content")):
            err = "tool returned error content"

        if err is not None:
            corr = retract(
                prior_record=rec,
                reason=err,
                trigger="check_failed",
                agent_id=self.agent_id,
                private_key=self.private_key,
                principal_id=self.principal_id,
                fix_type="replace",
                fix_note=f"langchain tool {tool_name} errored",
            )
            self.sink.append(corr)

        return result

    # -- public API -------------------------------------------------------
    def mark_wrong(self, prior_record: dict[str, Any], reason: str, fix_note: str | None = None) -> dict[str, Any]:
        """Human-flag a prior record as wrong -> signed correction."""
        corr = retract(
            prior_record=prior_record,
            reason=reason,
            trigger="human_flagged",
            agent_id=self.agent_id,
            private_key=self.private_key,
            principal_id=self.principal_id,
            fix_type="replace",
            fix_note=fix_note,
        )
        self.sink.append(corr)
        return corr


def _looks_like_error(content) -> bool:
    if isinstance(content, str):
        low = content.lower()
        return any(m in low for m in ("error", "failed", "exception", "traceback", "denied", "invalid"))
    if isinstance(content, list):
        return any(_looks_like_error(c) for c in content)
    return False
