"""WSGI entry for shared hosting (cPanel: LiteSpeed LSAPI or Phusion Passenger).

a2wsgi runs the ASGI app on an event loop in a background thread, started when
the middleware is created. LiteSpeed imports the app once and then forks worker
processes; a thread does not survive fork, so a middleware built at import time
leaves every worker waiting forever on a loop nobody runs (503 once all workers
are stuck). The middleware is therefore built lazily, once per process.
"""

from __future__ import annotations

import os
import threading

from a2wsgi import ASGIMiddleware


def fork_safe_wsgi(asgi_app):
    lock = threading.Lock()
    state: dict = {"pid": None, "app": None}

    def application(environ, start_response):
        pid = os.getpid()
        if state["pid"] != pid:
            with lock:
                if state["pid"] != pid:
                    state["app"] = ASGIMiddleware(asgi_app)
                    state["pid"] = pid
        # LiteSpeed flags TLS with HTTPS=on but may leave wsgi.url_scheme at http.
        if environ.get("HTTPS", "").lower() in ("on", "1"):
            environ["wsgi.url_scheme"] = "https"
        return state["app"](environ, start_response)

    return application
