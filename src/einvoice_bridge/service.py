"""The automated pipeline: Stripe event -> e-invoice -> validate -> archive -> deliver."""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import asdict
from email.message import EmailMessage
from typing import Protocol

from .billing import current_month, effective_plan, usage
from .model import Invoice
from .pdf import to_zugferd_pdf
from .sources.stripe import MappingResult, Problem, map_credit_note, map_invoice
from .store import Account, Document, Store
from .ubl import to_ubl
from .validation import validate

log = logging.getLogger(__name__)

# Which Stripe event finalises an invoice for our purposes. Auto-charged
# invoices are converted once paid, so the payment method is known and the
# e-invoice can say "bereits bezahlt"; invoices sent for manual payment are
# converted as soon as they are finalised.
HANDLED_EVENTS = {"invoice.finalized", "invoice.paid", "credit_note.created", "credit_note.voided"}


class StripeGateway(Protocol):
    def invoice(self, invoice_id: str) -> dict: ...
    def tax_rate(self, tax_rate_id: str) -> dict | None: ...
    def payment_method(self, invoice: dict) -> dict | None: ...
    def recent_invoices(self, limit: int) -> list[dict]: ...
    def credit_note(self, credit_note_id: str) -> dict: ...
    def recent_credit_notes(self, limit: int) -> list[dict]: ...


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

    def recent_invoices(self, limit: int) -> list[dict]:
        """Newest finalised invoices (open or paid), for the first run after install."""
        page = self.client.v1.invoices.list({"limit": min(100, limit * 3)})
        found = [inv.to_dict() for inv in page.data if inv.get("status") in ("open", "paid")]
        return found[:limit]

    def credit_note(self, credit_note_id: str) -> dict:
        note = self.client.v1.credit_notes.retrieve(credit_note_id).to_dict()
        if (note.get("lines") or {}).get("has_more"):
            lines = [
                line.to_dict()
                for line in self.client.v1.credit_notes.line_items.list(credit_note_id, {"limit": 100}).auto_paging_iter()
            ]
            note["lines"] = {"object": "list", "data": lines, "has_more": False}
        return note

    def recent_credit_notes(self, limit: int) -> list[dict]:
        page = self.client.v1.credit_notes.list({"limit": min(100, limit * 2)})
        return [n.to_dict() for n in page.data if n.get("status") == "issued"][:limit]

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
    if invoice.is_credit_note:
        doc = f"die Rechnungskorrektur {invoice.number} zur Rechnung {invoice.preceding_invoice}"
        msg["Subject"] = f"Rechnungskorrektur {invoice.number} zu Rechnung {invoice.preceding_invoice} von {invoice.seller.name}"
    else:
        doc = f"die Rechnung {invoice.number}"
        msg["Subject"] = f"Rechnung {invoice.number} von {invoice.seller.name}"
    msg["To"] = ", ".join(to)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    msg["Reply-To"] = invoice.seller.contact.email if invoice.seller.contact else invoice.seller.electronic_address
    msg.set_content(
        f"Guten Tag,\n\nanbei erhalten Sie {doc} als E-Rechnung:\n\n"
        f"- {invoice.number}.pdf: ZUGFeRD (PDF mit eingebetteten Rechnungsdaten)\n"
        f"- {invoice.number}.xml: dasselbe Dokument im Format XRechnung\n\n"
        "Beide Dateien enthalten dasselbe Dokument; bitte verbuchen Sie es nur einmal.\n\n"
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
    if event_type.startswith("credit_note."):
        return event_type in HANDLED_EVENTS
    if event_type == "invoice.finalized":
        return invoice.get("collection_method") == "send_invoice"
    # Paid invoices are always (re)considered: this is the first conversion for
    # auto-charged invoices and the retry for send_invoice ones that were
    # blocked at finalisation. process_invoice skips anything already generated.
    return event_type == "invoice.paid"


def process_invoice(
    store: Store,
    account: Account,
    invoice_id: str,
    gateway: StripeGateway,
    mailer: Mailer,
    deliver: bool = True,
    billable: bool = True,
    base_url: str = "",
) -> Document:
    """Convert one Stripe invoice.

    ``deliver=False`` archives without e-mailing; ``billable=False`` does not
    count towards the plan's monthly limit (only the one-time first-run backfill).
    """
    existing = store.document(account.id, invoice_id)
    if existing and existing.status == "generated":
        return existing  # idempotent: Stripe retries webhooks
    if not account.is_active:
        # Installed but onboarding not finished: keep a visible placeholder;
        # the invoice is retried on its next event or from the dashboard.
        problem = {"field": "seller", "message": "Firmendaten fehlen noch. Bitte Einrichtung abschließen.", "severity": "error"}
        return store.save_document(account.id, invoice_id, None, "blocked", [problem])
    if billable:
        used = usage(store, account)
        if used.exhausted:
            # Never drop an invoice silently: keep it visible and retry it
            # automatically when the seller upgrades.
            problem = {
                "field": "plan",
                "message": f"Monatslimit des Tarifs {used.plan.name} erreicht ({used.plan.monthly_limit} E-Rechnungen). "
                "Nach einem Upgrade wird diese Rechnung automatisch umgewandelt.",
                "severity": "error",
            }
            doc = store.save_document(account.id, invoice_id, None, "blocked", [problem], billable=True)
            if deliver and account.limit_notice_month != current_month():
                mailer.send(build_limit_email(account, used.plan.name, used.plan.monthly_limit, base_url))
                store.set_limit_notice(account.id, current_month())
            return doc

    raw = gateway.invoice(invoice_id)
    paid = raw.get("status") == "paid"
    result: MappingResult = map_invoice(
        raw,
        account.profile,
        tax_rate=gateway.tax_rate,
        payment_method=gateway.payment_method(raw) if paid else None,
    )
    return _finish(store, account, invoice_id, raw, result, mailer, deliver, billable)


def process_credit_note(
    store: Store,
    account: Account,
    credit_note_id: str,
    gateway: StripeGateway,
    mailer: Mailer,
    deliver: bool = True,
) -> Document:
    """Convert a Stripe credit note into an e-invoice correction (type 381).

    Corrections never count towards the plan limit and are processed even
    when the limit is reached: a refund must be documented either way.
    """
    existing = store.document(account.id, credit_note_id)
    if existing and existing.status in ("generated", "voided"):
        return existing
    if not account.is_active:
        problem = {"field": "seller", "message": "Firmendaten fehlen noch. Bitte Einrichtung abschließen.", "severity": "error"}
        return store.save_document(account.id, credit_note_id, None, "blocked", [problem], kind="credit_note")

    raw = gateway.credit_note(credit_note_id)
    invoice_ref = raw.get("invoice")
    invoice = gateway.invoice(invoice_ref if isinstance(invoice_ref, str) else invoice_ref["id"])
    refunded = bool(raw.get("refunds") or raw.get("refund"))
    result = map_credit_note(
        raw,
        invoice,
        account.profile,
        tax_rate=gateway.tax_rate,
        payment_method=gateway.payment_method(invoice) if refunded else None,
    )
    return _finish(
        store, account, credit_note_id, raw, result, mailer, deliver, billable=False,
        kind="credit_note", related_number=invoice.get("number"),
    )


def void_credit_note(store: Store, account: Account, credit_note_id: str, mailer: Mailer) -> Document | None:
    """A credit note was voided in Stripe: flag it, and tell the seller if it was already sent."""
    doc = store.mark_voided(
        account.id, credit_note_id,
        "In Stripe storniert. Die bereits erzeugte E-Rechnung bleibt archiviert; "
        "falls sie versendet wurde, informieren Sie bitte Ihren Kunden.",
    )
    if doc and doc.delivered_to and account.profile:
        msg = EmailMessage()
        msg["Subject"] = f"Rechnungskorrektur {doc.number} wurde in Stripe storniert"
        msg["To"] = account.profile.contact.email
        msg.set_content(
            f"Hallo,\n\ndie Rechnungskorrektur {doc.number} zur Rechnung {doc.related_number} wurde in Stripe storniert. "
            f"Die E-Rechnung dazu wurde bereits an {doc.delivered_to} versendet.\n\n"
            "Bitte informieren Sie Ihren Kunden, dass diese Korrektur nicht gilt. "
            "Die Dateien bleiben unverändert im Archiv (Aufbewahrungspflicht).\n"
        )
        mailer.send(msg)
    return doc


def _finish(
    store: Store,
    account: Account,
    stripe_id: str,
    raw: dict,
    result: MappingResult,
    mailer: Mailer,
    deliver: bool,
    billable: bool,
    kind: str = "invoice",
    related_number: str | None = None,
) -> Document:
    """Validate, archive and (optionally) deliver a mapped invoice or credit note."""
    problems = [asdict(p) for p in result.problems]
    meta = {"kind": kind, "related_number": related_number}

    if not result.ok:
        doc = store.save_document(account.id, stripe_id, raw.get("number"), "blocked", problems, **meta)
        if deliver:
            mailer.send(build_fix_list_email(account, raw, result.problems, account.profile.contact.email))
        return doc

    invoice = result.invoice
    xml = to_ubl(invoice)
    pdf = to_zugferd_pdf(invoice)
    findings = []
    for name, report in (("xrechnung.xml", validate(xml)), ("zugferd.pdf", validate(pdf))):
        findings += [{"file": name, **f} for f in report.to_dict()["findings"] if f["severity"] == "error"]
    if findings:
        # Should not happen; never send a document the official rules reject.
        log.error("generated document %s failed validation: %s", stripe_id, findings)
        return store.save_document(account.id, stripe_id, invoice.number, "failed", problems + findings, **meta)

    doc = store.save_document(
        account.id,
        stripe_id,
        invoice.number,
        "generated",
        problems,
        files={"xrechnung.xml": xml, "zugferd.pdf": pdf},
        billable=billable,
        **meta,
    )

    if not deliver:
        return doc
    seller_copy = account.profile.contact.email
    to_customer = account.send_to_customer and effective_plan(account).customer_delivery
    to = [invoice.buyer.electronic_address] if to_customer else [seller_copy]
    bcc = [seller_copy] if to_customer else []
    mailer.send(build_delivery_email(invoice, pdf, xml, to, bcc))
    store.mark_delivered(doc.id, ", ".join(to + bcc))
    return store.document(account.id, stripe_id)


def backfill(
    store: Store,
    account: Account,
    gateway: StripeGateway,
    mailer: Mailer,
    limit: int = 10,
    billable: bool = False,
) -> list[Document]:
    """Convert the newest invoices (archived, not e-mailed).

    Right after setup this is a free preview (``billable=False``) so the
    dashboard is not empty. Run again from the dashboard it counts towards the
    plan. Nothing is e-mailed: these invoices were already sent the old way,
    and sending them again to customers would create duplicates.
    """
    docs = [
        process_invoice(store, account, raw["id"], gateway, mailer, deliver=False, billable=billable)
        for raw in gateway.recent_invoices(limit)
    ]
    docs += [
        process_credit_note(store, account, raw["id"], gateway, mailer, deliver=False)
        for raw in gateway.recent_credit_notes(limit)
    ]
    return docs


def retry_limited(store: Store, account: Account, gateway: StripeGateway, mailer: Mailer, base_url: str = "") -> list[Document]:
    """After an upgrade, convert and deliver invoices that were held back by the old limit."""
    held = [d for d in store.documents(account.id) if d.status == "blocked" and any(p.get("field") == "plan" for p in d.problems)]
    results = []
    for doc in reversed(held):  # oldest first
        account = store.account(account.id)
        results.append(process_invoice(store, account, doc.stripe_invoice_id, gateway, mailer, base_url=base_url))
    return results


def build_limit_email(account: Account, plan_name: str, limit: int, base_url: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Monatslimit erreicht: {limit} E-Rechnungen im Tarif {plan_name}"
    msg["To"] = account.profile.contact.email
    msg.set_content(
        f"Hallo,\n\nIhr Tarif {plan_name} enthält {limit} E-Rechnungen pro Monat, und dieses Limit ist erreicht. "
        "Weitere Stripe-Rechnungen werden gespeichert, aber erst nach einem Upgrade umgewandelt und zugestellt; "
        "das passiert dann automatisch.\n\n"
        f"Tarif wechseln: {base_url}/konto/abo\n"
    )
    return msg
