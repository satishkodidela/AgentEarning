"""The automated pipeline: Stripe event -> e-invoice -> validate -> archive -> deliver."""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import asdict
from email.message import EmailMessage
from typing import Protocol

from .model import Invoice
from .pdf import to_zugferd_pdf
from .sources.stripe import MappingResult, Problem, map_invoice
from .store import Account, Document, Store
from .ubl import to_ubl
from .validation import validate

log = logging.getLogger(__name__)

# Which Stripe event finalises an invoice for our purposes. Auto-charged
# invoices are converted once paid, so the payment method is known and the
# e-invoice can say "bereits bezahlt"; invoices sent for manual payment are
# converted as soon as they are finalised.
HANDLED_EVENTS = {"invoice.finalized", "invoice.paid"}


class StripeGateway(Protocol):
    def invoice(self, invoice_id: str) -> dict: ...
    def tax_rate(self, tax_rate_id: str) -> dict | None: ...
    def payment_method(self, invoice: dict) -> dict | None: ...


class LiveStripeGateway:
    """Reads from the seller's Stripe account with their restricted key."""

    def __init__(self, api_key: str):
        import stripe

        self.client = stripe.StripeClient(api_key)
        self._rates: dict[str, dict | None] = {}

    def invoice(self, invoice_id: str) -> dict:
        invoice = self.client.v1.invoices.retrieve(invoice_id).to_dict()
        lines = invoice.get("lines") or {}
        if lines.get("has_more"):
            all_lines = [
                line.to_dict()
                for line in self.client.v1.invoices.line_items.list(invoice_id, {"limit": 100}).auto_paging_iter()
            ]
            invoice["lines"] = {"object": "list", "data": all_lines, "has_more": False}
        return invoice

    def tax_rate(self, tax_rate_id: str) -> dict | None:
        if tax_rate_id not in self._rates:
            try:
                self._rates[tax_rate_id] = self.client.v1.tax_rates.retrieve(tax_rate_id).to_dict()
            except Exception:  # noqa: BLE001 - reported to the seller as an unknown rate
                log.exception("could not load tax rate %s", tax_rate_id)
                self._rates[tax_rate_id] = None
        return self._rates[tax_rate_id]

    def payment_method(self, invoice: dict) -> dict | None:
        """Best effort: the payment method of the payment that settled the invoice."""
        try:
            intent_id = None
            payments = self.client.v1.invoice_payments.list({"invoice": invoice["id"], "limit": 10})
            for payment in payments.data:
                payment = payment.to_dict()
                details = payment.get("payment") or {}
                if payment.get("status") == "paid" and details.get("payment_intent"):
                    intent_id = details["payment_intent"]
                    break
            intent_id = intent_id or invoice.get("payment_intent")
            if not intent_id:
                return None
            intent = self.client.v1.payment_intents.retrieve(intent_id, {"expand": ["payment_method"]}).to_dict()
            method = intent.get("payment_method")
            return method if isinstance(method, dict) else None
        except Exception:  # noqa: BLE001 - falls back to "paid via Stripe"
            log.exception("could not load payment method for %s", invoice.get("id"))
            return None


class Mailer(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpMailer:
    """Sends through the SMTP server in SMTP_HOST/PORT/USER/PASSWORD."""

    def __init__(self) -> None:
        self.host = os.environ.get("SMTP_HOST")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.user = os.environ.get("SMTP_USER")
        self.password = os.environ.get("SMTP_PASSWORD")
        self.sender = os.environ.get("SMTP_FROM", self.user or "")

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)

    def send(self, message: EmailMessage) -> None:
        if not self.configured:
            log.warning("SMTP not configured; not sending %r", message["Subject"])
            return
        if not message["From"]:
            message["From"] = self.sender
        with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
            smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password or "")
            smtp.send_message(message)


def build_delivery_email(invoice: Invoice, pdf: bytes, xml: bytes, to: list[str], bcc: list[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Rechnung {invoice.number} von {invoice.seller.name}"
    msg["To"] = ", ".join(to)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Reply-To"] = invoice.seller.contact.email if invoice.seller.contact else invoice.seller.electronic_address
    msg.set_content(
        f"Guten Tag,\n\nanbei erhalten Sie die Rechnung {invoice.number} als E-Rechnung:\n\n"
        f"- {invoice.number}.pdf: ZUGFeRD-Rechnung (PDF mit eingebetteten Rechnungsdaten)\n"
        f"- {invoice.number}.xml: dieselbe Rechnung im Format XRechnung\n\n"
        "Beide Dateien enthalten dieselbe Rechnung; bitte verbuchen Sie sie nur einmal.\n\n"
        f"Mit freundlichen Grüßen\n{invoice.seller.name}\n"
    )
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"{invoice.number}.pdf")
    msg.add_attachment(xml, maintype="application", subtype="xml", filename=f"{invoice.number}.xml")
    return msg


def build_fix_list_email(account: Account, invoice: dict, problems: list[Problem], to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"E-Rechnung für {invoice.get('number') or invoice.get('id')} konnte nicht erstellt werden"
    msg["To"] = to
    items = "\n".join(f"- {p.message}" for p in problems if p.severity == "error")
    msg.set_content(
        "Hallo,\n\nfür diese Stripe-Rechnung konnte noch keine gültige E-Rechnung erstellt werden. "
        f"Bitte korrigieren Sie in Stripe bzw. in Ihrem Profil:\n\n{items}\n\n"
        "Danach wird die Rechnung beim nächsten Ereignis automatisch erneut verarbeitet.\n"
    )
    return msg


def should_process(event_type: str, invoice: dict) -> bool:
    if event_type == "invoice.finalized":
        return invoice.get("collection_method") == "send_invoice"
    if event_type == "invoice.paid":
        return invoice.get("collection_method") != "send_invoice"
    return False


def process_invoice(
    store: Store, account: Account, invoice_id: str, gateway: StripeGateway, mailer: Mailer
) -> Document:
    existing = store.document(account.id, invoice_id)
    if existing and existing.status == "generated":
        return existing  # idempotent: Stripe retries webhooks

    raw = gateway.invoice(invoice_id)
    paid = raw.get("status") == "paid"
    result: MappingResult = map_invoice(
        raw,
        account.profile,
        tax_rate=gateway.tax_rate,
        payment_method=gateway.payment_method(raw) if paid else None,
    )
    problems = [asdict(p) for p in result.problems]

    if not result.ok:
        doc = store.save_document(account.id, invoice_id, raw.get("number"), "blocked", problems)
        mailer.send(build_fix_list_email(account, raw, result.problems, account.profile.contact.email))
        return doc

    invoice = result.invoice
    xml = to_ubl(invoice)
    pdf = to_zugferd_pdf(invoice)
    findings = []
    for name, report in (("xrechnung.xml", validate(xml)), ("zugferd.pdf", validate(pdf))):
        findings += [{"file": name, **f} for f in report.to_dict()["findings"] if f["severity"] == "error"]
    if findings:
        # Should not happen; never send an invoice the official rules reject.
        log.error("generated invoice %s failed validation: %s", invoice_id, findings)
        return store.save_document(account.id, invoice_id, invoice.number, "failed", problems + findings)

    doc = store.save_document(
        account.id,
        invoice_id,
        invoice.number,
        "generated",
        problems,
        files={"xrechnung.xml": xml, "zugferd.pdf": pdf},
    )

    seller_copy = account.profile.contact.email
    to = [invoice.buyer.electronic_address] if account.send_to_customer else [seller_copy]
    bcc = [seller_copy] if account.send_to_customer else []
    mailer.send(build_delivery_email(invoice, pdf, xml, to, bcc))
    store.mark_delivered(doc.id, ", ".join(to + bcc))
    return store.document(account.id, invoice_id)
