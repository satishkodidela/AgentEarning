from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from einvoice_bridge.model import (
    Address,
    Allowance,
    Contact,
    Invoice,
    Line,
    Party,
    Payment,
    VatCategory,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def seller() -> Party:
    return Party(
        name="Muster Software GmbH",
        address=Address(city="Berlin", postcode="10115", country_code="DE", line1="Invalidenstraße 1"),
        electronic_address="rechnung@muster.de",
        vat_id="DE123456789",
        tax_number="30/123/45678",
        contact=Contact(name="Buchhaltung", phone="+49 30 1234567", email="buchhaltung@muster.de"),
    )


@pytest.fixture
def buyer() -> Party:
    return Party(
        name="Kunde AG",
        address=Address(city="München", postcode="80331", country_code="DE", line1="Marienplatz 2"),
        electronic_address="ap@kunde.de",
        vat_id="DE987654321",
    )


@pytest.fixture
def make_invoice(seller, buyer):
    def make(**overrides) -> Invoice:
        fields = dict(
            number="INV-0001",
            issue_date=date(2026, 10, 1),
            seller=seller,
            buyer=buyer,
            buyer_reference="cus_123",
            payment=Payment(
                means_code="58",
                iban="DE02120300000000202051",
                account_name="Muster Software GmbH",
                remittance_info="INV-0001",
            ),
            due_date=date(2026, 10, 15),
            payment_terms="Zahlbar innerhalb von 14 Tagen.",
            delivery_date=date(2026, 10, 1),
            lines=[
                Line(
                    id="1",
                    name="Pro-Abo",
                    quantity=Decimal(1),
                    net_price=Decimal("49.00"),
                    vat_category=VatCategory.STANDARD,
                    vat_rate=Decimal(19),
                    period_start=date(2026, 10, 1),
                    period_end=date(2026, 10, 31),
                ),
                Line(
                    id="2",
                    name="Zusätzliche Nutzer",
                    quantity=Decimal(3),
                    net_price=Decimal("9.99"),
                    vat_category=VatCategory.STANDARD,
                    vat_rate=Decimal(19),
                    allowances=[Allowance(Decimal("3.00"))],
                ),
                Line(
                    id="3",
                    name="E-Book",
                    quantity=Decimal(1),
                    net_price=Decimal("10"),
                    vat_category=VatCategory.STANDARD,
                    vat_rate=Decimal(7),
                ),
            ],
        )
        fields.update(overrides)
        return Invoice(**fields)

    return make


@pytest.fixture
def load_json():
    def load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return load
