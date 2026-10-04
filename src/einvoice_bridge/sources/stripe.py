"""Map a Stripe Invoice object to the EN 16931 invoice model.

The mapper is pure: it takes the invoice as Stripe returns it (a dict) plus
the few objects a webhook payload does not carry (tax rates, the payment
method), and returns either an Invoice or a list of problems in German that
tell the seller exactly what to fix in Stripe. It never guesses a tax
category or papers over a total that does not add up.

Both the current Stripe line shape (``taxes`` / ``total_taxes``, API
2025-03-31 and later) and the legacy one (``tax_amounts``) are supported.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ..model import (
    Address,
    Allowance,
    Invoice,
    Line,
    Party,
    Payment,
    VatCategory,
    money,
)
from ..profile import SellerProfile

ZERO_DECIMAL_CURRENCIES = {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf"}

BUYER_REFERENCE_FIELDS = ("leitweg-id", "leitweg_id", "buyer_reference", "käuferreferenz", "kaeuferreferenz")
ORDER_REFERENCE_FIELDS = ("po", "po_number", "order_reference", "bestellnummer", "purchase order")

CARD_MEANS = {"credit": "54", "debit": "55"}


@dataclass
class Problem:
    field: str
    message: str
    severity: str = "error"  # "error" blocks generation; "warning" is informational


@dataclass
class MappingResult:
    invoice: Invoice | None
    problems: list[Problem] = field(default_factory=list)

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == "error"]

    @property
    def ok(self) -> bool:
        return self.invoice is not None and not self.errors


TaxRateLookup = Callable[[str], dict | None]


def _amount(cents: int | None, currency: str) -> Decimal:
    if cents is None:
        return Decimal(0)
    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return Decimal(cents)
    return Decimal(cents) / 100


def _local_date(ts: int | None, tz: ZoneInfo) -> date | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz).date()


def _fields(invoice: dict) -> dict[str, str]:
    """Custom fields and metadata, keyed by lower-cased name."""
    values: dict[str, str] = {}
    for key, value in (invoice.get("metadata") or {}).items():
        if value:
            values[key.strip().lower()] = str(value).strip()
    for custom in invoice.get("custom_fields") or []:
        if custom.get("value"):
            values[custom["name"].strip().lower()] = custom["value"].strip()
    return values


def _first(values: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if values.get(name):
            return values[name]
    return None


def _line_taxes(line: dict) -> list[dict]:
    """Normalise the current ``taxes`` and legacy ``tax_amounts`` shapes."""
    if line.get("taxes") is not None:
        result = []
        for t in line["taxes"]:
            rate = (t.get("tax_rate_details") or {}).get("tax_rate")
            result.append(
                {
                    "amount": t.get("amount", 0),
                    "inclusive": t.get("tax_behavior") == "inclusive",
                    "taxable_amount": t.get("taxable_amount"),
                    "rate": rate,
                    "reason": t.get("taxability_reason"),
                }
            )
        return result
    return [
        {
            "amount": t.get("amount", 0),
            "inclusive": bool(t.get("inclusive")),
            "taxable_amount": t.get("taxable_amount"),
            "rate": t.get("tax_rate"),
            "reason": t.get("taxability_reason"),
        }
        for t in line.get("tax_amounts") or []
    ]


def _rate_percentage(rate: str | dict | None, lookup: TaxRateLookup | None) -> Decimal | None:
    if isinstance(rate, dict):
        obj = rate
    elif isinstance(rate, str) and lookup:
        obj = lookup(rate)
    else:
        obj = None
    if not obj:
        return None
    pct = obj.get("percentage")
    if pct is None:
        pct = obj.get("effective_percentage")
    return Decimal(str(pct)) if pct is not None else None


def _vat_category(
    rate: Decimal, reasons: set[str | None], profile: SellerProfile, invoice: dict
) -> tuple[VatCategory | None, str | None]:
    """Return the EN 16931 VAT category, or an explanation why it is unclear."""
    if rate > 0:
        return VatCategory.STANDARD, None
    if profile.kleinunternehmer:
        return VatCategory.EXEMPT, None
    if "reverse_charge" in reasons or invoice.get("customer_tax_exempt") == "reverse":
        return VatCategory.REVERSE_CHARGE, None
    if "zero_rated" in reasons:
        return VatCategory.ZERO, None
    if reasons & {"product_exempt", "customer_exempt"}:
        return VatCategory.EXEMPT, None
    if reasons & {"not_subject_to_tax", "not_collecting"}:
        return VatCategory.NOT_SUBJECT, None
    return None, (
        "Für diese Position wird keine Umsatzsteuer berechnet, aber Stripe nennt keinen Grund "
        "(z. B. Reverse Charge). Hinterlegen Sie beim Kunden den Steuerstatus oder nutzen Sie Stripe Tax."
    )


def _buyer(invoice: dict, problems: list[Problem]) -> Party:
    addr = invoice.get("customer_address") or {}
    name = invoice.get("customer_name") or ""
    if not name:
        problems.append(Problem("customer_name", "Der Kunde hat keinen Namen in Stripe."))
    for key, label in (("city", "Ort"), ("postal_code", "Postleitzahl"), ("country", "Land")):
        if not addr.get(key):
            problems.append(
                Problem(f"customer_address.{key}", f"In der Rechnungsadresse des Kunden fehlt: {label}.")
            )
    email = invoice.get("customer_email")
    if not email:
        problems.append(
            Problem(
                "customer_email",
                "Der Kunde hat keine E-Mail-Adresse. Sie ist als elektronische Adresse (BT-49) Pflicht.",
            )
        )
    vat_id = next(
        (t["value"] for t in invoice.get("customer_tax_ids") or [] if t.get("type") == "eu_vat"),
        None,
    )
    return Party(
        name=name,
        address=Address(
            city=addr.get("city") or "",
            postcode=addr.get("postal_code") or "",
            country_code=(addr.get("country") or "").upper(),
            line1=addr.get("line1"),
            line2=addr.get("line2"),
            state=addr.get("state"),
        ),
        electronic_address=email,
        vat_id=vat_id,
    )


def _line(
    raw: dict,
    index: int,
    currency: str,
    profile: SellerProfile,
    invoice: dict,
    lookup: TaxRateLookup | None,
    tz: ZoneInfo,
    problems: list[Problem],
) -> Line | None:
    where = f"lines[{index}]"
    quantity = Decimal(1 if raw.get("quantity") is None else raw["quantity"])
    amount = _amount(raw.get("amount"), currency)
    discount = sum((_amount(d.get("amount"), currency) for d in raw.get("discount_amounts") or []), Decimal(0))
    taxes = _line_taxes(raw)

    rates = set()
    for t in taxes:
        pct = _rate_percentage(t["rate"], lookup)
        if pct is None:
            if _amount(t["amount"], currency) == 0:
                pct = Decimal(0)
            else:
                problems.append(Problem(where, "Der Steuersatz der Position konnte nicht ermittelt werden."))
                return None
        rates.add(pct)
    if len(rates) > 1:
        problems.append(
            Problem(where, "Die Position hat mehrere Steuersätze; das lässt EN 16931 pro Position nicht zu.")
        )
        return None
    rate = rates.pop() if rates else Decimal(0)

    category, why = _vat_category(rate, {t["reason"] for t in taxes}, profile, invoice)
    if category is None:
        problems.append(Problem(where, why))
        return None

    inclusive = any(t["inclusive"] for t in taxes)
    tax = sum((_amount(t["amount"], currency) for t in taxes), Decimal(0))
    allowances = []
    if inclusive:
        # Prices include VAT: the net amount after discount is Stripe's taxable
        # amount (or what remains once its tax is taken out).
        taxable = [t["taxable_amount"] for t in taxes if t["taxable_amount"] is not None]
        priced = _amount(sum(taxable), currency) if taxable else amount - discount - tax
    else:
        priced = amount
        if discount:
            allowances.append(Allowance(money(discount)))

    # EN 16931 forbids negative prices (BR-27). Credits such as Stripe's
    # proration line "Unused time on ..." become a negative quantity instead.
    quantity = abs(quantity)
    if priced < 0:
        if allowances:
            problems.append(Problem(where, "Rabatt auf eine Gutschriftsposition wird nicht unterstützt."))
            return None
        quantity = -quantity
    if quantity == 0:
        if priced != 0:
            problems.append(Problem(where, "Position mit Menge 0, aber einem Betrag."))
            return None
        net_price = Decimal(0)
    else:
        net_price = priced / quantity

    # Subscription lines carry a service period; Stripe's end is exclusive.
    # One-off items have start == end, i.e. no period.
    period = raw.get("period") or {}
    start = end = None
    if period.get("start") and period.get("end") and period["end"] > period["start"]:
        start = _local_date(period["start"], tz)
        end = _local_date(period["end"] - 1, tz)

    name = raw.get("description") or "Position"
    if inclusive and discount:
        name = f"{name} (inkl. Rabatt)"
    return Line(
        id=str(index + 1),
        name=name,
        quantity=quantity,
        net_price=net_price.quantize(Decimal("0.000001")),
        vat_category=category,
        vat_rate=rate,
        period_start=start,
        period_end=end,
        allowances=allowances,
    )


def _payment(
    invoice: dict,
    profile: SellerProfile,
    payment_method: dict | None,
    paid: bool,
    problems: list[Problem],
) -> Payment:
    number = invoice.get("number")
    if paid:
        pm_type = (payment_method or {}).get("type")
        if pm_type == "card":
            card = payment_method["card"]
            return Payment(
                means_code=CARD_MEANS.get(card.get("funding"), "54"),
                card_last_digits=card.get("last4"),
                card_network=(card.get("brand") or "card").upper(),
                remittance_info=number,
            )
        if pm_type == "sepa_debit" and profile.creditor_id:
            sepa = payment_method["sepa_debit"]
            mandate = (payment_method.get("mandate") or {}).get("reference") or sepa.get("mandate_reference")
            if mandate:
                return Payment(
                    means_code="59",
                    mandate_reference=mandate,
                    debited_iban=sepa.get("iban") or f"****{sepa.get('last4', '')}",
                    remittance_info=number,
                )
        # Paid through a method EN 16931 has no detailed group for.
        return Payment(means_code="ZZZ", means_text="Bereits bezahlt über Stripe", remittance_info=number)

    if not profile.iban:
        problems.append(
            Problem(
                "seller.iban",
                "Für offene Rechnungen braucht die E-Rechnung Ihre IBAN als Zahlungsweg. "
                "Hinterlegen Sie sie in Ihrem Verkäuferprofil.",
            )
        )
    return Payment(
        means_code="58",
        iban=profile.iban,
        bic=profile.bic,
        account_name=profile.account_name or profile.name,
        remittance_info=number,
    )


def map_invoice(
    invoice: dict,
    profile: SellerProfile,
    tax_rate: TaxRateLookup | None = None,
    payment_method: dict | None = None,
) -> MappingResult:
    problems = [Problem("seller", msg) for msg in profile.problems()]
    tz = ZoneInfo(profile.timezone)
    currency = (invoice.get("currency") or "eur").lower()

    if invoice.get("status") in (None, "draft"):
        problems.append(Problem("status", "Entwürfe werden nicht umgewandelt; erst die finalisierte Rechnung."))
    number = invoice.get("number")
    if not number:
        problems.append(Problem("number", "Die Rechnung hat noch keine Rechnungsnummer."))

    buyer = _buyer(invoice, problems)

    raw_lines = (invoice.get("lines") or {}).get("data") or []
    if (invoice.get("lines") or {}).get("has_more"):
        problems.append(Problem("lines", "Nicht alle Positionen wurden geladen (has_more)."))
    lines = [
        _line(raw, i, currency, profile, invoice, tax_rate, tz, problems) for i, raw in enumerate(raw_lines)
    ]
    if not raw_lines:
        problems.append(Problem("lines", "Die Rechnung hat keine Positionen."))

    issued = invoice.get("status_transitions", {}).get("finalized_at") or invoice.get("effective_at") or invoice.get("created")
    issue_date = _local_date(issued, tz)
    due_date = _local_date(invoice.get("due_date"), tz)

    total = _amount(invoice.get("total"), currency)
    remaining = _amount(invoice.get("amount_remaining", invoice.get("amount_due")), currency)
    paid = invoice.get("status") == "paid" or (total > 0 and remaining == 0)
    payment = _payment(invoice, profile, payment_method, paid, problems)

    values = _fields(invoice)
    buyer_reference = _first(values, BUYER_REFERENCE_FIELDS)
    if not buyer_reference:
        # B2B buyers rarely issue a reference; the customer number is the
        # usual agreed stand-in. Public-sector buyers need their Leitweg-ID.
        customer = invoice.get("customer")
        buyer_reference = customer if isinstance(customer, str) else (customer or {}).get("id")
        problems.append(
            Problem(
                "buyer_reference",
                "Keine Käuferreferenz/Leitweg-ID angegeben; die Stripe-Kundennummer wird verwendet. "
                "Für Behörden muss die Leitweg-ID als Custom Field oder Metadatum „Leitweg-ID“ gesetzt sein.",
                "warning",
            )
        )

    if any(line is None for line in lines) or any(p.severity == "error" for p in problems):
        return MappingResult(None, problems)

    seller = profile.party()
    categories = {line.vat_category for line in lines}
    if VatCategory.NOT_SUBJECT in categories:
        # BR-O-02: no VAT identifiers when the supply is outside the scope of VAT.
        seller = replace(seller, vat_id=None)
        buyer = replace(buyer, vat_id=None)
        if not seller.effective_identifier:
            problems.append(Problem("seller.tax_number", "Für nicht steuerbare Leistungen wird Ihre Steuernummer benötigt."))
            return MappingResult(None, problems)
    if VatCategory.REVERSE_CHARGE in categories and not buyer.vat_id:
        problems.append(Problem("customer_tax_ids", "Für Reverse Charge braucht der Kunde eine USt-IdNr. in Stripe."))
        return MappingResult(None, problems)

    notes = [text for text in (invoice.get("description"), invoice.get("footer")) if text]
    starts = [line.period_start for line in lines if line.period_start]
    ends = [line.period_end for line in lines if line.period_end]

    result = Invoice(
        number=number,
        issue_date=issue_date,
        seller=seller,
        buyer=buyer,
        lines=lines,
        buyer_reference=buyer_reference,
        payment=payment,
        currency=currency.upper(),
        due_date=None if paid else due_date,
        notes=notes,
        order_reference=_first(values, ORDER_REFERENCE_FIELDS),
        period_start=min(starts) if starts else None,
        period_end=max(ends) if ends else None,
        delivery_date=None if starts else issue_date,
    )

    # Keep the tax Stripe actually charged (it rounds per line).
    charged: dict[tuple[VatCategory, Decimal], Decimal] = {}
    for line, raw in zip(lines, raw_lines):
        key = (line.vat_category, line.vat_rate)
        charged[key] = charged.get(key, Decimal(0)) + sum(
            (_amount(t["amount"], currency) for t in _line_taxes(raw)), Decimal(0)
        )
    result.charged_tax = charged

    if result.tax_inclusive_total != money(total):
        problems.append(
            Problem(
                "total",
                f"Die berechnete Summe {result.tax_inclusive_total} weicht von der Stripe-Summe {money(total)} ab "
                "(z. B. durch Rabatte auf Rechnungsebene oder Guthaben). Die Rechnung wird nicht umgewandelt.",
            )
        )
        return MappingResult(None, problems)

    result.paid_amount = money(total - remaining)
    if paid:
        paid_at = _local_date(invoice.get("status_transitions", {}).get("paid_at"), tz)
        result.payment_terms = f"Bereits bezahlt am {paid_at:%d.%m.%Y}." if paid_at else "Bereits bezahlt."
    elif due_date:
        result.payment_terms = f"Zahlbar ohne Abzug bis {due_date:%d.%m.%Y}."
        if invoice.get("hosted_invoice_url"):
            result.payment_terms += f" Online bezahlen: {invoice['hosted_invoice_url']}"
    else:
        result.payment_terms = "Zahlbar sofort ohne Abzug."

    return MappingResult(result, problems)

