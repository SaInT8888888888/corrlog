"""corrlog-claude-code — plugin surface. The actual hook logic is in cli.py."""

from __future__ import annotations


def is_available() -> bool:
    """Claude Code hooks are external processes — always 'available' if python is."""
    return True
