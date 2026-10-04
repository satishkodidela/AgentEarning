"""Web app: free validator (lead magnet), rule pages (SEO), Stripe webhook, dashboard."""

from __future__ import annotations

import json
import logging
import os
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from ..service import (
    HANDLED_EVENTS,
    LiveStripeGateway,
    Mailer,
    SmtpMailer,
    StripeGateway,
    process_invoice,
    should_process,
)
from ..store import Account, Store
from ..summary import summarize
from ..validation import NotAnInvoice, extract_xml_from_pdf, validate
from ..validation.catalog import by_slug, rules

log = logging.getLogger(__name__)

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
# "/Q{urn:...}Invoice[1]/Q{urn:...}BuyerReference[1]" -> "/Invoice/BuyerReference"
TEMPLATES.env.filters["short_path"] = lambda path: re.sub(
    r"\[namespace-uri\(\)='[^']*'\]|Q\{[^}]*\}|\*:|\b[a-z]+:(?=[A-Z])|\[1\]", "", path
)
MAX_UPLOAD = 10 * 1024 * 1024
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_app(
    store: Store | None = None,
    gateway_factory: Callable[[Account], StripeGateway] | None = None,
    mailer: Mailer | None = None,
    base_url: str | None = None,
) -> FastAPI:
    if store is None:
        data_dir = Path(os.environ.get("EINVOICE_DATA_DIR", "data"))
        secret = os.environ.get("EINVOICE_SECRET_KEY")
        if not secret:
            raise RuntimeError("EINVOICE_SECRET_KEY is not set (generate one with `einvoice-bridge secret`)")
        data_dir.mkdir(parents=True, exist_ok=True)
        store = Store(data_dir, secret)
    gateway_factory = gateway_factory or (lambda account: LiveStripeGateway(account.stripe_api_key))
    mailer = mailer or SmtpMailer()
    base_url = (base_url or os.environ.get("EINVOICE_BASE_URL", "http://localhost:8000")).rstrip("/")

    app = FastAPI(title="E-Rechnung für Stripe", docs_url=None, redoc_url=None)
    app.state.store = store

    def render(request: Request, template: str, status_code: int = 200, **context) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request, template, {"base_url": base_url, **context}, status_code=status_code
        )

    async def read_upload(upload: UploadFile) -> bytes:
        content = await upload.read(MAX_UPLOAD + 1)
        if len(content) > MAX_UPLOAD:
            raise HTTPException(413, "Datei ist größer als 10 MB.")
        return content

    # public pages ---------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return render(request, "index.html")

    @app.post("/pruefen", response_class=HTMLResponse)
    async def check(request: Request, datei: UploadFile = File(...)):
        content = await read_upload(datei)
        try:
            report = validate(content)
            xml = extract_xml_from_pdf(content) if content.lstrip()[:5] == b"%PDF-" else content
            facts = summarize(xml) if not any(f.source == "xsd" for f in report.findings) else None
        except NotAnInvoice as exc:
            return render(request, "report.html", status_code=422, error=str(exc), filename=datei.filename)
        return render(request, "report.html", report=report, facts=facts, filename=datei.filename)

    @app.post("/api/v1/validate")
    async def api_validate(datei: UploadFile = File(...)):
        content = await read_upload(datei)
        try:
            return validate(content).to_dict()
        except NotAnInvoice as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)

    @app.get("/regeln", response_class=HTMLResponse)
    def rule_index(request: Request):
        groups: dict[str, list] = {}
        for rule in rules().values():
            prefix = rule.id.rsplit("-", 1)[0]
            groups.setdefault(prefix, []).append(rule)
        return render(request, "rules.html", groups=groups)

    @app.get("/regeln/{slug}", response_class=HTMLResponse)
    def rule_page(request: Request, slug: str):
        rule = by_slug(slug)
        if not rule:
            raise HTTPException(404, "Regel nicht gefunden")
        return render(request, "rule.html", rule=rule)

    @app.get("/sitemap.xml")
    def sitemap():
        urls = [f"{base_url}/", f"{base_url}/regeln"] + [f"{base_url}/regeln/{r.slug}" for r in rules().values()]
        body = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
        return Response(
            f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>',
            media_type="application/xml",
        )

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return f"User-agent: *\nDisallow: /konto/\nSitemap: {base_url}/sitemap.xml\n"

    @app.get("/impressum", response_class=HTMLResponse)
    def impressum(request: Request):
        return render(request, "legal.html", title="Impressum")

    @app.get("/datenschutz", response_class=HTMLResponse)
    def privacy(request: Request):
        return render(request, "legal.html", title="Datenschutzerklärung")

    # waitlist with double opt-in (consent is required for e-mail marketing in Germany)

    @app.post("/warteliste", response_class=HTMLResponse)
    def waitlist(request: Request, email: str = Form(...), einwilligung: bool = Form(False), quelle: str = Form("")):
        if not EMAIL.match(email.strip()) or not einwilligung:
            return render(
                request, "message.html", status_code=422, title="Bitte prüfen",
                text="Bitte geben Sie eine gültige E-Mail-Adresse an und bestätigen Sie die Einwilligung.",
            )
        token = store.add_to_waitlist(email, quelle or None)
        if token:
            msg = EmailMessage()
            msg["Subject"] = "Bitte bestätigen Sie Ihre Anmeldung"
            msg["To"] = email.strip()
            msg.set_content(
                "Hallo,\n\nbitte bestätigen Sie Ihre Anmeldung zur Warteliste:\n"
                f"{base_url}/warteliste/bestaetigen/{token}\n\n"
                "Wenn Sie sich nicht angemeldet haben, ignorieren Sie diese E-Mail einfach.\n"
            )
            mailer.send(msg)
        return render(
            request, "message.html", title="Fast geschafft",
            text="Wir haben Ihnen eine E-Mail geschickt. Bitte bestätigen Sie den Link darin.",
        )

    @app.get("/warteliste/bestaetigen/{token}", response_class=HTMLResponse)
    def confirm_waitlist(request: Request, token: str):
        ok = store.confirm_waitlist(token)
        return render(
            request, "message.html", title="Danke!" if ok else "Link ungültig",
            text="Ihre Anmeldung ist bestätigt. Wir melden uns, sobald Ihr Zugang bereit ist."
            if ok else "Dieser Link ist ungültig oder wurde bereits verwendet.",
        )

    # Stripe -----------------------------------------------------------------

    @app.post("/stripe/webhook/{account_id}")
    async def stripe_webhook(account_id: str, request: Request, background: BackgroundTasks):
        import stripe

        account = store.account(account_id)
        if not account:
            raise HTTPException(404)
        payload = await request.body()
        try:
            stripe.WebhookSignature.verify_header(
                payload.decode("utf-8"), request.headers.get("stripe-signature", ""), account.webhook_secret
            )
        except stripe.SignatureVerificationError:
            raise HTTPException(400, "invalid signature") from None
        event = json.loads(payload)
        obj = event.get("data", {}).get("object", {})
        if event.get("type") in HANDLED_EVENTS and should_process(event["type"], obj):
            background.add_task(_run, store, account, obj["id"], gateway_factory, mailer)
        return {"received": True}

    # dashboard --------------------------------------------------------------

    @app.get("/konto/{token}", response_class=HTMLResponse)
    def dashboard(request: Request, token: str):
        account = store.account_by_token(token)
        if not account:
            raise HTTPException(404)
        return render(
            request, "account.html", account=account, documents=store.documents(account.id),
            webhook_url=f"{base_url}/stripe/webhook/{account.id}",
        )

    @app.get("/konto/{token}/dokumente/{invoice_id}/{name}")
    def download(token: str, invoice_id: str, name: str):
        account = store.account_by_token(token)
        doc = store.document(account.id, invoice_id) if account else None
        content = store.read_file(doc, name) if doc else None
        if content is None:
            raise HTTPException(404)
        media = "application/pdf" if name.endswith(".pdf") else "application/xml"
        filename = f"{doc.number}.{name.rsplit('.', 1)[-1]}"
        return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def _run(store: Store, account: Account, invoice_id: str, gateway_factory, mailer: Mailer) -> None:
    try:
        process_invoice(store, account, invoice_id, gateway_factory(account), mailer)
    except Exception:  # noqa: BLE001 - logged; Stripe will not retry a 200, so surface in logs/alerts
        log.exception("processing %s for account %s failed", invoice_id, account.id)
