"""corrlog-crewai — drop-in correction log for CrewAI agents.

Registers CrewAI tool-call hooks that (a) mint an action id + hash the tool
input before every tool call, (b) hash the result after, and (c) write a signed
correction record when a correction is detected.

Import-safe: if CrewAI is not installed, importing this module does nothing
and `is_available()` returns False. When installed, call `install(sink)`.

Correction triggers covered by CrewAI hooks:
  - check_failed   -> a guardrail/policy rejects the result (or a hook blocks it)
  - human_flagged  -> `request_human_input()` path / a human marks output wrong
  - supersede      -> a later write on the same key replaces an earlier one
"""

from __future__ import annotations

from typing import Any

from corrlog_core import record, retract

try:
    from crewai.hooks import (
        register_before_tool_call_hook,
        register_after_tool_call_hook,
    )  # type: ignore
    _CREWAI_AVAILABLE = True
except Exception:  # pragma: no cover - crewai not installed in CI
    _CREWAI_AVAILABLE = False


def is_available() -> bool:
    return _CREWAI_AVAILABLE


class CrewAICorrectionLog:
    """Wraps a corrlog sink; holds the signing key; tracks in-flight actions."""

    def __init__(self, sink, private_key, agent_id: str, principal_id: str = "organization") -> None:
        self.sink = sink
        self.private_key = private_key
        self.agent_id = agent_id
        self.principal_id = principal_id
        # action_id -> action record (so the after-hook can supersede the before-record)
        self._inflight: dict[str, dict[str, Any]] = {}

    # -- hooks -------------------------------------------------------------
    def _before(self, ctx) -> bool | None:
        """Hash the tool input, mint an action id, store the action record."""
        try:
            tool_name = ctx.tool_name
            tool_input = ctx.tool_input
        except AttributeError:
            return None  # not a tool-call context; skip
        rec = record(
            agent_id=self.agent_id,
            principal_id=self.principal_id,
            action_type=f"crewai.tool.{tool_name}",
            action_args=tool_input if isinstance(tool_input, dict) else {"input": tool_input},
            private_key=self.private_key,
        )
        self._inflight[rec["correctionId"]] = rec
        self.sink.append(rec)
        # Stash the action id onto the context if it supports it (best-effort).
        try:
            ctx.action_id = rec["correctionId"]
        except Exception:
            pass
        return None  # allow the call

    def _after(self, ctx) -> str | None:
        """Hash the result. If a correction is flagged, write a signed retract."""
        try:
            tool_name = ctx.tool_name
            tool_result = ctx.tool_result
        except AttributeError:
            return None

        # Find the in-flight action record.
        action_id = getattr(ctx, "action_id", None)
        prior = self._inflight.pop(action_id, None) if action_id else None

        # If a result-level guardrail flagged an error, write a check_failed correction.
        error = getattr(ctx, "error", None) or (
            tool_result if isinstance(tool_result, dict) and tool_result.get("error") else None
        )
        if error is not None:
            reason = str(error)
            if prior is not None:
                corr = retract(
                    prior_record=prior,
                    reason=reason,
                    trigger="check_failed",
                    agent_id=self.agent_id,
                    private_key=self.private_key,
                    principal_id=self.principal_id,
                    fix_type="replace",
                    fix_note=f"crewai tool {tool_name} errored: {reason}",
                )
                self.sink.append(corr)
        return None  # never replace the result from the adapter itself

    # -- public API --------------------------------------------------------
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


def install(log: CrewAICorrectionLog) -> None:
    """Register the global hooks. No-op if CrewAI is unavailable."""
    if not _CREWAI_AVAILABLE:
        return
    register_before_tool_call_hook(log._before)
    register_after_tool_call_hook(log._after)
