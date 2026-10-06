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


# Upstream builds one googleapiclient service at startup and reuses its httplib2
# keep-alive connection for the whole session. After a few idle minutes Google,
# an antivirus or the router drops that TCP connection; on Windows the next send
# fails with WinError 10053. httplib2 re-raises that error without closing the
# dead socket, so every following call fails the same way until the MCP server
# is restarted.
IDLE_SECONDS = 30
GET_RETRIES = 3


def _harden_google_http() -> None:
    import threading
    import time

    import httplib2
    from googleapiclient import http as gapi_http

    original_request = httplib2.Http.request
    lock = threading.Lock()

    def _close_connections(client) -> None:
        for conn in list(client.connections.values()):
            try:
                conn.close()
            except Exception:
                pass

    def request(self, *args, **kwargs):
        with lock:
            last = getattr(self, "_hypercrm_last_request", None)
            if last is not None and time.monotonic() - last > IDLE_SECONDS:
                # Never send on a socket that sat idle: reconnect instead.
                _close_connections(self)
            try:
                return original_request(self, *args, **kwargs)
            except (ConnectionError, OSError):
                # Drop the dead socket so the retry or the next call reconnects.
                _close_connections(self)
                raise
            finally:
                self._hypercrm_last_request = time.monotonic()

    httplib2.Http.request = request

    original_execute = gapi_http.HttpRequest.execute

    def execute(self, http=None, num_retries=0):
        # Reads are safe to repeat; writes are not retried to avoid duplicates.
        if num_retries == 0 and self.method == "GET":
            num_retries = GET_RETRIES
        return original_execute(self, http=http, num_retries=num_retries)

    gapi_http.HttpRequest.execute = execute


def main() -> None:
    _harden_google_http()
    from mcp_google_sheets import server

    if "--self-test" in sys.argv:
        _print("mcp-google-sheets clean launcher import ok", file=sys.stderr)
        return

    server.main()


if __name__ == "__main__":
    main()
