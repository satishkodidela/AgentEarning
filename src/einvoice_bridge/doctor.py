"""`einvoice-bridge doctor`: check a server's configuration before going live.

Every check prints one line: OK, a warning (works, but not ready for paying
customers) or an error (the app will not work). Secrets are never printed.
"""

from __future__ import annotations

import os
import smtplib
import sys
import tempfile
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path

OK, WARN, FAIL = "ok", "warn", "fail"
SYMBOL = {OK: "✓", WARN: "!", FAIL: "✗"}
LEGAL_PAGES = ("impressum", "datenschutz", "agb", "rueckerstattung")


@dataclass
class Report:
    lines: list[tuple[str, str, str]] = field(default_factory=list)

    def add(self, status: str, topic: str, message: str) -> None:
        self.lines.append((status, topic, message))

    @property
    def failed(self) -> bool:
        return any(status == FAIL for status, _, _ in self.lines)

    def print(self, out=sys.stdout) -> None:
        for status, topic, message in self.lines:
            print(f"{SYMBOL[status]} {topic:<14} {message}", file=out)
        fails = sum(s == FAIL for s, _, _ in self.lines)
        warns = sum(s == WARN for s, _, _ in self.lines)
        print(f"\n{fails} Fehler, {warns} Warnungen.", file=out)


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def check_runtime(report: Report) -> None:
    if sys.version_info >= (3, 11):
        report.add(OK, "Python", sys.version.split()[0])
    else:
        report.add(FAIL, "Python", f"{sys.version.split()[0]} – 3.11 oder neuer nötig")


def check_storage(report: Report) -> None:
    from cryptography.fernet import Fernet

    secret = _env("EINVOICE_SECRET_KEY")
    if not secret:
        report.add(FAIL, "Schlüssel", "EINVOICE_SECRET_KEY fehlt (einvoice-bridge secret)")
        return
    try:
        Fernet(secret.encode())
    except ValueError:
        report.add(FAIL, "Schlüssel", "EINVOICE_SECRET_KEY ist kein gültiger Fernet-Schlüssel")
        return
    report.add(OK, "Schlüssel", "gesetzt (gesichert? ohne ihn sind gespeicherte Stripe-Schlüssel verloren)")

    data = Path(_env("EINVOICE_DATA_DIR") or "data")
    try:
        data.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data):
            pass
        from .store import Store

        store = Store(data, secret)
        accounts = store.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        report.add(OK, "Datenbank", f"{data.resolve()} beschreibbar, {accounts} Konten")
    except Exception as exc:  # noqa: BLE001
        report.add(FAIL, "Datenbank", f"{data}: {exc}")


def check_web(report: Report) -> None:
    base = _env("EINVOICE_BASE_URL")
    if not base:
        report.add(FAIL, "Adresse", "EINVOICE_BASE_URL fehlt, z. B. https://erechnungsbote.de")
    elif not base.startswith("https://"):
        report.add(WARN, "Adresse", f"{base} – ohne HTTPS sind Login-Cookies nicht geschützt")
    else:
        report.add(OK, "Adresse", base)
    contact = _env("EINVOICE_CONTACT_EMAIL")
    report.add(OK if contact else WARN, "Kontakt", contact or "EINVOICE_CONTACT_EMAIL fehlt (Kontaktseite, Paddle-Prüfung)")

    legal = Path(_env("EINVOICE_LEGAL_DIR") or "legal")
    missing = [name for name in LEGAL_PAGES if not (legal / f"{name}.html").is_file()]
    if missing:
        report.add(WARN, "Rechtstexte", f"fehlen in {legal}: {', '.join(m + '.html' for m in missing)} (Pflicht vor dem Livegang)")
    else:
        report.add(OK, "Rechtstexte", f"alle vier in {legal}")


def check_engine(report: Report) -> None:
    try:
        from .validation import ARTIFACTS, validate

        sample = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "official" / "01.01a-INVOICE_ubl.xml"
        if sample.is_file():
            xml = sample.read_bytes()
        else:  # installed without tests: build a minimal invoice instead
            xml = _sample_invoice_xml()
        result = validate(xml)
        import json
        from importlib.metadata import version

        rules = json.loads((ARTIFACTS / "VERSIONS.json").read_text())
        if result.valid:
            report.add(
                OK, "Prüfregeln",
                f"XRechnung {rules['xrechnung']} / Schematron {rules['xrechnung_schematron']} aktiv (saxonche {version('saxonche')})",
            )
        else:
            report.add(FAIL, "Prüfregeln", f"Musterrechnung wurde abgelehnt: {[f.rule_id for f in result.errors][:5]}")
    except Exception as exc:  # noqa: BLE001
        report.add(FAIL, "Prüfregeln", f"Validator startet nicht: {exc}")

    try:
        from .pdf import to_zugferd_pdf
        from .sources.stripe import map_invoice  # noqa: F401  (import check)

        pdf = to_zugferd_pdf(_sample_invoice())
        report.add(OK, "PDF", f"ZUGFeRD-PDF erzeugt ({len(pdf) // 1024} KB)")
    except Exception as exc:  # noqa: BLE001
        report.add(FAIL, "PDF", f"PDF-Erzeugung fehlgeschlagen: {exc}")


def check_smtp(report: Report, connect: bool, send_to: str | None) -> None:
    host, user, sender = _env("SMTP_HOST"), _env("SMTP_USER"), _env("SMTP_FROM")
    if not host or not sender:
        report.add(FAIL, "E-Mail", "SMTP_HOST/SMTP_FROM fehlen – E-Rechnungen werden nicht versendet")
        return
    if not _env("SMTP_PASSWORD"):
        report.add(FAIL, "E-Mail", f"SMTP_PASSWORD fehlt für {user or host}")
        return
    if not connect and not send_to:
        report.add(OK, "E-Mail", f"{host} als {user} (Verbindung mit --smtp testen)")
        return
    try:
        with smtplib.SMTP(host, int(_env("SMTP_PORT") or 587), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(user, _env("SMTP_PASSWORD"))
            if send_to:
                msg = EmailMessage()
                msg["Subject"] = "E-Rechnungsbote: Test-E-Mail"
                msg["From"] = sender
                msg["To"] = send_to
                msg.set_content("Der E-Mail-Versand vom Server funktioniert.\n")
                smtp.send_message(msg)
        report.add(OK, "E-Mail", f"Anmeldung bei {host} erfolgreich" + (f", Test an {send_to} gesendet" if send_to else ""))
    except Exception as exc:  # noqa: BLE001
        report.add(FAIL, "E-Mail", f"{host}: {exc}")


def check_stripe(report: Report) -> None:
    key, link, client_id, hook = (
        _env("STRIPE_APP_SECRET_KEY"), _env("STRIPE_APP_INSTALL_LINK"), _env("STRIPE_APP_CLIENT_ID"),
        _env("STRIPE_CONNECT_WEBHOOK_SECRET"),
    )
    if not (key or link or client_id or hook):
        report.add(WARN, "Stripe-App", "nicht eingerichtet – Kunden können sich noch nicht verbinden")
        return
    problems = []
    if not key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
        problems.append("STRIPE_APP_SECRET_KEY fehlt oder hat ein unbekanntes Format")
    if not (link or client_id):
        problems.append("STRIPE_APP_INSTALL_LINK oder STRIPE_APP_CLIENT_ID fehlt")
    if not hook.startswith("whsec_"):
        problems.append("STRIPE_CONNECT_WEBHOOK_SECRET fehlt")
    if problems:
        report.add(FAIL, "Stripe-App", "; ".join(problems))
        return
    mode = "Test" if "_test_" in key else "Live"
    if mode == "Live" and "chnlink_" in link:
        report.add(WARN, "Stripe-App", "Live-Schlüssel mit Test-Installationslink – beide müssen zum selben Modus gehören")
    else:
        report.add(OK, "Stripe-App", f"{mode}-Modus eingerichtet")


def check_paddle(report: Report) -> None:
    from .billing import PAID_PLANS

    token, key, secret = _env("PADDLE_CLIENT_TOKEN"), _env("PADDLE_API_KEY"), _env("PADDLE_WEBHOOK_SECRET")
    if not (token or key or secret):
        report.add(WARN, "Paddle", "nicht eingerichtet – Tarife sind sichtbar, aber nicht buchbar")
        return
    missing = [n for n, v in (("PADDLE_CLIENT_TOKEN", token), ("PADDLE_API_KEY", key), ("PADDLE_WEBHOOK_SECRET", secret)) if not v]
    if missing:
        report.add(FAIL, "Paddle", f"fehlt: {', '.join(missing)}")
        return
    sandbox = _env("PADDLE_ENVIRONMENT") != "production"
    prices = {plan: _env(f"PADDLE_PRICES_{plan.upper()}") for plan in PAID_PLANS}
    no_price = [plan for plan, value in prices.items() if not value]
    if no_price:
        report.add(FAIL, "Paddle", f"Preis-IDs fehlen für: {', '.join(no_price)} (PADDLE_PRICES_…)")
        return
    if (sandbox and token.startswith("live_")) or (not sandbox and token.startswith("test_")):
        report.add(FAIL, "Paddle", "Client-Token passt nicht zu PADDLE_ENVIRONMENT (test_ = sandbox, live_ = production)")
        return
    report.add(OK if not sandbox else WARN, "Paddle", "Live-Zahlungen aktiv" if not sandbox else "Sandbox (Testzahlungen) – für den Livegang auf production umstellen")


def _sample_invoice():
    from datetime import date
    from decimal import Decimal

    from .model import Address, Contact, Invoice, Line, Party, Payment, VatCategory

    seller = Party(
        name="Muster GmbH", address=Address(city="Berlin", postcode="10115", country_code="DE", line1="Str. 1"),
        electronic_address="a@example.org", vat_id="DE123456789",
        contact=Contact(name="Buchhaltung", phone="030 123456", email="a@example.org"),
    )
    buyer = Party(name="Kunde AG", address=Address(city="Köln", postcode="50667", country_code="DE"), electronic_address="b@example.org")
    return Invoice(
        number="DOCTOR-1", issue_date=date.today(), seller=seller, buyer=buyer, buyer_reference="check",
        payment=Payment(means_code="58", iban="DE02120300000000202051"), payment_terms="Test", delivery_date=date.today(),
        lines=[Line(id="1", name="Test", quantity=Decimal(1), net_price=Decimal(10), vat_category=VatCategory.STANDARD, vat_rate=Decimal(19))],
    )


def _sample_invoice_xml() -> bytes:
    from .ubl import to_ubl

    return to_ubl(_sample_invoice())


def run(smtp: bool = False, send_test_to: str | None = None) -> Report:
    report = Report()
    check_runtime(report)
    check_storage(report)
    check_web(report)
    check_engine(report)
    check_smtp(report, smtp, send_test_to)
    check_stripe(report)
    check_paddle(report)
    return report
