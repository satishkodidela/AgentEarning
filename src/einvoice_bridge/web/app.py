"""Web app: free validator (lead magnet), rule pages (SEO), Stripe App install, webhooks, dashboard."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from cryptography.fernet import InvalidToken
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ..billing import (
    PAID_PLANS,
    PLANS,
    PaddleClient,
    PaddleConfig,
    apply_subscription_event,
    effective_plan,
    sign_account,
    usage,
    verify_paddle_signature,
)
from ..service import (
    HANDLED_EVENTS,
    LiveStripeGateway,
    Mailer,
    SmtpMailer,
    StripeGateway,
    backfill,
    process_credit_note,
    process_invoice,
    retry_limited,
    should_process,
    void_credit_note,
)
from ..store import Account, Store
from ..stripe_oauth import OAuthError, StripeOAuth
from .forms import parse_profile, values_from_profile
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
SESSION_COOKIE = "session"
STATE_COOKIE = "oauth_state"
SESSION_DAYS = 30
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_app(
    store: Store | None = None,
    gateway_factory: Callable[[Account], StripeGateway] | None = None,
    mailer: Mailer | None = None,
    base_url: str | None = None,
    legal_dir: Path | str | None = None,
    oauth: StripeOAuth | None = None,
    connect_webhook_secret: str | None = None,
    paddle: PaddleConfig | None = None,
    paddle_client: PaddleClient | None = None,
) -> FastAPI:
    if store is None:
        data_dir = Path(os.environ.get("EINVOICE_DATA_DIR", "data"))
        secret = os.environ.get("EINVOICE_SECRET_KEY")
        if not secret:
            raise RuntimeError("EINVOICE_SECRET_KEY is not set (generate one with `einvoice-bridge secret`)")
        data_dir.mkdir(parents=True, exist_ok=True)
        store = Store(data_dir, secret)
    mailer = mailer or SmtpMailer()
    base_url = (base_url or os.environ.get("EINVOICE_BASE_URL", "http://localhost:8000")).rstrip("/")
    oauth = oauth or StripeOAuth.from_env(base_url)
    connect_webhook_secret = connect_webhook_secret or os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET")
    secure_cookies = base_url.startswith("https://")
    paddle = paddle or PaddleConfig.from_env()
    if paddle and paddle_client is None:
        paddle_client = PaddleClient(paddle)

    def live_gateway(account: Account) -> StripeGateway:
        if account.is_oauth:
            if oauth is None:
                raise RuntimeError("Stripe App is not configured (STRIPE_APP_*)")
            return LiveStripeGateway(oauth.access_token(store, account))
        return LiveStripeGateway(account.stripe_api_key)

    gateway_factory = gateway_factory or live_gateway
    # Lawyer-reviewed legal texts are dropped in as HTML files (impressum.html,
    # datenschutz.html, agb.html, rueckerstattung.html) without a code change.
    legal_dir = Path(legal_dir or os.environ.get("EINVOICE_LEGAL_DIR", "legal"))
    contact_email = os.environ.get("EINVOICE_CONTACT_EMAIL", "")

    app = FastAPI(title="E-Rechnung für Stripe", docs_url=None, redoc_url=None)
    app.state.store = store

    def render(request: Request, template: str, status_code: int = 200, **context) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            template,
            {
                "base_url": base_url,
                "contact_email": contact_email,
                "stripe_app": oauth is not None,
                "paddle_enabled": paddle is not None,
                "plans": PLANS,
                **context,
            },
            status_code=status_code,
        )

    def legal(request: Request, name: str, title: str, fallback: str = "legal.html") -> HTMLResponse:
        path = legal_dir / f"{name}.html"
        if path.is_file():
            return render(request, "legal.html", title=title, body=path.read_text(encoding="utf-8"))
        return render(request, fallback, title=title)

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

    @app.get("/preise", response_class=HTMLResponse)
    def pricing(request: Request):
        return render(request, "pricing.html")

    @app.get("/kontakt", response_class=HTMLResponse)
    def contact(request: Request):
        return render(request, "contact.html")

    @app.get("/sitemap.xml")
    def sitemap():
        pages = ["", "/preise", "/regeln", "/kontakt"]
        urls = [f"{base_url}{p}" for p in pages] + [f"{base_url}/regeln/{r.slug}" for r in rules().values()]
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
        return legal(request, "impressum", "Impressum")

    @app.get("/datenschutz", response_class=HTMLResponse)
    def privacy(request: Request):
        return legal(request, "datenschutz", "Datenschutzerklärung")

    @app.get("/agb", response_class=HTMLResponse)
    def terms(request: Request):
        return legal(request, "agb", "Allgemeine Geschäftsbedingungen")

    @app.get("/rueckerstattung", response_class=HTMLResponse)
    def refunds(request: Request):
        return legal(request, "rueckerstattung", "Rückerstattung", fallback="refund.html")

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

    # Stripe App install (OAuth) ---------------------------------------------

    def session_account(request: Request) -> Account | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        try:
            account_id = store.fernet.decrypt(token.encode(), ttl=SESSION_DAYS * 86400).decode()
        except InvalidToken:
            return None
        account = store.account(account_id)
        return account if account and account.status != "uninstalled" else None

    def require_session(request: Request) -> Account:
        account = session_account(request)
        if not account:
            raise HTTPException(303, headers={"Location": "/anmelden"})
        return account

    def start_session(response: Response, account: Account) -> None:
        response.set_cookie(
            SESSION_COOKIE, store.fernet.encrypt(account.id.encode()).decode(),
            max_age=SESSION_DAYS * 86400, httponly=True, secure=secure_cookies, samesite="lax",
        )

    @app.get("/stripe/install")
    @app.get("/anmelden")
    def install(request: Request):
        """Start install, or sign in again: both are the same OAuth round trip."""
        if oauth is None:
            return render(
                request, "message.html", status_code=503, title="Bald verfügbar",
                text="Die Stripe-App ist noch nicht freigeschaltet. Tragen Sie sich auf der Startseite in die Warteliste ein.",
            )
        state = secrets.token_urlsafe(24)
        response = RedirectResponse(oauth.authorize_url(state), status_code=303)
        response.set_cookie(STATE_COOKIE, state, max_age=900, httponly=True, secure=secure_cookies, samesite="lax")
        return response

    @app.get("/stripe/oauth/callback")
    def oauth_callback(
        request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""
    ):
        if oauth is None:
            raise HTTPException(404)
        if error or not code:
            return render(
                request, "message.html", status_code=400, title="Installation abgebrochen",
                text=error_description or "Die Verbindung mit Stripe wurde nicht hergestellt.",
            )
        # Installs started on our site carry our state, which must match the
        # cookie (CSRF). Installs started in the Stripe App Marketplace arrive
        # without state; the one-time code is then the only proof, as Stripe intends.
        if state and not secrets.compare_digest(state, request.cookies.get(STATE_COOKIE, "")):
            return render(
                request, "message.html", status_code=400, title="Sitzung abgelaufen",
                text="Bitte starten Sie die Verbindung mit Stripe erneut.",
            )
        try:
            tokens = oauth.exchange_code(code)
        except OAuthError as exc:
            log.warning("OAuth code exchange failed: %s", exc)
            return render(
                request, "message.html", status_code=400, title="Verbindung fehlgeschlagen",
                text="Stripe hat die Verbindung nicht bestätigt. Bitte versuchen Sie es erneut.",
            )
        account, _new = store.install(
            tokens.stripe_account_id, tokens.livemode, tokens.access_token, tokens.refresh_token, tokens.expires_in
        )
        target = "/konto" if account.profile else "/konto/einrichten"
        response = RedirectResponse(target, status_code=303)
        start_session(response, account)
        response.delete_cookie(STATE_COOKIE)
        return response

    @app.post("/stripe/webhook")
    async def connect_webhook(request: Request, background: BackgroundTasks):
        """Events from every account that installed the app (a Connect endpoint)."""
        import stripe

        if not connect_webhook_secret:
            raise HTTPException(404)
        payload = await request.body()
        try:
            stripe.WebhookSignature.verify_header(
                payload.decode("utf-8"), request.headers.get("stripe-signature", ""), connect_webhook_secret
            )
        except stripe.SignatureVerificationError:
            raise HTTPException(400, "invalid signature") from None
        event = json.loads(payload)
        account = store.account_by_stripe_id(event.get("account", ""), bool(event.get("livemode")))
        if not account or not account.is_oauth:
            return {"received": True, "ignored": "unknown account"}
        if event.get("type") == "account.application.deauthorized":
            store.uninstall(account.id)
            return {"received": True}
        obj = event.get("data", {}).get("object", {})
        if account.status != "uninstalled":
            _schedule(background, event, store, account, gateway_factory, mailer, base_url)
        return {"received": True}

    # manual accounts (restricted key + own webhook, set up with the CLI)

    @app.post("/stripe/webhook/{account_id}")
    async def stripe_webhook(account_id: str, request: Request, background: BackgroundTasks):
        import stripe

        account = store.account(account_id)
        if not account or account.is_oauth:
            raise HTTPException(404)
        payload = await request.body()
        try:
            stripe.WebhookSignature.verify_header(
                payload.decode("utf-8"), request.headers.get("stripe-signature", ""), account.webhook_secret
            )
        except stripe.SignatureVerificationError:
            raise HTTPException(400, "invalid signature") from None
        _schedule(background, json.loads(payload), store, account, gateway_factory, mailer, base_url)
        return {"received": True}

    # dashboard (signed-in via Stripe) ------------------------------------------

    @app.get("/konto", response_class=HTMLResponse)
    def my_account(request: Request):
        account = require_session(request)
        if account.profile is None:
            return RedirectResponse("/konto/einrichten", status_code=303)
        return render(
            request, "account.html", account=account, documents=store.documents(account.id),
            base="/konto", notice=request.query_params.get("hinweis"), usage=usage(store, account),
        )

    @app.get("/konto/einrichten", response_class=HTMLResponse)
    def setup_form(request: Request):
        account = require_session(request)
        values = values_from_profile(account.profile, account.send_to_customer)
        return render(request, "onboarding.html", account=account, v=values, errors={})

    @app.post("/konto/einrichten", response_class=HTMLResponse)
    async def setup_save(request: Request, background: BackgroundTasks):
        account = require_session(request)
        form = dict(await request.form())
        profile, errors, values = parse_profile(form)
        if errors:
            return render(request, "onboarding.html", status_code=422, account=account, v=values, errors=errors)
        first_time = account.profile is None
        store.save_profile(account.id, profile, values["send_to_customer"])
        if first_time:
            # Show results right away: convert recent invoices (archived, not e-mailed).
            background.add_task(_backfill, store, store.account(account.id), gateway_factory, mailer)
            return RedirectResponse("/konto?hinweis=eingerichtet", status_code=303)
        return RedirectResponse("/konto?hinweis=gespeichert", status_code=303)

    @app.post("/konto/umwandeln")
    def convert_recent(request: Request, background: BackgroundTasks):
        account = require_session(request)
        if not account.is_active:
            return RedirectResponse("/konto/einrichten", status_code=303)
        background.add_task(_backfill, store, account, gateway_factory, mailer, True)
        return RedirectResponse("/konto?hinweis=umwandlung", status_code=303)

    # billing (Paddle) --------------------------------------------------------

    @app.get("/konto/abo", response_class=HTMLResponse)
    def subscription(request: Request):
        account = require_session(request)
        if account.profile is None:
            return RedirectResponse("/konto/einrichten", status_code=303)
        checkout = None
        if paddle:
            checkout = {
                "client_token": paddle.client_token,
                "sandbox": paddle.sandbox,
                "email": account.profile.contact.email,
                "custom_data": {"account_id": account.id, "account_sig": sign_account(account.id, store.secret)},
                "prices": {plan: paddle.checkout_price(plan) for plan in PAID_PLANS},
            }
        return render(
            request, "subscription.html", account=account, usage=usage(store, account),
            current=effective_plan(account), checkout=checkout, status=request.query_params.get("status"),
        )

    @app.get("/bezahlen", response_class=HTMLResponse)
    def pay(request: Request):
        """Paddle's "default payment link": Paddle.js opens the checkout for ?_ptxn=…"""
        if not paddle:
            raise HTTPException(404)
        return render(request, "pay.html", paddle_token=paddle.client_token, sandbox=paddle.sandbox)

    @app.post("/konto/abo/verwalten")
    def manage_subscription(request: Request):
        account = require_session(request)
        if not (paddle_client and account.paddle_customer_id):
            return RedirectResponse("/konto/abo", status_code=303)
        try:
            url = paddle_client.portal_url(account.paddle_customer_id, account.paddle_subscription_id)
        except Exception:  # noqa: BLE001 - Paddle unreachable; tell the user instead of a 500
            log.exception("Paddle portal session for %s failed", account.id)
            return render(
                request, "message.html", status_code=502, title="Kundenportal nicht erreichbar",
                text="Paddle ist gerade nicht erreichbar. Bitte versuchen Sie es in ein paar Minuten erneut.",
            )
        return RedirectResponse(url, status_code=303)

    @app.post("/konto/abo/wechseln")
    async def change_plan(request: Request):
        account = require_session(request)
        plan = (await request.form()).get("plan")
        price = paddle.checkout_price(plan) if paddle and plan in PAID_PLANS else None
        if not (price and paddle_client and account.paddle_subscription_id):
            raise HTTPException(400, "Tarifwechsel nicht möglich")
        try:
            paddle_client.change_plan(account.paddle_subscription_id, price)
        except Exception:  # noqa: BLE001
            log.exception("plan change for %s failed", account.id)
            return render(
                request, "message.html", status_code=502, title="Tarifwechsel fehlgeschlagen",
                text="Paddle hat den Wechsel nicht bestätigt. Bitte versuchen Sie es erneut oder nutzen Sie das Kundenportal.",
            )
        return RedirectResponse("/konto/abo?status=gewechselt", status_code=303)

    @app.post("/paddle/webhook")
    async def paddle_webhook(request: Request, background: BackgroundTasks):
        if not paddle:
            raise HTTPException(404)
        raw = await request.body()
        if not verify_paddle_signature(raw, request.headers.get("paddle-signature", ""), paddle.webhook_secret):
            raise HTTPException(400, "invalid signature")
        change = apply_subscription_event(store, paddle, store.secret, json.loads(raw))
        if change and change.became_paid:
            background.add_task(_retry_limited, store, store.account(change.account_id), gateway_factory, mailer, base_url)
        return {"received": True}

    @app.get("/konto/dokumente/{invoice_id}/{name}")
    def my_download(request: Request, invoice_id: str, name: str):
        return _download(store, require_session(request), invoice_id, name)

    @app.post("/abmelden")
    def logout():
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        return response

    # dashboard (secret link, manual accounts) ----------------------------------

    @app.get("/konto/{token}", response_class=HTMLResponse)
    def dashboard(request: Request, token: str):
        account = store.account_by_token(token)
        if not account:
            raise HTTPException(404)
        return render(
            request, "account.html", account=account, documents=store.documents(account.id),
            base=f"/konto/{token}", webhook_url=f"{base_url}/stripe/webhook/{account.id}",
        )

    @app.get("/konto/{token}/dokumente/{invoice_id}/{name}")
    def download(token: str, invoice_id: str, name: str):
        return _download(store, store.account_by_token(token), invoice_id, name)

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def _download(store: Store, account: Account | None, invoice_id: str, name: str) -> Response:
    doc = store.document(account.id, invoice_id) if account else None
    content = store.read_file(doc, name) if doc else None
    if content is None:
        raise HTTPException(404)
    media = "application/pdf" if name.endswith(".pdf") else "application/xml"
    filename = f"{doc.number}.{name.rsplit('.', 1)[-1]}"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _backfill(store: Store, account: Account, gateway_factory, mailer: Mailer, billable: bool = False) -> None:
    try:
        backfill(store, account, gateway_factory(account), mailer, billable=billable)
    except Exception:  # noqa: BLE001 - logged; the user can retry from the dashboard
        log.exception("backfill for account %s failed", account.id)


def _schedule(background: BackgroundTasks, event: dict, store: Store, account: Account, gateway_factory, mailer: Mailer, base_url: str) -> None:
    """Queue the work a Stripe event asks for (invoices and credit notes)."""
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    if not obj.get("id") or event_type not in HANDLED_EVENTS or not should_process(event_type, obj):
        return
    if event_type == "credit_note.created":
        background.add_task(_run_credit_note, store, account, obj["id"], gateway_factory, mailer)
    elif event_type == "credit_note.voided":
        background.add_task(void_credit_note, store, account, obj["id"], mailer)
    else:
        background.add_task(_run, store, account, obj["id"], gateway_factory, mailer, base_url)


def _run_credit_note(store: Store, account: Account, credit_note_id: str, gateway_factory, mailer: Mailer) -> None:
    try:
        process_credit_note(store, account, credit_note_id, gateway_factory(account), mailer)
    except Exception:  # noqa: BLE001 - logged; retried on the next event or from the dashboard
        log.exception("processing credit note %s for account %s failed", credit_note_id, account.id)


def _retry_limited(store: Store, account: Account, gateway_factory, mailer: Mailer, base_url: str) -> None:
    try:
        retry_limited(store, account, gateway_factory(account), mailer, base_url)
    except Exception:  # noqa: BLE001 - logged; remaining invoices retry on their next event
        log.exception("retrying limited invoices for %s failed", account.id)


def _run(store: Store, account: Account, invoice_id: str, gateway_factory, mailer: Mailer, base_url: str = "") -> None:
    try:
        process_invoice(store, account, invoice_id, gateway_factory(account), mailer, base_url=base_url)
    except Exception:  # noqa: BLE001 - logged; Stripe will not retry a 200, so surface in logs/alerts
        log.exception("processing %s for account %s failed", invoice_id, account.id)
