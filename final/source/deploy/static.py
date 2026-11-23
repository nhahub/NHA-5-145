"""Loopback-only built Panel server for local rehearsal. Production uses Caddy."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, directory=str(Path(__file__).resolve().parents[1] / "panel/dist"), **kwargs
        )

    def do_GET(self):
        path = urlsplit(self.path).path
        if path != "/" and not path.startswith("/assets/"):
            self.send_error(404)
            return
        super().do_GET()

    def log_message(self, *_args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 4100), Handler).serve_forever()
