from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from einvoice_bridge.cii import to_cii
from einvoice_bridge.model import VatCategory
from einvoice_bridge.profile import SellerProfile
from einvoice_bridge.sources.stripe import map_invoice
from einvoice_bridge.ubl import to_ubl
from einvoice_bridge.validation import validate

from .conftest import FIXTURES


@pytest.fixture
def profile() -> SellerProfile:
    return SellerProfile.load(FIXTURES / "seller_profile.toml")


@pytest.fixture
def rates(load_json):
    return load_json("stripe/tax_rates.json").get


@pytest.fixture
def card(load_json):
    return load_json("stripe/payment_method_card.json")


def assert_all_formats_valid(invoice):
    for xml in (to_ubl(invoice), to_cii(invoice, "xrechnung"), to_cii(invoice, "en16931")):
        report = validate(xml)
        assert report.valid, [(f.rule_id, f.message) for f in report.errors]


def test_paid_subscription_with_discount(load_json, profile, rates, card):
    result = map_invoice(load_json("stripe/invoice_paid_card.json"), profile, rates, card)
    assert result.ok, result.problems
    inv = result.invoice
    assert inv.number == "MUSTER-0001"
    assert str(inv.issue_date) == "2026-10-01"
    assert [line.net_amount for line in inv.lines] == [Decimal("49.00"), Decimal("26.97")]
    assert inv.lines[1].allowance_total == Decimal("3.00")
    assert inv.tax_inclusive_total == Decimal("90.40")
    assert inv.amount_due == 0
    assert (inv.payment.means_code, inv.payment.card_last_digits) == ("54", "4242")
    assert inv.buyer_reference == "cus_Q1"
    assert [p.field for p in result.problems] == ["buyer_reference"]  # warning only
    assert_all_formats_valid(inv)


def test_open_invoice_to_public_sector_uses_leitweg_id(load_json, profile):
    result = map_invoice(load_json("stripe/invoice_open_public_sector.json"), profile)
    assert result.ok, result.problems
    inv = result.invoice
    assert inv.buyer_reference == "991-12345-67"
    assert inv.order_reference == "PO-2026-17"
    assert inv.payment.means_code == "58" and inv.payment.iban == profile.iban
    assert str(inv.due_date) == "2026-10-16"
    assert "16.10.2026" in inv.payment_terms and "invoice.stripe.com" in inv.payment_terms
    assert {line.vat_rate for line in inv.lines} == {Decimal(19), Decimal(7)}
    assert inv.delivery_date == inv.issue_date  # one-off items: date of supply
    assert_all_formats_valid(inv)


def test_reverse_charge(load_json, profile, rates, card):
    result = map_invoice(load_json("stripe/invoice_reverse_charge.json"), profile, rates, card)
    assert result.ok, result.problems
    assert result.invoice.lines[0].vat_category == VatCategory.REVERSE_CHARGE
    assert_all_formats_valid(result.invoice)


def test_tax_inclusive_prices(load_json, profile, rates, card):
    result = map_invoice(load_json("stripe/invoice_tax_inclusive.json"), profile, rates, card)
    assert result.ok, result.problems
    inv = result.invoice
    assert inv.line_total == Decimal("45.00")
    assert inv.tax_total == Decimal("8.55")
    assert_all_formats_valid(inv)


def test_missing_customer_address_gives_fix_list(load_json, profile, rates, card):
    raw = load_json("stripe/invoice_paid_card.json")
    raw["customer_address"] = {"line1": None, "city": None, "postal_code": None, "country": "DE"}
    raw["customer_email"] = None
    result = map_invoice(raw, profile, rates, card)
    assert result.invoice is None
    fields = {p.field for p in result.errors}
    assert {"customer_address.city", "customer_address.postal_code", "customer_email"} <= fields


def test_zero_tax_without_reason_is_not_guessed(load_json, profile, rates, card):
    raw = load_json("stripe/invoice_paid_card.json")
    for line in raw["lines"]["data"]:
        line["taxes"] = []
    raw["total"] = raw["amount_due"] = raw["amount_paid"] = 7597
    result = map_invoice(raw, profile, rates, card)
    assert result.invoice is None
    assert any("keine Umsatzsteuer" in p.message for p in result.errors)


def test_kleinunternehmer_without_tax(load_json, profile, rates, card):
    raw = load_json("stripe/invoice_paid_card.json")
    for line in raw["lines"]["data"]:
        line["taxes"] = []
    raw["total"] = raw["amount_due"] = raw["amount_paid"] = 7597
    small = replace(profile, kleinunternehmer=True, vat_id=None)
    result = map_invoice(raw, small, rates, card)
    assert result.ok, result.problems
    assert {line.vat_category for line in result.invoice.lines} == {VatCategory.EXEMPT}
    assert_all_formats_valid(result.invoice)


def test_total_mismatch_is_refused(load_json, profile, rates, card):
    raw = load_json("stripe/invoice_paid_card.json")
    raw["total"] += 500  # e.g. an invoice-level item the mapper does not model
    result = map_invoice(raw, profile, rates, card)
    assert result.invoice is None
    assert any(p.field == "total" for p in result.errors)


def test_unknown_tax_rate_is_reported(load_json, profile, card):
    result = map_invoice(load_json("stripe/invoice_paid_card.json"), profile, None, card)
    assert result.invoice is None
    assert any("Steuersatz" in p.message for p in result.errors)


def test_drafts_are_skipped(load_json, profile, rates, card):
    raw = load_json("stripe/invoice_paid_card.json")
    raw["status"] = "draft"
    assert map_invoice(raw, profile, rates, card).invoice is None
