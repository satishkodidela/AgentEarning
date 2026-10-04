"""Every generated document must pass the official XSD + Schematron rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from einvoice_bridge.cii import to_cii
from einvoice_bridge.model import Address, Line, Party, Payment, VatCategory
from einvoice_bridge.ubl import to_ubl
from einvoice_bridge.validation import validate

RENDERERS = {
    "xrechnung-ubl": to_ubl,
    "xrechnung-cii": lambda inv: to_cii(inv, "xrechnung"),
    "zugferd-en16931-cii": lambda inv: to_cii(inv, "en16931"),
}


def assert_valid(xml: bytes, expect_xrechnung: bool) -> None:
    report = validate(xml)
    problems = [(f.rule_id, f.message) for f in report.findings if f.severity != "info"]
    assert report.valid and not problems, problems
    assert report.is_xrechnung is expect_xrechnung


@pytest.fixture(params=sorted(RENDERERS))
def render(request):
    renderer = RENDERERS[request.param]
    return lambda inv: assert_valid(renderer(inv), expect_xrechnung=request.param.startswith("xrechnung"))


def test_standard_invoice_with_two_rates_and_discount(make_invoice, render):
    invoice = make_invoice()
    assert invoice.line_total == Decimal("85.97")  # 49 + (29.97 - 3) + 10
    assert invoice.tax_total == Decimal("15.13")  # 19% of 75.97 = 14.43, plus 7% of 10
    render(invoice)


def test_paid_by_card(make_invoice, render):
    invoice = make_invoice(
        payment=Payment(means_code="54", card_last_digits="4242", card_network="VISA"),
        due_date=None,
        payment_terms="Bereits per Kreditkarte bezahlt.",
    )
    invoice.paid_amount = invoice.tax_inclusive_total
    assert invoice.amount_due == 0
    render(invoice)


def test_credit_note(make_invoice, render):
    render(make_invoice(type_code="381", preceding_invoice="INV-0001", preceding_invoice_date=date(2026, 10, 1)))


def test_sepa_direct_debit(make_invoice, seller, render):
    render(
        make_invoice(
            seller=replace(seller, creditor_id="DE98ZZZ09999999999"),
            payment=Payment(means_code="59", mandate_reference="MANDATE-1", debited_iban="DE02120300000000202051"),
        )
    )


def test_kleinunternehmer_without_vat_id(make_invoice, seller, render):
    small = replace(seller, name="Anna Freelance", vat_id=None)
    invoice = make_invoice(
        seller=small,
        lines=[
            Line(
                id="1",
                name="Beratung",
                quantity=Decimal("2.5"),
                unit_code="HUR",
                net_price=Decimal(80),
                vat_category=VatCategory.EXEMPT,
                vat_rate=Decimal(0),
            )
        ],
    )
    assert invoice.tax_total == 0
    assert small.effective_identifier == small.tax_number
    render(invoice)


def test_reverse_charge_to_eu_business(make_invoice, render):
    buyer = Party(
        name="Client SARL",
        address=Address(city="Paris", postcode="75001", country_code="FR", line1="1 Rue de Rivoli"),
        electronic_address="ap@client.fr",
        vat_id="FR12345678901",
    )
    render(
        make_invoice(
            buyer=buyer,
            lines=[
                Line(
                    id="1",
                    name="SaaS-Lizenz",
                    quantity=Decimal(1),
                    net_price=Decimal(500),
                    vat_category=VatCategory.REVERSE_CHARGE,
                    vat_rate=Decimal(0),
                )
            ],
        )
    )


def test_charged_tax_within_tolerance_is_kept(make_invoice, render):
    invoice = make_invoice()
    key = (VatCategory.STANDARD, Decimal(19))
    computed = next(b.tax_amount for b in invoice.vat_breakdown() if b.rate == 19)
    invoice.charged_tax[key] = computed + Decimal("0.01")  # Stripe rounds per line
    assert invoice.tax_total == Decimal("15.14")
    render(invoice)


def test_missing_buyer_reference_is_reported(make_invoice):
    report = validate(to_ubl(make_invoice(buyer_reference="")))
    assert not report.valid
    (finding,) = [f for f in report.errors if f.rule_id == "BR-DE-15"]
    assert finding.hint
