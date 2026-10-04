"""Render the human-readable invoice PDF and embed the XML (ZUGFeRD).

The visual PDF is built with fpdf2 in PDF/A-3B mode with embedded fonts;
factur-x then attaches the EN 16931 CII XML and writes the Factur-X /
ZUGFeRD XMP metadata, producing a hybrid invoice that opens as a normal PDF
and is processed automatically by accounting software.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

from .cii import to_cii
from .model import Invoice, VatCategory, fmt_decimal, money

FONTS = Path(__file__).parent / "fonts"

# A seller's credit note (381) is titled "Rechnungskorrektur": in German VAT law
# "Gutschrift" means self-billing by the buyer (§ 14 Abs. 2 UStG), and using it
# for a seller's correction invites confusion with the tax office.
TYPE_TITLES = {"380": "Rechnung", "381": "Rechnungskorrektur", "384": "Rechnungskorrektur", "326": "Teilrechnung"}
MEANS_TEXT = {
    "58": "SEPA-Überweisung",
    "30": "Überweisung",
    "59": "SEPA-Lastschrift",
    "54": "Kreditkarte",
    "55": "Debitkarte",
    "48": "Kartenzahlung",
}


def eur(value: Decimal, currency: str = "EUR") -> str:
    text = f"{money(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €" if currency == "EUR" else f"{text} {currency}"


def de_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def de_number(value: Decimal) -> str:
    return fmt_decimal(value).replace(".", ",")


class _InvoicePDF(FPDF):
    def __init__(self, footer_lines: list[str]):
        super().__init__(format="A4", enforce_compliance="PDF/A-3B")
        self.footer_lines = footer_lines
        self.add_font("DejaVu", "", str(FONTS / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(True, margin=30)
        self.set_margins(20, 15, 20)

    def footer(self) -> None:
        self.set_y(-25)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(90, 90, 90)
        for line in self.footer_lines:
            self.cell(0, 3.5, line, align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 3.5, f"Seite {self.page_no()}/{{nb}}", align="C")


def render_visual_pdf(invoice: Invoice) -> bytes:
    s, b = invoice.seller, invoice.buyer
    footer = [
        " · ".join(
            x
            for x in (
                s.name,
                s.address.line1,
                f"{s.address.postcode} {s.address.city}",
                s.contact.email if s.contact else s.electronic_address,
                s.contact.phone if s.contact else None,
            )
            if x
        ),
        " · ".join(
            x
            for x in (
                f"USt-IdNr. {s.vat_id}" if s.vat_id else None,
                f"Steuernummer {s.tax_number}" if s.tax_number else None,
                s.legal_registration_id,
                f"IBAN {invoice.payment.iban}" if invoice.payment.iban else None,
            )
            if x
        ),
        "Dieses Dokument enthält eine maschinenlesbare E-Rechnung (ZUGFeRD / Factur-X, Profil EN 16931).",
    ]
    pdf = _InvoicePDF(footer)
    pdf.set_title(f"{TYPE_TITLES.get(invoice.type_code, 'Rechnung')} {invoice.number}")
    pdf.set_author(s.name)
    pdf.set_lang("de-DE")
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 13)
    pdf.cell(0, 7, s.trading_name or s.name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(90, 90, 90)
    pdf.set_y(45)
    pdf.cell(0, 4, f"{s.name} · {s.address.line1 or ''} · {s.address.postcode} {s.address.city}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", 10)
    buyer_lines = [b.name, b.address.line1, b.address.line2, f"{b.address.postcode} {b.address.city}"]
    if b.address.country_code != "DE":
        buyer_lines.append(b.address.country_code)
    for line in filter(None, buyer_lines):
        pdf.cell(85, 5, line, new_x="LMARGIN", new_y="NEXT")

    meta = [
        ("Korrekturnummer" if invoice.is_credit_note else "Rechnungsnummer", invoice.number),
        ("Datum" if invoice.is_credit_note else "Rechnungsdatum", de_date(invoice.issue_date)),
    ]
    if invoice.period_start:
        meta.append(("Leistungszeitraum", f"{de_date(invoice.period_start)} – {de_date(invoice.period_end)}"))
    elif invoice.delivery_date:
        meta.append(("Leistungsdatum", de_date(invoice.delivery_date)))
    if invoice.due_date:
        meta.append(("Fällig am", de_date(invoice.due_date)))
    meta.append(("Ihre Referenz", invoice.buyer_reference))
    if invoice.order_reference:
        meta.append(("Bestellnummer", invoice.order_reference))
    if b.vat_id:
        meta.append(("Ihre USt-IdNr.", b.vat_id))
    if invoice.preceding_invoice:
        meta.append(("Zu Rechnung", invoice.preceding_invoice))
        if invoice.preceding_invoice_date:
            meta.append(("vom", de_date(invoice.preceding_invoice_date)))
    y = 50
    pdf.set_font("DejaVu", "", 8.5)
    for label, value in meta:
        pdf.set_xy(120, y)
        pdf.cell(32, 4.5, label)
        pdf.cell(38, 4.5, value, align="R")
        y += 4.5

    pdf.set_y(max(pdf.get_y(), y) + 12)
    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 8, f"{TYPE_TITLES.get(invoice.type_code, 'Rechnung')} {invoice.number}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 9)
    for note in invoice.notes:
        pdf.multi_cell(0, 4.5, note, align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    widths = (10, 72, 16, 26, 16, 30)
    headers = ("Pos.", "Bezeichnung", "Menge", "Einzelpreis", "USt.", "Betrag (netto)")
    pdf.set_font("DejaVu", "B", 8.5)
    pdf.set_fill_color(240, 240, 240)
    for w, h, align in zip(widths, headers, "LLRRRR"):
        pdf.cell(w, 6, h, align=align, fill=True)
    pdf.ln()
    pdf.set_font("DejaVu", "", 8.5)
    cur = invoice.currency
    for line in invoice.lines:
        top = pdf.get_y()
        pdf.set_x(pdf.l_margin + widths[0])
        text = line.name
        if line.period_start and line.period_end:
            text += f"\nZeitraum {de_date(line.period_start)} – {de_date(line.period_end)}"
        if line.description:
            text += f"\n{line.description}"
        pdf.multi_cell(widths[1], 4.5, text, align="L", new_x="RIGHT", new_y="TOP")
        bottom = pdf.get_y() if pdf.get_y() > top else top
        pdf.set_xy(pdf.l_margin, top)
        pdf.cell(widths[0], 4.5, line.id)
        pdf.set_x(pdf.l_margin + widths[0] + widths[1])
        pdf.cell(widths[2], 4.5, de_number(line.quantity), align="R")
        pdf.cell(widths[3], 4.5, eur(line.net_price, cur) if line.net_price == money(line.net_price) else f"{de_number(line.net_price)} {cur}", align="R")
        pdf.cell(widths[4], 4.5, f"{de_number(line.vat_rate)} %", align="R")
        pdf.cell(widths[5], 4.5, eur(money(line.quantity * line.net_price), cur), align="R")
        lines_used = text.count("\n") + 1
        pdf.set_y(max(bottom, top + 4.5 * lines_used))
        for allowance in line.allowances:
            pdf.set_x(pdf.l_margin + widths[0])
            pdf.cell(sum(widths[1:5]), 4.5, f"abzüglich {allowance.reason}")
            pdf.cell(widths[5], 4.5, f"-{eur(allowance.amount, cur)}", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(220, 220, 220)
        pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.l_margin + sum(widths), pdf.get_y() + 1)
        pdf.ln(2)

    def total_row(label: str, value: str, bold: bool = False) -> None:
        pdf.set_font("DejaVu", "B" if bold else "", 9)
        pdf.set_x(pdf.l_margin + 80)
        pdf.cell(sum(widths) - 80 - 30, 5.5, label)
        pdf.cell(30, 5.5, value, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    total_row("Summe netto", eur(invoice.line_total, cur))
    reasons = []
    for vb in invoice.vat_breakdown():
        if vb.category in (VatCategory.STANDARD, VatCategory.ZERO):
            total_row(f"USt. {de_number(vb.rate)} % auf {eur(vb.taxable_amount, cur)}", eur(vb.tax_amount, cur))
        elif vb.exemption_reason:
            reasons.append(vb.exemption_reason)
    total_row("Korrekturbetrag" if invoice.is_credit_note else "Gesamtbetrag", eur(invoice.tax_inclusive_total, cur), bold=True)
    if invoice.paid_amount:
        total_row("Bereits bezahlt", f"-{eur(invoice.paid_amount, cur)}")
        total_row("Zahlbetrag", eur(invoice.amount_due, cur), bold=True)

    pdf.ln(4)
    pdf.set_font("DejaVu", "", 9)
    for reason in reasons:
        pdf.multi_cell(0, 4.5, reason, align="L", new_x="LMARGIN", new_y="NEXT")
    pay = invoice.payment
    if invoice.payment_terms:
        pdf.multi_cell(0, 4.5, invoice.payment_terms, align="L", new_x="LMARGIN", new_y="NEXT")
    if pay.iban and invoice.amount_due > 0 and not invoice.is_credit_note:
        details = f"Bitte überweisen Sie den Betrag auf: IBAN {pay.iban}"
        if pay.bic:
            details += f", BIC {pay.bic}"
        if pay.remittance_info:
            details += f". Verwendungszweck: {pay.remittance_info}"
        pdf.multi_cell(0, 4.5, details, align="L", new_x="LMARGIN", new_y="NEXT")
    elif pay.card_last_digits and not invoice.is_credit_note:  # credit notes say how they are refunded
        pdf.multi_cell(
            0, 4.5, f"Zahlungsart: {MEANS_TEXT.get(pay.means_code, 'Karte')} (**** {pay.card_last_digits})",
            new_x="LMARGIN", new_y="NEXT",
        )
    elif pay.mandate_reference:
        pdf.multi_cell(
            0, 4.5, f"Der Betrag wird per SEPA-Lastschrift eingezogen (Mandat {pay.mandate_reference}).",
            new_x="LMARGIN", new_y="NEXT",
        )

    return bytes(pdf.output())


def to_zugferd_pdf(invoice: Invoice) -> bytes:
    """Hybrid PDF/A-3 with the EN 16931 CII XML embedded as factur-x.xml."""
    from facturx import generate_from_binary

    visual = render_visual_pdf(invoice)
    xml = to_cii(invoice, "en16931")
    title = f"{TYPE_TITLES.get(invoice.type_code, 'Rechnung')} {invoice.number}"
    return generate_from_binary(
        visual,
        xml,
        flavor="factur-x",
        level="en16931",
        check_xsd=True,
        pdf_metadata={
            "author": invoice.seller.name,
            "keywords": "Factur-X, ZUGFeRD, E-Rechnung",
            "title": title,
            "subject": f"{title} von {invoice.seller.name}",
        },
        lang="de-DE",
    )
