# E-Rechnung für Stripe (einvoice-bridge)

Turns Stripe invoices into German e-invoices that pass the official
validators, automatically:

- **XRechnung 3.0** (UBL and CII) for public-sector and B2B recipients
- **ZUGFeRD / Factur-X (EN 16931 profile)**: a PDF/A-3 that looks like a
  normal invoice and carries the XML inside

Every generated file is checked with the same rule sets the KoSIT reference
validator uses (OASIS UBL 2.1 / UN/CEFACT CII D16B XSDs, CEN EN 16931
Schematron, KoSIT XRechnung Schematron incl. the adopted Peppol rules)
before it is archived or sent.

Germany requires e-invoices for domestic B2B sales from **1 Jan 2027**
(prior-year turnover above €800k) and from **1 Jan 2028** for everyone.
Receiving them has been mandatory since 1 Jan 2025.

## What is in here

| Part | Where | What it does |
|---|---|---|
| Invoice model | `src/einvoice_bridge/model.py` | EN 16931 business terms, totals and rounding in one place |
| Writers | `ubl.py`, `cii.py`, `pdf.py` | XRechnung UBL/CII, ZUGFeRD PDF/A-3 |
| Validator | `validation/` | XSD + EN 16931 + XRechnung rules, plain-German hints, rule catalogue |
| Stripe mapper | `sources/stripe.py` | Stripe Invoice → model, or a German fix list of what is missing |
| Pipeline | `service.py`, `store.py` | Webhook → convert → validate → write-once archive (SHA-256) → email |
| Web app | `web/` | Free validator (lead magnet), 1,600+ rule pages (SEO), Stripe App install + onboarding, webhooks, customer dashboard, double-opt-in waitlist |
| Billing | `billing.py` | Plans and monthly limits, Paddle checkout (14-day trial), signed webhooks, customer portal, plan changes |
| Stripe App | `stripe_oauth.py`, `stripe-app/` | OAuth install link, code exchange, token refresh, Connect webhook, uninstall handling; app manifest and setup guide |
| CLI | `cli.py` | `validate`, `convert`, `fetch`, `account-create`, `secret`, `serve` |
| Research | `reports/`, `research_notes/` | Market research behind the product choice |
| Go-to-market | `docs/go-to-market.md` | Where to market, what not to do (cold email in Germany), pricing, kill criteria |
| Launch setup | `docs/launch-setup.md`, `deploy/` | Costs, domain/server/e-mail/Paddle steps, DNS records, lawyer e-mail, one-command server setup |

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                      # 101 tests, incl. official KoSIT samples

# validate any XRechnung / ZUGFeRD file
.venv/bin/einvoice-bridge validate rechnung.xml rechnung.pdf

# convert a Stripe invoice exported as JSON
.venv/bin/einvoice-bridge convert tests/fixtures/stripe/invoice_paid_card.json \
  --profile tests/fixtures/seller_profile.toml \
  --tax-rates tests/fixtures/stripe/tax_rates.json \
  --payment-method tests/fixtures/stripe/payment_method_card.json --out out/

# or fetch it straight from Stripe (restricted key, read-only)
STRIPE_API_KEY=rk_test_... .venv/bin/einvoice-bridge fetch in_123 --profile my_profile.toml
```

The seller profile holds what Stripe does not know (VAT ID / Steuernummer,
contact, IBAN, Kleinunternehmer status). See
`tests/fixtures/seller_profile.toml` for the format.

## Self-serve install (Stripe App)

With the Stripe App configured (`stripe-app/README.md`), a seller:
1. clicks "Mit Stripe verbinden" and approves read access in Stripe,
2. enters company data Stripe does not have (VAT ID or Steuernummer,
   contact, IBAN) in a validated form, and
3. lands in a dashboard where their newest invoices are already converted.
   These are archived only, never e-mailed, to avoid duplicates.

From then on, invoice events for every installed account arrive at one
Connect webhook (`/stripe/webhook`). Access tokens (1 hour) are refreshed
automatically. Signing in again is the same OAuth round trip, so there are
no passwords. Uninstalling in Stripe deletes the tokens and keeps the archive.

## Plans and billing (Paddle)

| Plan | Price | E-invoices per month | Sent straight to customers |
|---|---|---|---|
| Kostenlos | €0 | 3 | no (seller gets them) |
| Starter | €9 | 30 | no |
| Business | €29 | 300 | yes |

- Paid plans start with a 14-day trial in Paddle's checkout overlay
  (`/konto/abo`). Paddle is the merchant of record: it charges, invoices and
  handles VAT.
- Subscription state comes only from signed Paddle webhooks
  (`/paddle/webhook`). Events can arrive out of order, so older ones are
  ignored. `past_due` keeps access while Paddle retries the payment.
- Over the limit, no invoice is dropped. It is kept as "held back", the
  seller gets one e-mail per month, and held invoices are converted and
  delivered automatically after an upgrade.
- The first-run preview after install does not count towards the limit.
- "Abo verwalten" opens Paddle's customer portal through a fresh,
  signed-in session link. Plan switches go through Paddle's API with
  proration.
- Accounts created with the CLI get an operator-assigned plan (`--plan`,
  default `business`) without Paddle, for beta customers.

## Running the service

```bash
export EINVOICE_SECRET_KEY=$(.venv/bin/einvoice-bridge secret)   # encrypts Stripe keys at rest
export EINVOICE_DATA_DIR=/var/lib/einvoice                        # SQLite + archive
export EINVOICE_BASE_URL=https://your-domain.de
export SMTP_HOST=... SMTP_USER=... SMTP_PASSWORD=... SMTP_FROM=rechnung@your-domain.de

.venv/bin/einvoice-bridge account-create --profile seller.toml \
  --stripe-key rk_live_... --webhook-secret whsec_...
.venv/bin/einvoice-bridge serve --host 0.0.0.0 --port 8000
```

`account-create` prints the webhook URL to add in Stripe (events
`invoice.finalized` and `invoice.paid`) and a secret dashboard link.

Stripe restricted key: read access to Invoices, Tax Rates, PaymentIntents
and PaymentMethods is enough. By default each e-invoice is emailed to the
seller only; pass `--send-to-customer` once the output has been checked.

### How invoices flow

- `send_invoice` invoices are converted on `invoice.finalized`; auto-charged
  ones on `invoice.paid`, so the e-invoice can say how it was paid.
- If data is missing (customer address, e-mail, tax reason, IBAN...), nothing
  is generated; the seller gets a fix list and the next event retries.
- The mapper never guesses: a zero-tax line without a Stripe tax reason, or a
  total that differs from Stripe's, is refused.
- Leitweg-ID / buyer reference comes from an invoice custom field or
  metadata named `Leitweg-ID`, `buyer_reference` or `Käuferreferenz`;
  otherwise the Stripe customer ID is used (with a warning).
- Generated files are archived read-only with their SHA-256; reads verify the
  hash. Webhook retries do not regenerate or resend.

## Updating the validation rules

KoSIT and CEN publish new rule versions a few times a year. Bump the pinned
versions in `scripts/build_validation_artifacts.py` and run it; it clones the
sources, merges the Peppol rules into XRechnung, compiles the Schematron with
SchXslt and rewrites `src/einvoice_bridge/validation/artifacts/`.

## Known limits (before charging money)

- Stripe **credit notes** (CreditNote objects) are not converted yet; the
  model and writers already support type 381.
- Invoice-level items Stripe does not attach to lines (e.g. customer balance
  adjustments that change the total) are refused rather than modelled.
- Delivery is e-mail only. Public-sector recipients usually need upload to
  their portal or Peppol; that is not automated.
- PDF/A-3 metadata, embedded fonts and output intent are set, but the PDFs
  have not been run through veraPDF.
- The Stripe App must be uploaded and reviewed by Stripe before live installs
  work; test-mode install links work before that.
- The Kanzlei (multi-client) plan is "on request"; the multi-client
  dashboard is not built yet.
- Legal pages (`/impressum`, `/datenschutz`, `/agb`, `/rueckerstattung`) are
  placeholders until lawyer-reviewed HTML files are placed in
  `EINVOICE_LEGAL_DIR`; see `docs/launch-setup.md`.

## Licences of bundled third-party files

- Validation artifacts: CEN EN 16931 (EUPL 1.2), KoSIT XRechnung
  Schematron (Apache 2.0), OASIS UBL 2.1 and UN/CEFACT schemas; see
  `src/einvoice_bridge/validation/artifacts/LICENSES/` and `VERSIONS.json`.
- DejaVu fonts: `src/einvoice_bridge/fonts/LICENSE-DejaVu.txt`.
- KoSIT test-suite samples: `tests/fixtures/official/` (Apache 2.0).
