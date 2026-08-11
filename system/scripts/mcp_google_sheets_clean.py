#!/usr/bin/env python3
"""
Clean stdio launcher for mcp-google-sheets.

The upstream package prints status logs with print(), which writes to stdout.
MCP stdio uses stdout for protocol frames, so logs must go to stderr.
Known benign startup/request logs are suppressed so Claude does not report
normal MCP chatter as errors.
"""

from __future__ import annotations

import builtins
import logging
import sys
import warnings


warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

_print = builtins.print
_BENIGN_STARTUP_MESSAGES = {
    "Tool filtering disabled. All tools are enabled.",
    "Using service account authentication",
    "Working with Google Drive folder ID: Not specified",
}
_BENIGN_PREFIXES = (
    "Processing request of type ",
)


def _is_benign_log(message: str) -> bool:
    if message in _BENIGN_STARTUP_MESSAGES:
        return True
    return any(message.startswith(prefix) for prefix in _BENIGN_PREFIXES)


class _FilteringStderr:
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def write(self, text):
        stripped = text.strip()
        if stripped and _is_benign_log(stripped):
            return len(text)
        return self._wrapped.write(text)

    def flush(self):
        return self._wrapped.flush()

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


sys.stderr = _FilteringStderr(sys.stderr)


def _print_to_stderr(*args, **kwargs):
    message = " ".join(str(arg) for arg in args)
    if _is_benign_log(message):
        return None

    if kwargs.get("file") is None:
        kwargs["file"] = sys.stderr
    return _print(*args, **kwargs)


builtins.print = _print_to_stderr


def main() -> None:
    from mcp_google_sheets import server

    if "--self-test" in sys.argv:
        _print("mcp-google-sheets clean launcher import ok", file=sys.stderr)
        return

    server.main()


if __name__ == "__main__":
    main()
