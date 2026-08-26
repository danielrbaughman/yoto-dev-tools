"""One-shot loopback HTTP server that receives the OAuth redirect."""

import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

from yoto.domain.errors import ConfigError, OAuthFlowError, OperationTimeout

_SUCCESS_PAGE = b"""<!doctype html><meta charset="utf-8">
<title>yoto login</title>
<body style="font-family: system-ui; margin: 4rem auto; max-width: 30rem;">
<h1>Logged in</h1><p>You can close this tab and return to the terminal.</p>
"""
_FAILURE_PAGE = b"""<!doctype html><meta charset="utf-8">
<title>yoto login</title>
<body style="font-family: system-ui; margin: 4rem auto; max-width: 30rem;">
<h1>Login failed</h1><p>Return to the terminal for details.</p>
"""


class LoopbackCodeReceiver:
    """Implements the CodeReceiver port with http.server on 127.0.0.1."""

    def __init__(self, port: int, *, host: str = "127.0.0.1") -> None:
        self._host = host
        self._port = port
        self._queue: queue.Queue[dict[str, str]] = queue.Queue()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> str:
        results = self._queue

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parts = urlsplit(self.path)
                if parts.path != "/callback":
                    self.send_error(404)
                    return
                params = {
                    key: values[0]
                    for key, values in parse_qs(parts.query).items()
                    if values
                }
                page = _FAILURE_PAGE if "error" in params else _SUCCESS_PAGE
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
                results.put(params)

            def log_message(self, format: str, *args: object) -> None:
                """Silenced: keep the CLI's stderr clean."""

        try:
            self._server = HTTPServer((self._host, self._port), Handler)
            self._port = self._server.server_address[1]  # resolves port 0
        except OSError as exc:
            raise ConfigError(
                f"Cannot listen on {self._host}:{self._port} ({exc.strerror}). "
                "Pass --port (and register the matching redirect URI at "
                "https://dashboard.yoto.dev/)."
            ) from exc
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="yoto-login", daemon=True
        )
        self._thread.start()
        return f"http://{self._host}:{self._port}/callback"

    def wait_for_code(self, *, expected_state: str, timeout: float) -> str:
        try:
            params = self._queue.get(timeout=timeout)
        except queue.Empty:
            raise OperationTimeout(
                f"No login callback within {timeout:.0f}s. "
                "If the browser showed an error, check that the redirect URI "
                "is registered for your client id."
            ) from None
        if "error" in params:
            description = params.get("error_description", "")
            raise OAuthFlowError(
                f"Login failed: {params['error']}"
                + (f" — {description}" if description else ""),
                error=params["error"],
            )
        if params.get("state") != expected_state:
            raise OAuthFlowError(
                "Login failed: state mismatch (possible CSRF); try again."
            )
        code = params.get("code")
        if not code:
            raise OAuthFlowError("Login failed: callback had no authorization code.")
        return code

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
