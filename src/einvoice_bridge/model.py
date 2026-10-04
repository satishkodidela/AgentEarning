"""Semantic invoice model following EN 16931 business terms (BT-/BG- numbers).

Generators for UBL and CII both render from this model, so totals are
computed in exactly one place, with the rounding rules the validators check.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

CENT = Decimal("0.01")

XRECHNUNG_CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
EN16931_CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017"
PEPPOL_PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_amount(value: Decimal) -> str:
    return f"{money(value):.2f}"


def fmt_decimal(value: Decimal) -> str:
    """Render quantities, prices and rates without trailing zeros."""
    text = format(Decimal(value).normalize(), "f")
    return text if text not in ("-0", "") else "0"


class VatCategory(str, Enum):
    STANDARD = "S"
    ZERO = "Z"
    EXEMPT = "E"  # e.g. Kleinunternehmer (§ 19 UStG)
    REVERSE_CHARGE = "AE"
    INTRA_COMMUNITY = "K"
    EXPORT = "G"
    NOT_SUBJECT = "O"


# Wording that German tax offices and recipients expect when no VAT is charged.
DEFAULT_EXEMPTION_REASONS = {
    VatCategory.EXEMPT: "Kein Ausweis von Umsatzsteuer, da Kleinunternehmer gemäß § 19 UStG",
    VatCategory.REVERSE_CHARGE: "Steuerschuldnerschaft des Leistungsempfängers",
    VatCategory.INTRA_COMMUNITY: "Steuerfreie innergemeinschaftliche Lieferung",
    VatCategory.EXPORT: "Steuerfreie Ausfuhrlieferung",
    VatCategory.NOT_SUBJECT: "Nicht im Inland steuerbare Leistung",
}

DEFAULT_EXEMPTION_CODES = {
    VatCategory.REVERSE_CHARGE: "VATEX-EU-AE",
    VatCategory.INTRA_COMMUNITY: "VATEX-EU-IC",
    VatCategory.EXPORT: "VATEX-EU-G",
    VatCategory.NOT_SUBJECT: "VATEX-EU-O",
}


@dataclass
class Address:
    city: str
    postcode: str
    country_code: str  # ISO 3166-1 alpha-2
    line1: str | None = None
    line2: str | None = None
    state: str | None = None


@dataclass
class Contact:
    name: str
    phone: str
    email: str


@dataclass
class Party:
    name: str  # BT-27 / BT-44 (registered name)
    address: Address
    electronic_address: str | None = None  # BT-34 / BT-49
    electronic_address_scheme: str = "EM"  # EM = e-mail
    vat_id: str | None = None  # BT-31 / BT-48
    tax_number: str | None = None  # BT-32 (Steuernummer), seller only
    trading_name: str | None = None  # BT-28 / BT-45
    legal_registration_id: str | None = None  # BT-30 / BT-47 (e.g. HRB)
    contact: Contact | None = None  # BG-6 / BG-9
    creditor_id: str | None = None  # BT-90 SEPA creditor identifier, seller only
    identifier: str | None = None  # BT-29 / BT-46

    @property
    def effective_identifier(self) -> str | None:
        """BT-29, falling back to the Steuernummer.

        BR-CO-26 needs BT-29, BT-30 or BT-31 for the seller. Kleinunternehmer
        often have neither a VAT ID nor a register entry, only a Steuernummer,
        which is the identifier German recipients then use.
        """
        if self.identifier or self.vat_id or self.legal_registration_id:
            return self.identifier
        return self.tax_number


@dataclass
class Allowance:
    amount: Decimal
    reason: str = "Rabatt"


@dataclass
class Line:
    id: str
    name: str  # BT-153
    quantity: Decimal  # BT-129
    net_price: Decimal  # BT-146, per unit after price discounts
    vat_category: VatCategory
    vat_rate: Decimal  # BT-152, percent
    unit_code: str = "C62"  # UN/ECE Rec 20, C62 = one (unit)
    description: str | None = None  # BT-154
    period_start: date | None = None  # BT-134
    period_end: date | None = None  # BT-135
    allowances: list[Allowance] = field(default_factory=list)

    @property
    def allowance_total(self) -> Decimal:
        return money(sum((a.amount for a in self.allowances), Decimal(0)))

    @property
    def net_amount(self) -> Decimal:  # BT-131
        return money(self.quantity * self.net_price) - self.allowance_total


@dataclass
class Payment:
    """BG-16 payment instructions. means_code is UNTDID 4461."""

    means_code: str
    means_text: str | None = None  # BT-82
    remittance_info: str | None = None  # BT-83 (Verwendungszweck)
    iban: str | None = None  # BT-84, credit transfer (codes 30/58)
    account_name: str | None = None  # BT-85
    bic: str | None = None  # BT-86
    card_last_digits: str | None = None  # BT-87, card payment (codes 48/54/55)
    card_network: str | None = None
    card_holder: str | None = None  # BT-88
    mandate_reference: str | None = None  # BT-89, direct debit (code 59)
    debited_iban: str | None = None  # BT-91


@dataclass
class VatBreakdown:
    category: VatCategory
    rate: Decimal
    taxable_amount: Decimal  # BT-116
    tax_amount: Decimal  # BT-117
    exemption_reason: str | None = None  # BT-120
    exemption_code: str | None = None  # BT-121


@dataclass
class Invoice:
    number: str  # BT-1
    issue_date: date  # BT-2
    seller: Party
    buyer: Party
    lines: list[Line]
    buyer_reference: str  # BT-10 (Leitweg-ID for public buyers)
    payment: Payment
    type_code: str = "380"  # BT-3: 380 invoice, 381 credit note, 384 corrected
    currency: str = "EUR"  # BT-5
    due_date: date | None = None  # BT-9
    payment_terms: str | None = None  # BT-20
    notes: list[str] = field(default_factory=list)  # BT-22
    order_reference: str | None = None  # BT-13
    preceding_invoice: str | None = None  # BT-25
    preceding_invoice_date: date | None = None  # BT-26
    delivery_date: date | None = None  # BT-72
    period_start: date | None = None  # BT-73
    period_end: date | None = None  # BT-74
    paid_amount: Decimal = Decimal(0)  # BT-113
    exemption_reasons: dict[VatCategory, str] = field(default_factory=dict)
    # Tax per (category, rate) as actually charged, e.g. by Stripe Tax, which
    # rounds per line. Must stay within EN 16931's one-unit tolerance (BR-CO-17).
    charged_tax: dict[tuple[VatCategory, Decimal], Decimal] = field(default_factory=dict)

    @property
    def is_direct_debit(self) -> bool:
        return self.payment.means_code == "59"

    @property
    def is_credit_note(self) -> bool:
        return self.type_code == "381"

    @property
    def line_total(self) -> Decimal:  # BT-106
        return money(sum((line.net_amount for line in self.lines), Decimal(0)))

    @property
    def tax_exclusive_total(self) -> Decimal:  # BT-109 (no document-level allowances)
        return self.line_total

    def vat_breakdown(self) -> list[VatBreakdown]:  # BG-23
        groups: dict[tuple[VatCategory, Decimal], Decimal] = defaultdict(Decimal)
        for line in self.lines:
            groups[(line.vat_category, Decimal(line.vat_rate))] += line.net_amount
        result = []
        for (category, rate), taxable in sorted(groups.items(), key=lambda kv: (kv[0][0].value, kv[0][1])):
            computed = money(taxable * rate / 100)
            tax = money(self.charged_tax.get((category, rate), computed))
            reason = code = None
            if category != VatCategory.STANDARD and category != VatCategory.ZERO:
                reason = self.exemption_reasons.get(category) or DEFAULT_EXEMPTION_REASONS.get(category)
                code = DEFAULT_EXEMPTION_CODES.get(category)
            result.append(VatBreakdown(category, rate, money(taxable), tax, reason, code))
        return result

    @property
    def tax_total(self) -> Decimal:  # BT-110
        return money(sum((b.tax_amount for b in self.vat_breakdown()), Decimal(0)))

    @property
    def tax_inclusive_total(self) -> Decimal:  # BT-112
        return self.tax_exclusive_total + self.tax_total

    @property
    def amount_due(self) -> Decimal:  # BT-115
        return self.tax_inclusive_total - money(self.paid_amount)
