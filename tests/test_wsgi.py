"""The app behind a WSGI server (cPanel/Passenger via a2wsgi), background jobs included."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from wsgiref.util import setup_testing_defaults

import pytest
from a2wsgi import ASGIMiddleware
from cryptography.fernet import Fernet

from einvoice_bridge.profile import SellerProfile
from einvoice_bridge.web.app import create_app
from einvoice_bridge.web.wsgi import fork_safe_wsgi

from .conftest import FIXTURES
from .test_web import WEBHOOK_SECRET, gateway, mailer, signed, store  # noqa: F401 (shared fixtures)


def call(app, method: str, path: str, body: bytes = b"", headers: dict | None = None, scheme: str = "http"):
    environ: dict = {"wsgi.url_scheme": scheme}
    setup_testing_defaults(environ)
    environ.update(REQUEST_METHOD=method, PATH_INFO=path, CONTENT_LENGTH=str(len(body)))
    environ["wsgi.input"] = io.BytesIO(body)
    for key, value in (headers or {}).items():
        name = key.upper().replace("-", "_")
        environ[name if name == "CONTENT_TYPE" else f"HTTP_{name}"] = value
    status = {}

    def start_response(s, h, exc_info=None):
        status["line"] = s
        status["headers"] = dict(h)

    content = b"".join(app(environ, start_response))
    call.last_headers = status["headers"]
    return status["line"], content


def test_pages_and_webhook_background_job_under_wsgi(store, gateway, mailer):
    profile = SellerProfile.load(FIXTURES / "seller_profile.toml")
    account = store.create_account(profile, "rk", WEBHOOK_SECRET, send_to_customer=True, plan="business")
    app = ASGIMiddleware(create_app(store=store, gateway_factory=lambda a: gateway, mailer=mailer, base_url="https://x.test"))

    status, body = call(app, "GET", "/")
    assert status.startswith("200") and "E-Rechnungsbote".encode() in body
    status, body = call(app, "GET", "/health")
    assert status.startswith("200") and b'"ok":true' in body

    event = {"type": "invoice.paid", "data": {"object": {"id": "in_paid", "collection_method": "charge_automatically"}}}
    payload, headers = signed(event)
    headers["content-type"] = "application/json"
    status, _ = call(app, "POST", f"/stripe/webhook/{account.id}", payload, headers)
    assert status.startswith("200")

    # The conversion runs as a background task after the response was sent.
    deadline = time.time() + 20
    while time.time() < deadline:
        doc = store.document(account.id, "in_paid")
        if doc and doc.status == "generated" and doc.delivered_to:
            break
        time.sleep(0.1)
    assert doc and doc.status == "generated"
    assert mailer.sent and mailer.sent[0]["To"] == "ap@kunde.de"


def test_force_https_follows_passenger_scheme(store, gateway, mailer, monkeypatch):
    # Passenger sets wsgi.url_scheme from Apache's HTTPS flag; a2wsgi passes it on.
    monkeypatch.setenv("EINVOICE_FORCE_HTTPS", "1")
    app = ASGIMiddleware(create_app(store=store, gateway_factory=lambda a: gateway, mailer=mailer, base_url="https://x.test"))

    status, _ = call(app, "GET", "/preise", scheme="http")
    assert status.startswith("301") and call.last_headers["location"] == "https://x.test/preise"
    status, _ = call(app, "GET", "/preise", scheme="https")
    assert status.startswith("200")


FORKED_WORKER = """
import io, os, signal, sys
from wsgiref.util import setup_testing_defaults
from a2wsgi import ASGIMiddleware
from einvoice_bridge.web.app import create_app
from einvoice_bridge.web.wsgi import fork_safe_wsgi

wrap = ASGIMiddleware if sys.argv[1] == "plain" else fork_safe_wsgi
app = wrap(create_app())

def health():
    environ = {}
    setup_testing_defaults(environ)
    environ.update(REQUEST_METHOD="GET", PATH_INFO="/health", CONTENT_LENGTH="0", **{"wsgi.input": io.BytesIO()})
    status = []
    body = b"".join(app(environ, lambda s, h, e=None: status.append(s)))
    return status[0].startswith("200") and b'"ok":true' in body

assert health()  # parent, as a preloading server would after import
pid = os.fork()
if pid == 0:
    signal.alarm(5)
    os._exit(0 if health() else 2)
_, wait_status = os.waitpid(pid, 0)
sys.exit(os.waitstatus_to_exitcode(wait_status))
"""


def run_forked_worker(tmp_path, mode: str) -> int:
    # A fresh interpreter: state from other tests (e.g. a started Saxon VM) must not leak into the fork.
    env = dict(
        os.environ,
        EINVOICE_DATA_DIR=str(tmp_path),
        EINVOICE_SECRET_KEY=Fernet.generate_key().decode(),
        EINVOICE_BASE_URL="https://x.test",
    )
    return subprocess.run([sys.executable, "-c", FORKED_WORKER, mode], env=env, timeout=60).returncode


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")
def test_request_in_forked_worker_does_not_hang(tmp_path):
    # LiteSpeed imports the app, then forks workers. a2wsgi's loop thread does
    # not survive the fork, so a middleware built at import hangs every request.
    assert run_forked_worker(tmp_path, "plain") != 0
    assert run_forked_worker(tmp_path, "fork_safe") == 0


def test_litespeed_https_flag_counts_as_https(store, gateway, mailer, monkeypatch):
    # LiteSpeed sets HTTPS=on; without honouring it the https redirect would loop.
    monkeypatch.setenv("EINVOICE_FORCE_HTTPS", "1")
    app = fork_safe_wsgi(create_app(store=store, gateway_factory=lambda a: gateway, mailer=mailer, base_url="https://x.test"))

    status, _ = call(app, "GET", "/preise", headers={})
    assert status.startswith("301")
    environ_https = {"HTTPS": "on"}
    status, _ = call_with_environ(app, "GET", "/preise", environ_https)
    assert status.startswith("200")


def call_with_environ(app, method: str, path: str, extra: dict):
    def wrapped(environ, start_response):
        environ.update(extra)
        return app(environ, start_response)

    return call(wrapped, method, path)
