"""Paddle billing: plans, limits, webhook, checkout, portal, plan change."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from einvoice_bridge.billing import (
    PLANS,
    PaddleClient,
    PaddleConfig,
    account_from_custom_data,
    effective_plan,
    sign_account,
    verify_paddle_signature,
)
from einvoice_bridge.profile import SellerProfile
from einvoice_bridge.service import backfill, process_invoice
from einvoice_bridge.web.app import SESSION_COOKIE, create_app

from .conftest import FIXTURES
from .test_web import FakeGateway, FakeMailer, gateway, mailer, store  # noqa: F401 (shared fixtures)

PADDLE_SECRET = "pdl_ntfset_secret"
PRICES = {"starter": ["pri_starter_m", "pri_starter_y"], "business": ["pri_business_m"]}


def paddle_signed(event: dict, secret: str = PADDLE_SECRET, ts: int | None = None) -> tuple[bytes, dict]:
    body = json.dumps(event).encode()
    ts = ts or int(time.time())
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return body, {"paddle-signature": f"ts={ts};h1={h1}", "content-type": "application/json"}


class FakePaddleAPI:
    def __init__(self):
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/portal-sessions"):
            return httpx.Response(201, json={"data": {"urls": {"general": {"overview": "https://customer-portal.paddle.com/cpl_1"}}}})
        if request.method == "PATCH":
            return httpx.Response(200, json={"data": {"id": "sub_1"}})
        return httpx.Response(404, json={})


@pytest.fixture
def paddle():
    return PaddleConfig("test_client_token", "pdl_sdbx_apikey", PADDLE_SECRET, sandbox=True, prices=PRICES)


@pytest.fixture
def paddle_api():
    return FakePaddleAPI()


@pytest.fixture
def seller_account(store):
    profile = SellerProfile.load(FIXTURES / "seller_profile.toml")
    return store.create_account(profile, "rk_test", "whsec_x", send_to_customer=True)  # free plan


@pytest.fixture
def many_invoices(gateway):
    """Ten distinct paid invoices for limit tests."""
    template = gateway.invoices["in_paid"]
    for n in range(1, 11):
        gateway.invoices[f"in_{n}"] = {**json.loads(json.dumps(template)), "id": f"in_{n}", "number": f"MUSTER-1{n:03d}"}
    return gateway


@pytest.fixture
def client(store, gateway, mailer, paddle, paddle_api, seller_account):
    app = create_app(
        store=store,
        gateway_factory=lambda account: gateway,
        mailer=mailer,
        base_url="https://example.test",
        paddle=paddle,
        paddle_client=PaddleClient(paddle, http=httpx.Client(transport=httpx.MockTransport(paddle_api))),
    )
    client = TestClient(app, base_url="https://example.test", follow_redirects=False)
    client.cookies.set(SESSION_COOKIE, store.fernet.encrypt(seller_account.id.encode()).decode())
    return client


def subscription_event(account_id, store, *, status="trialing", price="pri_business_m", event_type="subscription.created",
                       occurred_at="2026-10-04T08:00:00Z", signed_data=True, scheduled_change=None):
    custom = {"account_id": account_id, "account_sig": sign_account(account_id, store.secret)} if signed_data else {}
    return {
        "event_id": "evt_1",
        "event_type": event_type,
        "occurred_at": occurred_at,
        "notification_id": "ntf_1",
        "data": {
            "id": "sub_1",
            "status": status,
            "customer_id": "ctm_1",
            "items": [{"price": {"id": price, "product_id": "pro_1"}, "quantity": 1}],
            "custom_data": custom,
            "current_billing_period": {"starts_at": "2026-10-04T08:00:00Z", "ends_at": "2026-10-18T08:00:00Z"},
            "scheduled_change": scheduled_change,
        },
    }


# signatures -------------------------------------------------------------------


def test_paddle_signature_checks():
    body, headers = paddle_signed({"a": 1})
    header = headers["paddle-signature"]
    assert verify_paddle_signature(body, header, PADDLE_SECRET)
    assert not verify_paddle_signature(body + b" ", header, PADDLE_SECRET)  # body changed
    assert not verify_paddle_signature(body, header, "other_secret")
    assert not verify_paddle_signature(body, "garbage", PADDLE_SECRET)
    old_body, old = paddle_signed({"a": 1}, ts=int(time.time()) - 3600)
    assert not verify_paddle_signature(old_body, old["paddle-signature"], PADDLE_SECRET)  # replay


def test_checkout_custom_data_cannot_be_forged():
    tag = sign_account("acc_1", "server-secret")
    assert account_from_custom_data({"account_id": "acc_1", "account_sig": tag}, "server-secret") == "acc_1"
    assert account_from_custom_data({"account_id": "acc_2", "account_sig": tag}, "server-secret") is None
    assert account_from_custom_data({"account_id": "acc_1"}, "server-secret") is None


def test_effective_plan(seller_account):
    assert effective_plan(seller_account).key == "free"
    assert effective_plan(replace(seller_account, plan="business")).key == "business"  # operator-assigned
    sub = replace(seller_account, plan="starter", paddle_subscription_id="sub_1")
    for status, expected in (("trialing", "starter"), ("active", "starter"), ("past_due", "starter"),
                             ("paused", "free"), ("canceled", "free")):
        assert effective_plan(replace(sub, subscription_status=status)).key == expected


# limits in the pipeline -----------------------------------------------------------


def test_free_plan_limit_holds_invoices_and_notifies_once(store, seller_account, many_invoices, mailer):
    results = [process_invoice(store, store.account(seller_account.id), f"in_{n}", many_invoices, mailer, base_url="https://x")
               for n in range(1, 6)]
    assert [d.status for d in results] == ["generated"] * 3 + ["blocked"] * 2
    assert results[3].problems[0]["field"] == "plan"
    limit_mails = [m for m in mailer.sent if "Monatslimit" in m["Subject"]]
    assert len(limit_mails) == 1 and "https://x/konto/abo" in limit_mails[0].get_content()


def test_first_run_preview_does_not_count(store, seller_account, many_invoices, mailer):
    docs = backfill(store, store.account(seller_account.id), many_invoices, mailer, limit=10)
    assert all(d.status == "generated" for d in docs) and len(docs) == 10
    doc = process_invoice(store, store.account(seller_account.id), "in_open", many_invoices, mailer)
    assert doc.status == "generated"  # still within the 3 free conversions


def test_customer_delivery_needs_business(store, seller_account, gateway, mailer):
    store.db.execute("UPDATE accounts SET plan = 'starter'")
    store.db.commit()
    process_invoice(store, store.account(seller_account.id), "in_paid", gateway, mailer)
    (msg,) = mailer.sent
    assert msg["To"] == "buchhaltung@muster.de"  # seller, although send_to_customer is on


# webhook -------------------------------------------------------------------------


def test_subscription_webhook_upgrades_and_releases_held_invoices(client, store, seller_account, many_invoices, mailer):
    for n in range(1, 6):
        process_invoice(store, store.account(seller_account.id), f"in_{n}", many_invoices, mailer)
    assert sum(d.status == "blocked" for d in store.documents(seller_account.id)) == 2
    mailer.sent.clear()

    body, headers = paddle_signed(subscription_event(seller_account.id, store))
    assert client.post("/paddle/webhook", content=body, headers=headers).status_code == 200

    account = store.account(seller_account.id)
    assert (account.plan, account.subscription_status, account.paddle_customer_id) == ("business", "trialing", "ctm_1")
    assert effective_plan(account).key == "business"
    assert all(d.status == "generated" for d in store.documents(seller_account.id))
    # the two held invoices are delivered now, to the customer (Business)
    assert [m["To"] for m in mailer.sent] == ["ap@kunde.de", "ap@kunde.de"]


def test_older_webhook_does_not_override_newer_state(client, store, seller_account):
    newer = subscription_event(seller_account.id, store, status="canceled", event_type="subscription.canceled",
                               occurred_at="2026-10-05T10:00:00Z")
    older = subscription_event(seller_account.id, store, status="active", event_type="subscription.updated",
                               occurred_at="2026-10-05T09:00:00Z")
    for event in (newer, older):
        body, headers = paddle_signed(event)
        client.post("/paddle/webhook", content=body, headers=headers)
    account = store.account(seller_account.id)
    assert account.subscription_status == "canceled" and effective_plan(account).key == "free"


def test_later_events_found_by_subscription_id_and_cancel_scheduled(client, store, seller_account):
    body, headers = paddle_signed(subscription_event(seller_account.id, store, status="active"))
    client.post("/paddle/webhook", content=body, headers=headers)
    update = subscription_event(seller_account.id, store, status="active", event_type="subscription.updated",
                                price="pri_starter_y", occurred_at="2026-10-06T08:00:00Z", signed_data=False,
                                scheduled_change={"action": "cancel", "effective_at": "2026-11-04T08:00:00Z"})
    body, headers = paddle_signed(update)
    client.post("/paddle/webhook", content=body, headers=headers)
    account = store.account(seller_account.id)
    assert account.plan == "starter" and account.cancel_at == "2026-11-04T08:00:00Z"
    page = client.get("/konto/abo")
    assert "Gekündigt zum 2026-11-04" in page.text


def test_webhook_rejects_bad_signature_and_ignores_strangers(client, store, seller_account):
    body, headers = paddle_signed(subscription_event(seller_account.id, store), secret="wrong")
    assert client.post("/paddle/webhook", content=body, headers=headers).status_code == 400
    stranger = subscription_event("acc_unknown", store)
    stranger["data"].update(id="sub_other", customer_id="ctm_other")
    body, headers = paddle_signed(stranger)
    assert client.post("/paddle/webhook", content=body, headers=headers).status_code == 200
    assert store.account(seller_account.id).paddle_subscription_id is None


# pages, portal, plan change ---------------------------------------------------------


def test_subscription_page_offers_trial_checkout(client, store, seller_account):
    page = client.get("/konto/abo")
    assert page.status_code == 200
    assert "cdn.paddle.com/paddle/v2/paddle.js" in page.text and 'Paddle.Environment.set("sandbox")' in page.text
    assert 'data-price="pri_starter_m"' in page.text and 'data-price="pri_business_m"' in page.text
    assert sign_account(seller_account.id, store.secret) in page.text
    assert "0 von 3 E-Rechnungen" in page.text


def test_portal_link_is_created_on_demand(client, store, seller_account, paddle_api):
    body, headers = paddle_signed(subscription_event(seller_account.id, store, status="active"))
    client.post("/paddle/webhook", content=body, headers=headers)
    response = client.post("/konto/abo/verwalten")
    assert response.headers["location"] == "https://customer-portal.paddle.com/cpl_1"
    request = paddle_api.requests[-1]
    assert str(request.url) == "https://sandbox-api.paddle.com/customers/ctm_1/portal-sessions"
    assert request.headers["authorization"] == "Bearer pdl_sdbx_apikey"
    assert json.loads(request.content) == {"subscription_ids": ["sub_1"]}


def test_plan_change_goes_through_paddle(client, store, seller_account, paddle_api):
    body, headers = paddle_signed(subscription_event(seller_account.id, store, status="active", price="pri_starter_m"))
    client.post("/paddle/webhook", content=body, headers=headers)
    page = client.get("/konto/abo")
    assert "Zu Business wechseln" in page.text and "14 Tage kostenlos testen" not in page.text
    response = client.post("/konto/abo/wechseln", data={"plan": "business"})
    assert response.headers["location"] == "/konto/abo?status=gewechselt"
    request = paddle_api.requests[-1]
    assert request.method == "PATCH" and request.url.path == "/subscriptions/sub_1"
    assert json.loads(request.content) == {
        "items": [{"price_id": "pri_business_m", "quantity": 1}],
        "proration_billing_mode": "prorated_immediately",
    }


def test_billing_pages_without_paddle(store, gateway, mailer, seller_account, monkeypatch):
    for var in ("PADDLE_CLIENT_TOKEN", "PADDLE_API_KEY", "PADDLE_WEBHOOK_SECRET"):
        monkeypatch.delenv(var, raising=False)
    client = TestClient(create_app(store=store, gateway_factory=lambda a: gateway, mailer=mailer), follow_redirects=False)
    client.cookies.set(SESSION_COOKIE, store.fernet.encrypt(seller_account.id.encode()).decode())
    page = client.get("/konto/abo")
    assert page.status_code == 200 and "paddle.js" not in page.text and "Bald verfügbar" in page.text
    assert client.post("/paddle/webhook", content=b"{}").status_code == 404


def test_plans_match_pricing_page():
    assert (PLANS["starter"].price_eur, PLANS["starter"].monthly_limit) == (9, 30)
    assert (PLANS["business"].price_eur, PLANS["business"].monthly_limit) == (29, 300)


def test_default_payment_link_page_is_public(client):
    client.cookies.clear()
    page = client.get("/bezahlen?_ptxn=txn_123")
    assert page.status_code == 200 and "Paddle.Initialize" in page.text


def test_late_cancel_of_old_subscription_keeps_new_one(client, store, seller_account):
    old = subscription_event(seller_account.id, store, status="active", occurred_at="2026-10-01T08:00:00Z")
    new = subscription_event(seller_account.id, store, status="active", occurred_at="2026-10-04T08:00:00Z")
    new["data"]["id"] = "sub_2"
    late_cancel = subscription_event(seller_account.id, store, status="canceled", event_type="subscription.canceled",
                                     occurred_at="2026-10-05T08:00:00Z")  # about sub_1
    for event in (old, new, late_cancel):
        body, headers = paddle_signed(event)
        client.post("/paddle/webhook", content=body, headers=headers)
    account = store.account(seller_account.id)
    assert account.paddle_subscription_id == "sub_2" and effective_plan(account).key == "business"


def test_unmapped_price_falls_back_to_free(client, store, seller_account, caplog):
    body, headers = paddle_signed(subscription_event(seller_account.id, store, status="active", price="pri_unknown"))
    client.post("/paddle/webhook", content=body, headers=headers)
    assert effective_plan(store.account(seller_account.id)).key == "free"
    assert "not mapped to a plan" in caplog.text
