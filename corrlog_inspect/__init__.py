"""corrlog-inspect: emit signed ACR correction receipts from Inspect AI evals.

An Inspect extension (`Hooks` subclass) that emits one signed ACR correction
receipt per failing sample. Ships as its own package so it is an extension,
not a core change to Inspect.

The Inspect side is grounded against the real `inspect_ai` API; the signing
call is wired to `corrlog_core`. See README.md for the mapping and scope.
"""
from __future__ import annotations

from .hooks import CorrlogReceiptHook

__all__ = ["CorrlogReceiptHook"]
__version__ = "0.1.0"
