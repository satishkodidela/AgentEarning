from __future__ import annotations

import hashlib
import hmac
import json
import re
import time

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from einvoice_bridge.profile import SellerProfile
from einvoice_bridge.service import process_invoice
from einvoice_bridge.store import Store
from einvoice_bridge.web.app import create_app

from .conftest import FIXTURES

WEBHOOK_SECRET = "whsec_test"


class FakeGateway:
    def __init__(self, invoices: dict, rates: dict, method: dict | None, credit_notes: dict | None = None):
        self.invoices, self.rates, self.method = invoices, rates, method
        self.credit_notes = credit_notes or {}

    def invoice(self, invoice_id):
        return json.loads(json.dumps(self.invoices[invoice_id]))

    def tax_rate(self, tax_rate_id):
        return self.rates.get(tax_rate_id)

    def payment_method(self, invoice):
        return self.method

    def recent_invoices(self, limit):
        return [self.invoice(i) for i in list(self.invoices)[:limit]]

    def credit_note(self, credit_note_id):
        return json.loads(json.dumps(self.credit_notes[credit_note_id]))

    def recent_credit_notes(self, limit):
        return [self.credit_note(i) for i in list(self.credit_notes)[:limit]]


class FakeMailer:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path, Fernet.generate_key().decode())


@pytest.fixture
def account(store):
    profile = SellerProfile.load(FIXTURES / "seller_profile.toml")
    return store.create_account(profile, "rk_test_123", WEBHOOK_SECRET, send_to_customer=True, plan="business")


@pytest.fixture
def gateway(load_json):
    invoices = {
        inv["id"]: inv
        for inv in (load_json("stripe/invoice_paid_card.json"), load_json("stripe/invoice_open_public_sector.json"))
    }
    return FakeGateway(invoices, load_json("stripe/tax_rates.json"), load_json("stripe/payment_method_card.json"))


@pytest.fixture
def mailer():
    return FakeMailer()


@pytest.fixture
def client(store, gateway, mailer):
    app = create_app(store=store, gateway_factory=lambda account: gateway, mailer=mailer, base_url="https://example.test")
    return TestClient(app)


def signed(payload: dict, secret: str = WEBHOOK_SECRET) -> tuple[bytes, dict]:
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


def test_secrets_are_encrypted_at_rest(store, account):
    raw = store.db.execute("SELECT stripe_api_key, webhook_secret FROM accounts").fetchone()
    assert "rk_test_123" not in raw[0] and WEBHOOK_SECRET not in raw[1]
    assert store.account(account.id).stripe_api_key == "rk_test_123"


def test_pipeline_generates_archives_and_delivers(store, account, gateway, mailer):
    doc = process_invoice(store, account, "in_paid", gateway, mailer)
    assert doc.status == "generated"
    assert set(doc.files) == {"xrechnung.xml", "zugferd.pdf"}
    assert store.read_file(doc, "zugferd.pdf").startswith(b"%PDF-")
    (msg,) = mailer.sent
    assert msg["To"] == "ap@kunde.de" and msg["Bcc"] == "buchhaltung@muster.de"
    names = [part.get_filename() for part in msg.iter_attachments()]
    assert names == ["MUSTER-0001.pdf", "MUSTER-0001.xml"]
    assert doc.delivered_to == "ap@kunde.de, buchhaltung@muster.de"

    # Stripe retries webhooks: a second run must not regenerate or resend.
    again = process_invoice(store, account, "in_paid", gateway, mailer)
    assert again.id == doc.id and len(mailer.sent) == 1


def test_archive_is_tamper_evident(store, account, gateway, mailer):
    doc = process_invoice(store, account, "in_paid", gateway, mailer)
    path = store.document_dir(account.id, "in_paid") / "xrechnung.xml"
    path.chmod(0o644)
    path.write_bytes(b"<changed/>")
    with pytest.raises(RuntimeError):
        store.read_file(doc, "xrechnung.xml")


def test_blocked_invoice_sends_fix_list_then_retries(store, account, gateway, mailer):
    gateway.invoices["in_paid"]["customer_address"]["city"] = None
    doc = process_invoice(store, account, "in_paid", gateway, mailer)
    assert doc.status == "blocked" and not doc.files
    assert "Ort" in mailer.sent[0].get_content()
    gateway.invoices["in_paid"]["customer_address"]["city"] = "München"
    assert process_invoice(store, account, "in_paid", gateway, mailer).status == "generated"


def test_webhook_rejects_bad_signature(client, account):
    body, headers = signed({"type": "invoice.paid", "data": {"object": {"id": "in_paid"}}})
    headers["stripe-signature"] = headers["stripe-signature"].replace("v1=", "v1=00")
    assert client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers).status_code == 400


def test_webhook_processes_paid_invoice(client, store, account):
    event = {"type": "invoice.paid", "data": {"object": {"id": "in_paid", "collection_method": "charge_automatically"}}}
    body, headers = signed(event)
    assert client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers).status_code == 200
    assert store.document(account.id, "in_paid").status == "generated"

    page = client.get(f"/konto/{account.dashboard_token}")
    assert "MUSTER-0001" in page.text and "Erstellt" in page.text
    pdf = client.get(f"/konto/{account.dashboard_token}/dokumente/in_paid/zugferd.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")


def test_webhook_ignores_finalized_auto_charge_invoices(client, store, account):
    event = {"type": "invoice.finalized", "data": {"object": {"id": "in_paid", "collection_method": "charge_automatically"}}}
    body, headers = signed(event)
    client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers)
    assert store.document(account.id, "in_paid") is None


def test_free_validator_page(client):
    xml = (FIXTURES / "official" / "01.01a-INVOICE_ubl.xml").read_bytes()
    page = client.post("/pruefen", files={"datei": ("rechnung.xml", xml, "application/xml")})
    assert page.status_code == 200 and "Gültig" in page.text

    broken = re.sub(rb"<cbc:BuyerReference>.*?</cbc:BuyerReference>", b"", xml)
    page = client.post("/pruefen", files={"datei": ("rechnung.xml", broken, "application/xml")})
    assert "Ungültig" in page.text and "/regeln/br-de-15" in page.text

    page = client.post("/pruefen", files={"datei": ("x.txt", b"hello", "text/plain")})
    assert page.status_code == 422


def test_validate_api(client):
    xml = (FIXTURES / "official" / "01.01a-INVOICE_uncefact.xml").read_bytes()
    data = client.post("/api/v1/validate", files={"datei": ("r.xml", xml)}).json()
    assert data["valid"] is True and data["is_xrechnung"] is True


def test_rule_pages_and_sitemap(client):
    page = client.get("/regeln/br-de-15")
    assert page.status_code == 200 and "Leitweg-ID" in page.text
    assert client.get("/regeln/does-not-exist").status_code == 404
    sitemap = client.get("/sitemap.xml").text
    assert "https://example.test/regeln/br-co-17" in sitemap


def test_waitlist_double_opt_in(client, store, mailer):
    assert client.post("/warteliste", data={"email": "a@firma.de"}).status_code == 422  # no consent
    client.post("/warteliste", data={"email": "a@firma.de", "einwilligung": "true"})
    (msg,) = mailer.sent
    link = next(line for line in msg.get_content().splitlines() if "/warteliste/bestaetigen/" in line)
    token = link.rsplit("/", 1)[-1]
    assert "Danke" in client.get(f"/warteliste/bestaetigen/{token}").text
    assert "ungültig" in client.get(f"/warteliste/bestaetigen/{token}").text


def test_send_invoice_blocked_at_finalize_is_retried_when_paid(client, store, account, gateway):
    gateway.invoices["in_open"]["customer_email"] = None
    finalized = {"type": "invoice.finalized", "data": {"object": {"id": "in_open", "collection_method": "send_invoice"}}}
    body, headers = signed(finalized)
    client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers)
    assert store.document(account.id, "in_open").status == "blocked"

    gateway.invoices["in_open"]["customer_email"] = "einkauf@musterstadt.de"
    paid = {"type": "invoice.paid", "data": {"object": {"id": "in_open", "collection_method": "send_invoice"}}}
    body, headers = signed(paid)
    client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers)
    assert store.document(account.id, "in_open").status == "generated"


def test_pages_paddle_reviews_are_public(client):
    # Paddle's domain review needs these to load without login and return 200.
    for path in ("/", "/preise", "/agb", "/rueckerstattung", "/datenschutz", "/impressum", "/kontakt"):
        assert client.get(path).status_code == 200, path
    assert "Paddle.com" in client.get("/preise").text
    assert "14 Tagen" in client.get("/rueckerstattung").text


def test_legal_texts_are_loaded_from_files(store, gateway, mailer, tmp_path):
    legal = tmp_path / "legal"
    legal.mkdir()
    (legal / "impressum.html").write_text("<p>Max Mustermann, Musterstraße 1</p>", encoding="utf-8")
    app = create_app(store=store, gateway_factory=lambda a: gateway, mailer=mailer, legal_dir=legal)
    page = TestClient(app).get("/impressum").text
    assert "Max Mustermann" in page and "Vor dem Livegang" not in page


def test_ssl_validation_files_are_served_without_traversal(store, gateway, mailer, tmp_path, monkeypatch):
    well_known = tmp_path / "public_html" / ".well-known"
    (well_known / "pki-validation").mkdir(parents=True)
    (well_known / "pki-validation" / "ABC.txt").write_text("sectigo-token")
    (tmp_path / "secret.txt").write_text("do not serve")
    monkeypatch.setenv("EINVOICE_WELL_KNOWN_DIR", str(well_known))
    client = TestClient(create_app(store=store, gateway_factory=lambda a: gateway, mailer=mailer))
    response = client.get("/.well-known/pki-validation/ABC.txt")
    assert response.status_code == 200 and response.text == "sectigo-token"
    assert client.get("/.well-known/pki-validation/missing.txt").status_code == 404
    assert client.get("/.well-known/../../secret.txt").status_code == 404
    assert client.get("/.well-known/%2e%2e/%2e%2e/secret.txt").status_code == 404
