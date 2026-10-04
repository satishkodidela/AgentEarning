"""Command line: validate files, convert Stripe invoices, run the server, manage accounts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .profile import SellerProfile


def _print_problems(problems) -> None:
    for p in problems:
        marker = "FEHLER " if p.severity == "error" else "Hinweis"
        print(f"  [{marker}] {p.field}: {p.message}")


def cmd_validate(args) -> int:
    from .validation import NotAnInvoice, validate

    status = 0
    for path in args.files:
        try:
            report = validate(Path(path).read_bytes())
        except NotAnInvoice as exc:
            print(f"{path}: kein E-Rechnungsdokument – {exc}")
            status = 1
            continue
        verdict = "GÜLTIG" if report.valid else "UNGÜLTIG"
        print(f"{path}: {verdict} ({report.syntax}, {report.specification_id})")
        for f in report.findings:
            if f.severity == "info" and not args.verbose:
                continue
            print(f"  [{f.severity}] {f.rule_id}: {f.hint or f.message}")
        status |= 0 if report.valid else 1
    return status


def _write_outputs(invoice, out: Path) -> None:
    from .cii import to_cii
    from .pdf import to_zugferd_pdf
    from .ubl import to_ubl

    out.mkdir(parents=True, exist_ok=True)
    (out / f"{invoice.number}-xrechnung.xml").write_bytes(to_ubl(invoice))
    (out / f"{invoice.number}-xrechnung-cii.xml").write_bytes(to_cii(invoice, "xrechnung"))
    (out / f"{invoice.number}-zugferd.pdf").write_bytes(to_zugferd_pdf(invoice))
    print(f"Geschrieben nach {out}/: {invoice.number}-xrechnung.xml, -xrechnung-cii.xml, -zugferd.pdf")


def cmd_convert(args) -> int:
    from .sources.stripe import map_invoice

    profile = SellerProfile.load(Path(args.profile))
    invoice = json.loads(Path(args.invoice).read_text(encoding="utf-8"))
    rates = json.loads(Path(args.tax_rates).read_text(encoding="utf-8")) if args.tax_rates else {}
    method = json.loads(Path(args.payment_method).read_text(encoding="utf-8")) if args.payment_method else None
    result = map_invoice(invoice, profile, tax_rate=rates.get, payment_method=method)
    _print_problems(result.problems)
    if not result.ok:
        print("Keine E-Rechnung erstellt. Bitte die Fehler oben beheben.")
        return 1
    _write_outputs(result.invoice, Path(args.out))
    return 0


def cmd_fetch(args) -> int:
    from .service import LiveStripeGateway
    from .sources.stripe import map_invoice

    key = args.api_key or os.environ.get("STRIPE_API_KEY")
    if not key:
        print("Stripe-Schlüssel fehlt (--api-key oder STRIPE_API_KEY).")
        return 2
    gateway = LiveStripeGateway(key)
    profile = SellerProfile.load(Path(args.profile))
    if args.invoice_id.startswith("cn_"):
        from .sources.stripe import map_credit_note

        note = gateway.credit_note(args.invoice_id)
        ref = note.get("invoice")
        invoice = gateway.invoice(ref if isinstance(ref, str) else ref["id"])
        method = gateway.payment_method(invoice) if (note.get("refunds") or note.get("refund")) else None
        result = map_credit_note(note, invoice, profile, tax_rate=gateway.tax_rate, payment_method=method)
    else:
        raw = gateway.invoice(args.invoice_id)
        method = gateway.payment_method(raw) if raw.get("status") == "paid" else None
        result = map_invoice(raw, profile, tax_rate=gateway.tax_rate, payment_method=method)
    _print_problems(result.problems)
    if not result.ok:
        return 1
    _write_outputs(result.invoice, Path(args.out))
    return 0


def _store():
    from .store import Store

    secret = os.environ.get("EINVOICE_SECRET_KEY")
    if not secret:
        print("EINVOICE_SECRET_KEY ist nicht gesetzt (erzeugen mit: einvoice-bridge secret).")
        sys.exit(2)
    data = Path(os.environ.get("EINVOICE_DATA_DIR", "data"))
    data.mkdir(parents=True, exist_ok=True)
    return Store(data, secret)


def cmd_account_create(args) -> int:
    profile = SellerProfile.load(Path(args.profile))
    problems = profile.problems()
    if problems:
        for p in problems:
            print(f"  [FEHLER] {p}")
        return 1
    account = _store().create_account(
        profile, args.stripe_key, args.webhook_secret, args.send_to_customer, plan=args.plan
    )
    base = os.environ.get("EINVOICE_BASE_URL", "http://localhost:8000").rstrip("/")
    print(f"Konto angelegt: {account.id}")
    print(f"Webhook-URL (in Stripe eintragen): {base}/stripe/webhook/{account.id}")
    print("  Ereignisse: invoice.finalized, invoice.paid, credit_note.created, credit_note.voided")
    print(f"Dashboard (geheim halten): {base}/konto/{account.dashboard_token}")
    return 0


def cmd_doctor(args) -> int:
    from .doctor import run

    report = run(smtp=args.smtp, send_test_to=args.send_test_to)
    report.print()
    return 1 if report.failed else 0


def cmd_secret(_args) -> int:
    from cryptography.fernet import Fernet

    print(Fernet.generate_key().decode())
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    from .web.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="einvoice-bridge", description="E-Rechnungen aus Stripe")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="XRechnung/ZUGFeRD-Dateien prüfen")
    p.add_argument("files", nargs="+")
    p.add_argument("-v", "--verbose", action="store_true", help="auch Hinweise anzeigen")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("convert", help="Stripe-Rechnung (JSON-Datei) umwandeln")
    p.add_argument("invoice")
    p.add_argument("--profile", required=True, help="Verkäuferprofil (.toml/.json)")
    p.add_argument("--tax-rates", help="JSON: Tax-Rate-ID -> Stripe TaxRate")
    p.add_argument("--payment-method", help="JSON: Stripe PaymentMethod")
    p.add_argument("--out", default="out")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser("fetch", help="Rechnung (in_…) oder Gutschrift (cn_…) aus Stripe laden und umwandeln")
    p.add_argument("invoice_id", help="in_… oder cn_…")
    p.add_argument("--profile", required=True)
    p.add_argument("--api-key", help="eingeschränkter Stripe-Schlüssel (Standard: STRIPE_API_KEY)")
    p.add_argument("--out", default="out")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("account-create", help="Konto für den Webhook-Betrieb anlegen")
    p.add_argument("--profile", required=True)
    p.add_argument("--stripe-key", required=True, help="eingeschränkter Schlüssel mit Lesezugriff")
    p.add_argument("--webhook-secret", required=True, help="whsec_… des Stripe-Endpunkts")
    p.add_argument("--send-to-customer", action="store_true", help="E-Rechnung direkt an Kunden senden")
    p.add_argument(
        "--plan", default="business", choices=["free", "starter", "business"],
        help="Tarif ohne Paddle-Abo, z. B. für Beta-Kunden (Standard: business)",
    )
    p.set_defaults(func=cmd_account_create)

    p = sub.add_parser("doctor", help="Server-Konfiguration vor dem Livegang prüfen")
    p.add_argument("--smtp", action="store_true", help="Anmeldung am SMTP-Server testen")
    p.add_argument("--send-test-to", metavar="EMAIL", help="zusätzlich eine Test-E-Mail senden")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("secret", help="Schlüssel für EINVOICE_SECRET_KEY erzeugen")
    p.set_defaults(func=cmd_secret)

    p = sub.add_parser("serve", help="Webserver starten")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
