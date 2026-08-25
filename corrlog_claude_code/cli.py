"""corrlog-claude-code — CLI for Claude Code hooks.

Invoked by hooks/hooks.json as an external process. Reads the hook's stdin JSON,
emits a signed correction-log record.

Modes:
  - PreToolUse   : hash the tool input, mint an action id (emit to stderr-free stdout)
  - PostToolUse  : hash the tool result, sign the action record
  - human-flag   : `corrlog human-flag --receipt <id> --reason "..."` to flag wrong

The key lives in $CORRLOG_KEY_PATH (a PEM/raw Ed25519 private key file).
Records append to $CORRLOG_SINK (JSONL path) or ./corrections.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corrlog_core import generate_keypair, record, retract, JsonlSink
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def _load_or_create_key(path: str):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    priv = ed25519.Ed25519PrivateKey.generate()
    if path:
        with open(path, "wb") as f:
            f.write(priv.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
    return priv


def _sink_path() -> str:
    return os.environ.get("CORRLOG_SINK", os.path.join(os.getcwd(), "corrections.jsonl"))


def _key_path() -> str:
    return os.environ.get("CORRLOG_KEY_PATH", os.path.join(os.getcwd(), "corrlog_key.pem"))


def _agent_id() -> str:
    return os.environ.get("CORRLOG_AGENT_ID", "claude-code-agent")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    # Subcommand: human-flag
    if argv and argv[0] == "human-flag":
        p = argparse.ArgumentParser(prog="corrlog human-flag")
        p.add_argument("--receipt", required=True)
        p.add_argument("--reason", required=True)
        p.add_argument("--fix-note")
        args = p.parse_args(argv[1:])
        priv = _load_or_create_key(_key_path())
        sink = JsonlSink(_sink_path())
        # Find the prior record.
        prior = sink.get(args.receipt)
        if prior is None:
            print(json.dumps({"ok": False, "error": f"receipt {args.receipt} not found"}), file=sys.stderr)
            return 1
        corr = retract(
            prior_record=prior, reason=args.reason, trigger="human_flagged",
            agent_id=_agent_id(), private_key=priv, fix_type="replace", fix_note=args.fix_note,
        )
        sink.append(corr)
        print(json.dumps({"ok": True, "correctionId": corr["correctionId"]}))
        return 0

    # Hook mode: read stdin JSON (Claude Code hook contract).
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    hook = data.get("hook_event_name", "")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    priv = _load_or_create_key(_key_path())
    sink = JsonlSink(_sink_path())

    if hook == "PreToolUse":
        rec = record(
            agent_id=_agent_id(), action_type=f"claude.tool.{tool_name}",
            action_args=tool_input if isinstance(tool_input, dict) else {"input": tool_input},
            private_key=priv,
        )
        sink.append(rec)
        # Allow the call; stash the action id in a sidecar file for PostToolUse.
        _sidecar = os.path.join(os.getcwd(), ".corrlog_inflight.json")
        try:
            inflight = json.load(open(_sidecar)) if os.path.exists(_sidecar) else {}
            inflight[tool_name] = rec["correctionId"]
            json.dump(inflight, open(_sidecar, "w"))
        except Exception:
            pass
        print(json.dumps({"continue": True}))

    elif hook == "PostToolUse":
        tool_result = data.get("tool_result", "")
        _sidecar = os.path.join(os.getcwd(), ".corrlog_inflight.json")
        prior_id = None
        try:
            inflight = json.load(open(_sidecar)) if os.path.exists(_sidecar) else {}
            prior_id = inflight.pop(tool_name, None)
            json.dump(inflight, open(_sidecar, "w"))
        except Exception:
            pass
        rec = record(
            agent_id=_agent_id(), action_type=f"claude.tool.{tool_name}",
            action_args=tool_input if isinstance(tool_input, dict) else {"input": tool_input},
            action_result=tool_result, private_key=priv,
        )
        sink.append(rec)
        # Detect error in result -> check_failed correction.
        if isinstance(tool_result, str) and any(
            m in tool_result.lower() for m in ("error", "failed", "exception", "denied")
        ):
            corr = retract(
                prior_record=rec, reason="tool returned error", trigger="check_failed",
                agent_id=_agent_id(), private_key=priv, fix_type="replace",
                fix_note=f"claude tool {tool_name} errored",
            )
            sink.append(corr)
        print(json.dumps({"continue": True}))

    else:
        # Unhandled hook event: no-op, allow.
        print(json.dumps({"continue": True}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
