"""Stripe credit notes become e-invoice corrections (type 381)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from einvoice_bridge.cii import to_cii
from einvoice_bridge.pdf import to_zugferd_pdf
from einvoice_bridge.profile import SellerProfile
from einvoice_bridge.service import backfill, process_credit_note, process_invoice
from einvoice_bridge.sources.stripe import map_credit_note
from einvoice_bridge.ubl import to_ubl
from einvoice_bridge.validation import validate
from einvoice_bridge.web.app import SESSION_COOKIE, create_app

from .conftest import FIXTURES
from .test_web import gateway, mailer, signed, store  # noqa: F401 (shared fixtures)


@pytest.fixture
def profile() -> SellerProfile:
    return SellerProfile.load(FIXTURES / "seller_profile.toml")


@pytest.fixture
def notes(load_json):
    return {
        "cn_partial": load_json("stripe/credit_note_partial_refund.json"),
        "cn_open": load_json("stripe/credit_note_open_invoice.json"),
    }


@pytest.fixture
def cn_gateway(gateway, notes):
    gateway.credit_notes = notes
    return gateway


def map_note(load_json, profile, note_name, invoice_name, card=True):
    rates = load_json("stripe/tax_rates.json").get
    method = load_json("stripe/payment_method_card.json") if card else None
    return map_credit_note(load_json(f"stripe/{note_name}.json"), load_json(f"stripe/{invoice_name}.json"), profile, rates, method)


def assert_valid(doc) -> None:
    for xml in (to_ubl(doc), to_cii(doc, "xrechnung"), to_cii(doc, "en16931"), to_zugferd_pdf(doc)):
        report = validate(xml)
        assert report.valid, [(f.rule_id, f.message) for f in report.errors]


def test_partial_refund_to_card(load_json, profile):
    result = map_note(load_json, profile, "credit_note_partial_refund", "invoice_paid_card")
    assert result.ok, result.problems
    cn = result.invoice
    assert (cn.type_code, cn.number) == ("381", "MUSTER-0001-CN-01")
    assert (cn.preceding_invoice, str(cn.preceding_invoice_date)) == ("MUSTER-0001", "2026-10-01")
    assert (cn.line_total, cn.tax_total, cn.tax_inclusive_total) == (Decimal("8.99"), Decimal("1.71"), Decimal("10.70"))
    assert cn.lines[0].allowance_total == Decimal("1.00")
    assert str(cn.lines[0].period_start) == "2026-10-01"  # taken from the invoice line
    assert (cn.payment.means_code, cn.payment.card_last_digits) == ("54", "4242")
    assert "Karte (**** 4242) erstattet" in cn.payment_terms
    assert cn.notes[:2] == ["Korrektur zur Rechnung MUSTER-0001 vom 01.10.2026.", "Grund: Reklamation."]
    assert_valid(cn)

    ubl = etree.fromstring(to_ubl(cn))
    assert etree.QName(ubl).localname == "CreditNote"
    ns = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
          "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    assert ubl.findtext("cac:BillingReference/cac:InvoiceDocumentReference/cbc:ID", namespaces=ns) == "MUSTER-0001"


def test_credit_against_open_invoice_is_offset(load_json, profile):
    result = map_note(load_json, profile, "credit_note_open_invoice", "invoice_open_public_sector", card=False)
    assert result.ok, result.problems
    cn = result.invoice
    assert cn.buyer_reference == "991-12345-67"  # Leitweg-ID of the corrected invoice
    assert (cn.payment.means_code, cn.tax_inclusive_total) == ("97", Decimal("42.69"))
    assert "mindert den offenen Betrag der Rechnung MUSTER-0002" in cn.payment_terms
    assert_valid(cn)


@pytest.mark.parametrize(
    "change, code, phrase",
    [
        ({"refunds": [], "customer_balance_transaction": "cbtxn_1"}, "97", "Kundenguthaben"),
        ({"refunds": [], "out_of_band_amount": 1070}, "ZZZ", "gesondert"),
        ({"refunds": [{"refund": "re_1", "amount_refunded": 1070}]}, "ZZZ", "ursprüngliche Zahlungsmittel"),
    ],
)
def test_settlement_variants(load_json, profile, change, code, phrase):
    note = {**load_json("stripe/credit_note_partial_refund.json"), **change}
    method = None  # unknown payment method for the refund case
    result = map_credit_note(note, load_json("stripe/invoice_paid_card.json"), profile, load_json("stripe/tax_rates.json").get, method)
    assert result.ok, result.problems
    assert result.invoice.payment.means_code == code and phrase in result.invoice.payment_terms
    assert_valid(result.invoice)


def test_void_and_mismatched_credit_notes_are_refused(load_json, profile):
    rates = load_json("stripe/tax_rates.json").get
    invoice = load_json("stripe/invoice_paid_card.json")
    void = {**load_json("stripe/credit_note_partial_refund.json"), "status": "void"}
    assert map_credit_note(void, invoice, profile, rates).invoice is None
    off = {**load_json("stripe/credit_note_partial_refund.json"), "total": 999}
    result = map_credit_note(off, invoice, profile, rates)
    assert result.invoice is None and any(p.field == "total" for p in result.errors)


def test_pipeline_archives_and_delivers_correction(store, cn_gateway, mailer, profile):
    account = store.create_account(profile, "rk", "whsec", send_to_customer=True, plan="business")
    doc = process_credit_note(store, account, "cn_partial", cn_gateway, mailer)
    assert (doc.status, doc.kind, doc.related_number, doc.number) == ("generated", "credit_note", "MUSTER-0001", "MUSTER-0001-CN-01")
    (msg,) = mailer.sent
    assert msg["Subject"].startswith("Rechnungskorrektur MUSTER-0001-CN-01 zu Rechnung MUSTER-0001")
    assert msg["To"] == "ap@kunde.de"
    assert store.read_file(doc, "zugferd.pdf").startswith(b"%PDF-")
    assert process_credit_note(store, account, "cn_partial", cn_gateway, mailer).id == doc.id  # idempotent
    assert len(mailer.sent) == 1


def test_corrections_ignore_the_plan_limit(store, cn_gateway, mailer, profile, load_json):
    account = store.create_account(profile, "rk", "whsec")  # free: 3 per month
    for n in range(3):
        cn_gateway.invoices[f"in_{n}"] = {**load_json("stripe/invoice_paid_card.json"), "id": f"in_{n}", "number": f"X-{n}"}
        process_invoice(store, store.account(account.id), f"in_{n}", cn_gateway, mailer)
    assert process_invoice(store, store.account(account.id), "in_open", cn_gateway, mailer).status == "blocked"
    doc = process_credit_note(store, store.account(account.id), "cn_partial", cn_gateway, mailer)
    assert doc.status == "generated"


def test_backfill_includes_recent_credit_notes(store, cn_gateway, mailer, profile):
    account = store.create_account(profile, "rk", "whsec")
    docs = backfill(store, account, cn_gateway, mailer)
    kinds = sorted((d.kind, d.status) for d in docs)
    assert kinds.count(("credit_note", "generated")) == 2 and mailer.sent == []


def test_webhook_created_then_voided(store, cn_gateway, mailer, profile):
    account = store.create_account(profile, "rk", "whsec_test", send_to_customer=True, plan="business")
    client = TestClient(create_app(store=store, gateway_factory=lambda a: cn_gateway, mailer=mailer, base_url="https://x.test"))
    created = {"type": "credit_note.created", "data": {"object": {"id": "cn_partial", "object": "credit_note"}}}
    body, headers = signed(created)
    assert client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers).status_code == 200
    assert store.document(account.id, "cn_partial").status == "generated"

    voided = {"type": "credit_note.voided", "data": {"object": {"id": "cn_partial", "object": "credit_note"}}}
    body, headers = signed(voided)
    client.post(f"/stripe/webhook/{account.id}", content=body, headers=headers)
    doc = store.document(account.id, "cn_partial")
    assert doc.status == "voided" and "storniert" in doc.problems[-1]["message"]
    assert "wurde in Stripe storniert" in mailer.sent[-1]["Subject"]
    assert store.read_file(doc, "xrechnung.xml")  # archive untouched

    client.cookies.set(SESSION_COOKIE, store.fernet.encrypt(account.id.encode()).decode())
    page = client.get(f"/konto/{account.dashboard_token}")
    assert "Rechnungskorrektur zu MUSTER-0001" in page.text and "Storniert" in page.text
