"""corrlog-autogen — drop-in correction log for AutoGen agents.

AutoGen has NO merged tool-call middleware as of this build (verified against the
cloned source). The seams we need — `BaseTool.run_json()` / `Workbench.call_tool()` —
are exactly what the still-open proposals target (#7405 GuardrailProvider, #7353 AAR
receipts). So this adapter wraps `run_json` rather than relying on a shipped hook.

Import-safe: if autogen is not installed, `is_available()` returns False and the
wrapper class still imports.

Usage (when autogen is installed):
    from corrlog_autogen import GuardedTool
    tool = GuardedTool(my_autogen_tool, sink, private_key, agent_id="agent-1")
"""

from __future__ import annotations

from typing import Any

from corrlog_core import record, retract

try:
    from autogen_core.tools import BaseTool  # type: ignore
    _AUTOGEN_AVAILABLE = True
except Exception:  # pragma: no cover
    _AUTOGEN_AVAILABLE = False


def is_available() -> bool:
    return _AUTOGEN_AVAILABLE


class GuardedTool:
    """Wraps an AutoGen tool, adding before/after correction-logging around `run_json`.

    Structured to match the proposed GuardrailProvider signature from #7405, so it
    upgrades cleanly when that lands upstream.
    """

    def __init__(self, tool, sink, private_key, agent_id: str, principal_id: str = "organization") -> None:
        self._tool = tool
        self.sink = sink
        self.private_key = private_key
        self.agent_id = agent_id
        self.principal_id = principal_id

    def __getattr__(self, name: str):
        # Delegate everything else to the wrapped tool.
        return getattr(self._tool, name)

    @property
    def name(self) -> str:
        return getattr(self._tool, "name", "unknown_tool")

    async def run_json(self, args, cancellation_token=None, call_id=None):
        tool_name = self.name
        rec = record(
            agent_id=self.agent_id,
            principal_id=self.principal_id,
            action_type=f"autogen.tool.{tool_name}",
            action_args=args if isinstance(args, dict) else {"args": args},
            private_key=self.private_key,
            metadata={"call_id": call_id} if call_id else None,
        )
        self.sink.append(rec)

        try:
            result = await self._tool.run_json(args, cancellation_token, call_id)
        except Exception as e:  # noqa: BLE001
            corr = retract(
                prior_record=rec,
                reason=f"tool raised: {e}",
                trigger="check_failed",
                agent_id=self.agent_id,
                private_key=self.private_key,
                principal_id=self.principal_id,
                fix_type="replace",
                fix_note=f"autogen tool {tool_name} raised",
            )
            self.sink.append(corr)
            raise

        # Result-level error detection (best-effort, framework-dependent shape).
        if isinstance(result, dict) and result.get("error"):
            corr = retract(
                prior_record=rec,
                reason=str(result["error"]),
                trigger="check_failed",
                agent_id=self.agent_id,
                private_key=self.private_key,
                principal_id=self.principal_id,
                fix_type="replace",
                fix_note=f"autogen tool {tool_name} errored",
            )
            self.sink.append(corr)

        return result

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
