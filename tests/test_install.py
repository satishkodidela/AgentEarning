"""Stripe App install flow: OAuth, onboarding, Connect webhook, uninstall."""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from einvoice_bridge.stripe_oauth import OAuthError, StripeOAuth
from einvoice_bridge.web.app import create_app
from einvoice_bridge.web.forms import iban_valid, parse_profile

from .test_web import gateway, mailer, signed, store  # noqa: F401 (shared fixtures)

CONNECT_SECRET = "whsec_connect"
APP_SECRET = "sk_test_app"
INSTALL_LINK = "https://marketplace.stripe.com/oauth/v2/chnlink_123/authorize?client_id=ca_test"

PROFILE_FORM = {
    "name": "Muster Software GmbH",
    "line1": "Invalidenstraße 1",
    "postcode": "10115",
    "city": "Berlin",
    "country_code": "DE",
    "vat_id": "DE123456789",
    "tax_number": "",
    "contact_name": "Buchhaltung",
    "contact_phone": "+49 30 1234567",
    "contact_email": "buchhaltung@muster.de",
    "iban": "DE02 1203 0000 0000 2020 51",
}


class FakeStripeOAuthServer:
    """Plays https://api.stripe.com/v1/oauth/token."""

    def __init__(self):
        self.requests = []
        self.refresh_counter = 0
        self.revoked = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        self.requests.append((request.headers.get("authorization"), form))
        grant = form["grant_type"][0]
        if grant == "authorization_code":
            if form["code"][0] != "ac_good":
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "bad code"})
            return httpx.Response(200, json=self._tokens("1"))
        if self.revoked:
            return httpx.Response(400, json={"error": "invalid_grant", "error_description": "revoked"})
        self.refresh_counter += 1
        return httpx.Response(200, json=self._tokens(str(self.refresh_counter + 1)))

    @staticmethod
    def _tokens(n: str) -> dict:
        return {
            "access_token": f"sk_test_access_{n}",
            "refresh_token": f"rt_{n}",
            "stripe_user_id": "acct_seller",
            "livemode": False,
            "scope": "stripe_apps",
            "token_type": "bearer",
        }


@pytest.fixture
def server():
    return FakeStripeOAuthServer()


@pytest.fixture
def oauth(server):
    return StripeOAuth(
        APP_SECRET,
        "https://example.test/stripe/oauth/callback",
        install_link=INSTALL_LINK,
        http=httpx.Client(transport=httpx.MockTransport(server)),
    )


@pytest.fixture
def app_client(store, gateway, mailer, oauth):
    app = create_app(
        store=store,
        gateway_factory=lambda account: gateway,
        mailer=mailer,
        base_url="https://example.test",
        oauth=oauth,
        connect_webhook_secret=CONNECT_SECRET,
    )
    return TestClient(app, base_url="https://example.test", follow_redirects=False)


def install(client) -> str:
    start = client.get("/stripe/install")
    assert start.status_code == 303
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    return client.get(f"/stripe/oauth/callback?code=ac_good&state={state}")


def test_install_link_carries_state_and_redirect_uri(app_client):
    response = app_client.get("/stripe/install")
    url = urlparse(response.headers["location"])
    query = parse_qs(url.query)
    assert url.netloc == "marketplace.stripe.com" and url.path.endswith("/chnlink_123/authorize")
    assert query["client_id"] == ["ca_test"]
    assert query["redirect_uri"] == ["https://example.test/stripe/oauth/callback"]
    assert response.cookies.get("oauth_state") == query["state"][0]


def test_callback_rejects_forged_state(app_client, store):
    app_client.get("/stripe/install")
    response = app_client.get("/stripe/oauth/callback?code=ac_good&state=forged")
    assert response.status_code == 400
    assert store.account_by_stripe_id("acct_seller", False) is None


def test_full_install_onboarding_and_backfill(app_client, store, server, mailer):
    response = install(app_client)
    assert response.status_code == 303 and response.headers["location"] == "/konto/einrichten"
    auth, form = server.requests[0]
    assert form == {"grant_type": ["authorization_code"], "code": ["ac_good"]}
    assert auth.startswith("Basic ")  # app secret key as basic-auth user

    account = store.account_by_stripe_id("acct_seller", False)
    assert account.status == "onboarding" and account.profile is None
    assert account.access_token == "sk_test_access_1"
    raw = store.db.execute("SELECT access_token, refresh_token FROM accounts").fetchone()
    assert "sk_test_access_1" not in raw[0] and "rt_1" not in raw[1]  # encrypted

    assert app_client.get("/konto").headers["location"] == "/konto/einrichten"
    page = app_client.get("/konto/einrichten")
    assert page.status_code == 200 and "Firmendaten" in page.text

    bad = app_client.post("/konto/einrichten", data={**PROFILE_FORM, "iban": "DE00123"})
    assert bad.status_code == 422 and "IBAN ist ungültig" in bad.text

    ok = app_client.post("/konto/einrichten", data=PROFILE_FORM)
    assert ok.headers["location"] == "/konto?hinweis=eingerichtet"
    account = store.account(account.id)
    assert account.is_active and account.profile.iban == "DE02120300000000202051"

    # first-run backfill converted recent invoices without e-mailing anyone
    docs = {d.stripe_invoice_id: d for d in store.documents(account.id)}
    assert docs["in_paid"].status == "generated" and docs["in_open"].status == "generated"
    assert mailer.sent == []

    dashboard = app_client.get("/konto")
    assert "Mit Stripe verbunden" in dashboard.text and "MUSTER-0001" in dashboard.text
    pdf = app_client.get("/konto/dokumente/in_paid/zugferd.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")


def test_marketplace_install_without_state_is_accepted(app_client, store):
    response = app_client.get("/stripe/oauth/callback?code=ac_good")
    assert response.status_code == 303
    assert store.account_by_stripe_id("acct_seller", False) is not None


def test_cancelled_install(app_client):
    response = app_client.get("/stripe/oauth/callback?error=access_denied&error_description=Abgebrochen")
    assert response.status_code == 400 and "Abgebrochen" in response.text


def test_bad_code_is_reported(app_client, store):
    response = app_client.get("/stripe/oauth/callback?code=ac_bad")
    assert response.status_code == 400
    assert store.account_by_stripe_id("acct_seller", False) is None


def test_sign_in_again_reuses_account(app_client, store):
    install(app_client)
    first = store.account_by_stripe_id("acct_seller", False)
    app_client.post("/konto/einrichten", data=PROFILE_FORM)
    app_client.post("/abmelden")
    assert app_client.get("/konto").headers["location"] == "/anmelden"
    response = install(app_client)
    assert response.headers["location"] == "/konto"
    assert store.account_by_stripe_id("acct_seller", False).id == first.id


def connect_event(event_type: str, obj: dict, account: str = "acct_seller") -> dict:
    return {"type": event_type, "account": account, "livemode": False, "data": {"object": obj}}


def test_connect_webhook_converts_invoices_of_installed_account(app_client, store, mailer, gateway):
    gateway.recent_invoices = lambda limit: []  # no first-run backfill here
    install(app_client)
    app_client.post("/konto/einrichten", data={**PROFILE_FORM, "send_to_customer": "1"})
    store.db.execute("UPDATE accounts SET plan = 'business'")  # customer delivery is a Business feature
    store.db.commit()

    event = connect_event("invoice.paid", {"id": "in_paid", "collection_method": "charge_automatically"})
    body, headers = signed(event, CONNECT_SECRET)
    assert app_client.post("/stripe/webhook", content=body, headers=headers).status_code == 200
    account = store.account_by_stripe_id("acct_seller", False)
    assert store.document(account.id, "in_paid").status == "generated"
    (msg,) = mailer.sent
    assert msg["To"] == "ap@kunde.de"


def test_connect_webhook_rejects_bad_signature_and_unknown_accounts(app_client):
    event = connect_event("invoice.paid", {"id": "in_paid"})
    body, headers = signed(event, "whsec_wrong")
    assert app_client.post("/stripe/webhook", content=body, headers=headers).status_code == 400
    body, headers = signed(connect_event("invoice.paid", {"id": "in_paid"}, account="acct_other"), CONNECT_SECRET)
    assert app_client.post("/stripe/webhook", content=body, headers=headers).json()["ignored"]


def test_event_before_onboarding_is_kept_as_blocked(app_client, store):
    install(app_client)
    body, headers = signed(connect_event("invoice.paid", {"id": "in_paid"}), CONNECT_SECRET)
    app_client.post("/stripe/webhook", content=body, headers=headers)
    account = store.account_by_stripe_id("acct_seller", False)
    doc = store.document(account.id, "in_paid")
    assert doc.status == "blocked" and "Firmendaten" in doc.problems[0]["message"]


def test_uninstall_event_forgets_tokens_and_ends_session(app_client, store):
    install(app_client)
    app_client.post("/konto/einrichten", data=PROFILE_FORM)
    body, headers = signed(connect_event("account.application.deauthorized", {"id": "ca_test"}), CONNECT_SECRET)
    app_client.post("/stripe/webhook", content=body, headers=headers)
    account = store.account_by_stripe_id("acct_seller", False)
    assert account.status == "uninstalled" and account.access_token is None and account.refresh_token is None
    assert account.profile is not None  # archive and profile are kept
    assert app_client.get("/konto").headers["location"] == "/anmelden"


def test_manual_webhook_path_refuses_oauth_accounts(app_client, store):
    install(app_client)
    account = store.account_by_stripe_id("acct_seller", False)
    body, headers = signed({"type": "invoice.paid", "data": {"object": {"id": "in_paid"}}})
    assert app_client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers).status_code == 404


def test_access_token_is_refreshed_and_rotated(app_client, store, oauth, server):
    install(app_client)
    account = store.account_by_stripe_id("acct_seller", False)
    assert oauth.access_token(store, account) == "sk_test_access_1"  # still fresh

    store.db.execute("UPDATE accounts SET token_expires_at = ?", (int(time.time()) - 1,))
    store.db.commit()
    assert oauth.access_token(store, account) == "sk_test_access_2"
    assert server.requests[-1][1] == {"grant_type": ["refresh_token"], "refresh_token": ["rt_1"]}
    assert store.account(account.id).refresh_token == "rt_2"  # rotated


def test_revoked_refresh_token_marks_account_uninstalled(app_client, store, oauth, server):
    install(app_client)
    account = store.account_by_stripe_id("acct_seller", False)
    store.db.execute("UPDATE accounts SET token_expires_at = 0")
    store.db.commit()
    server.revoked = True
    with pytest.raises(OAuthError):
        oauth.access_token(store, account)
    assert store.account(account.id).status == "uninstalled"


def test_install_page_without_app_config(store, gateway, mailer, monkeypatch):
    for var in ("STRIPE_APP_SECRET_KEY", "STRIPE_APP_INSTALL_LINK", "STRIPE_APP_CLIENT_ID"):
        monkeypatch.delenv(var, raising=False)
    client = TestClient(create_app(store=store, gateway_factory=lambda a: gateway, mailer=mailer))
    assert client.get("/stripe/install").status_code == 503
    assert "Mit Stripe verbinden" not in client.get("/").text


def test_iban_check_digits():
    assert iban_valid("DE02 1203 0000 0000 2020 51")
    assert not iban_valid("DE03120300000000202051")
    assert not iban_valid("DE02")


def test_kleinunternehmer_profile_needs_tax_number():
    form = {**PROFILE_FORM, "vat_id": "", "tax_number": "", "kleinunternehmer": "1"}
    profile, errors, _ = parse_profile(form)
    assert profile is None and "vat_id" in errors
    profile, errors, _ = parse_profile({**form, "tax_number": "30/123/45678"})
    assert errors == {} and profile.kleinunternehmer and profile.vat_id is None


def test_token_endpoint_outage_is_an_oauth_error():
    def down(request):
        raise httpx.ConnectError("no route")

    oauth = StripeOAuth(APP_SECRET, "https://x.test/cb", client_id="ca_x", http=httpx.Client(transport=httpx.MockTransport(down)))
    with pytest.raises(OAuthError) as exc:
        oauth.exchange_code("ac_good")
    assert exc.value.code == "unavailable"
    assert "client_id=ca_x" in oauth.authorize_url("s")  # link built from the client ID


def test_store_is_usable_from_several_threads(store):
    import threading

    errors = []

    def work(n):
        try:
            for i in range(20):
                store.add_to_waitlist(f"t{n}-{i}@firma.de", "test")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert store.db.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 80
