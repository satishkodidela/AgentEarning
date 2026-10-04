# Launch setup: domain, hosting, e-mail, legal, payments

Prices were checked on 4 October 2026, mostly from search-result summaries;
confirm them at checkout. The plan assumes you are a sole founder based in
India, selling to German businesses in euros.

## What it costs

| Item | Choice | Cost | Notes |
|---|---|---|---|
| Domain | `.de` at INWX | ~€3–5 first year, ~€4/yr renewal | Namecheap: ~$7–8/yr. No German address needed to register. |
| Server | Hetzner Cloud CX23 (2 vCPU, 4 GB, 40 GB), Germany | €5.49/month + IPv4 (~€0.50) + backups (+20%) ≈ **€7/month** | Price for new orders since 15 Jun 2026. |
| Mailbox (receive mail) | mailbox.org Standard, own domain | **€3/month** (annual) | German provider. For kontakt@, support@ and DMARC reports. |
| Sending mail (app) | Brevo, SMTP relay | **€0** up to 300 mails/day; paid from $9/month | EU provider; works with the app's SMTP settings as is. Move to Amazon SES Frankfurt (~$0.10–0.16 per 1,000) at volume. |
| Legal texts | IT-Recht Kanzlei "SaaS B2B" package | **€9.90/month** + VAT | AGB, privacy policy, Impressum, an AV-Vertrag template and updates when law changes. |
| Lawyer review | Fixed-price review by a German IT lawyer | One-time quote | No published prices found. Budget a few hundred to ~€1,500 (my estimate, unverified). Email draft below. |
| Payments | Paddle (merchant of record) | **No monthly fee**; 5% + $0.50 per payment | Payouts monthly by wire or Payoneer (a $15 SWIFT fee may apply). |

**Running cost:** about **€20/month** (server €7 + mailbox €3 + legal texts
€9.90 + domain ~€0.40), plus the one-time lawyer review and Paddle's
per-payment fee. Three Starter customers (€9) or one Business customer (€29)
cover it.

## Order of steps (about 2 weeks; the lawyer is the long pole)

1. **Day 1 – Domain.** Register the `.de` at INWX (or Namecheap) in your own
   name. DENIC only asks for a German "authorised recipient" if someone files
   a complaint, not at registration.
2. **Day 1 – Server.** Hetzner Cloud: Ubuntu 24.04, CX23, location Nuremberg
   or Falkenstein, add your SSH key, enable backups.
3. **Day 1 – DNS** (at your registrar): add the records below.
4. **Day 1 – Deploy.** On the server, as root:
   `bash setup-server.sh` (the domain defaults to `erechnungsbote.de`)
   (from `deploy/`). It installs the app, Caddy with automatic HTTPS, a
   firewall and a hardened systemd service, and creates `/etc/einvoice-bridge.env`
   with a fresh encryption key. **Back that key up**: without it the stored
   Stripe keys cannot be decrypted.
5. **Day 1–2 – E-mail.**
   - mailbox.org: add the domain and create `kontakt@` and `dmarc@`.
   - Brevo: add the domain and authenticate it (DKIM and verification code),
     then create an SMTP key and put it into `/etc/einvoice-bridge.env`
     (`SMTP_USER`, `SMTP_PASSWORD`).
   - Restart with `systemctl restart einvoice-bridge`.
   - Test: sign up on the waitlist with your own address. The confirmation
     mail must arrive and pass SPF, DKIM and DMARC. In Gmail, check
     "Show original".
6. **Day 2 – Legal texts (draft).** Order the IT-Recht Kanzlei package. Save
   the generated texts as `impressum.html`, `datenschutz.html`, `agb.html`
   and `rueckerstattung.html` in `/var/lib/einvoice/legal/`; the site picks
   them up without a redeploy. Send the lawyer email below.
7. **After the lawyer's changes – Paddle.** Apply at paddle.com. Paddle
   reviews the live site, which must be on HTTPS without a login. The app
   already has every page it checks:
   - product description (`/`)
   - pricing (`/preise`)
   - terms (`/agb`), which must name you and say Paddle is the merchant of
     record
   - refund policy (`/rueckerstattung`), which must offer a 14–90 day window;
     the draft offers 14 days
   - privacy policy (`/datenschutz`)
   - contact (`/kontakt`)
8. **Stripe App.** Upload the app and add the Connect webhook as described in
   `stripe-app/README.md`. Then install it on a Stripe test account with the
   test-mode link and run through setup. Submit it for Marketplace review once
   the legal pages are final.

### DNS records (replace values in angle brackets)

| Type | Name | Value |
|---|---|---|
| A | `@` | `<server IPv4>` |
| AAAA | `@` | `<server IPv6>` |
| CNAME | `www` | `erechnungsbote.de.` |
| MX | `@` | the MX hosts mailbox.org shows in its domain setup |
| TXT | `@` | `v=spf1 include:mailbox.org include:<Brevo SPF host from the Brevo dashboard> ~all` |
| CNAME/TXT | DKIM selectors | copy exactly from mailbox.org and Brevo |
| TXT | `@` | Brevo verification code (`brevo-code:...`) |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:dmarc@erechnungsbote.de` |

Use only **one** SPF record. Raise DMARC to `p=quarantine` after two weeks
of clean reports. Gmail rejects non-compliant bulk mail, and the e-invoices
must not land in spam.

## Paddle billing setup

Do this in the **sandbox** first (sandbox-vendors.paddle.com). Repeat it in
the live account once Paddle has approved your domain.

1. **Catalog > Products:** create "E-Rechnung Starter" and "E-Rechnung
   Business".
   - Add a monthly price of €9 and €29, tax **exclusive** (the site says
     "zzgl. USt.").
   - Give each price a **14-day trial**.
   - Optional: yearly prices.
2. **Developer tools > Authentication:**
   - Create a **client-side token** (for Paddle.js).
   - Create an **API key** that can create customer portal sessions and
     update subscriptions.
3. **Developer tools > Notifications:** add a destination
   `https://erechnungsbote.de/paddle/webhook` with the events
   `subscription.created`, `.updated`, `.activated`, `.trialing`,
   `.past_due`, `.paused`, `.resumed` and `.canceled`. Copy its secret key.
4. **Checkout > Checkout settings:** set the default payment link to
   `https://erechnungsbote.de/bezahlen`. Paddle sends customers there to pay,
   for example after a failed renewal.
5. Put the values into `/etc/einvoice-bridge.env`:
   - `PADDLE_ENVIRONMENT=sandbox` (or `production`)
   - `PADDLE_CLIENT_TOKEN`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`
   - `PADDLE_PRICES_STARTER`, `PADDLE_PRICES_BUSINESS` (comma-separated
     price IDs; the first one is offered at checkout)

   Then run `systemctl restart einvoice-bridge`.
6. **Test:**
   - Install the Stripe App on a test account, open **Konto > Tarif und
     Abrechnung** and start a trial with Paddle's sandbox test card
     (4242 4242 4242 4242).
   - The plan should switch within seconds.
   - Then try "Zu Business wechseln" and the customer portal.

## Payment provider decision

| | Paddle | Dodo Payments | Lemon Squeezy |
|---|---|---|---|
| Works for an India-based seller | Yes; payout by wire or Payoneer | Yes; built for Indian sellers | **No for new sellers:** its Stripe successor does not list India, and new signups are reported as gated |
| Fee on an EU subscription | 5% + $0.50 | 4% + $0.40, +1.5% non-US, +0.5% subscriptions ≈ 6% + $0.40 | – |
| Trust with German B2B buyers | High; well known, issues proper invoices with VAT | Newer | – |

**Recommendation:** Paddle first, with Dodo Payments as a fallback if Paddle
rejects or delays the application. Either way you sell to the merchant of
record, which resells to the customer. That makes your income an export of
services from India: file the GST LUT, and keep the purpose code and FIRA
for each payout (see the research report).

## E-mail to the lawyer (German, ready to send)

Send this to the firm you choose:
- IT-Recht Kanzlei (also sells the €9.90 package), or
- a lawyer who offers fixed-price SaaS-AGB reviews, such as anwalt-kg.de or
  srd-rechtsanwaelte.de.

Fill in the brackets.

> **Betreff:** Festpreisangebot: Prüfung der Rechtstexte für einen B2B-SaaS (E-Rechnungen) – Anbieter mit Sitz in Indien
>
> Sehr geehrte Damen und Herren,
>
> ich bin Einzelunternehmer mit Sitz in Indien und starte im November 2026 einen
> B2B-SaaS-Dienst ausschließlich für Unternehmen in Deutschland:
> „E-Rechnungsbote“ (erechnungsbote.de) wandelt Rechnungen aus dem Zahlungsdienst Stripe
> automatisch in E-Rechnungen (XRechnung, ZUGFeRD) um, prüft sie und versendet sie
> auf Wunsch an die Kunden meiner Kunden. Dabei verarbeite ich personenbezogene Daten
> aus den Rechnungen (Ansprechpartner, E-Mail-Adressen) im Auftrag meiner Kunden.
>
> Eckdaten:
> - Hosting in Deutschland (Hetzner), E-Mail-Versand über Brevo (Frankreich), Postfach bei mailbox.org.
> - Administration des Systems durch mich aus Indien (Drittlandzugriff).
> - Zahlungsabwicklung über Paddle als Merchant of Record (Paddle verkauft im eigenen Namen an meine Kunden).
> - Kostenloser Online-Validator: hochgeladene Dateien werden nur im Arbeitsspeicher geprüft und nicht gespeichert.
> - Warteliste mit Double-Opt-in; keine Kaltakquise per E-Mail.
> - Website (Testversion): https://erechnungsbote.de
>
> Ich bitte um ein Festpreisangebot für:
> 1. Impressum für einen Anbieter ohne Sitz in der EU.
> 2. Datenschutzerklärung für Website, Validator und Warteliste.
> 3. B2B-AGB für den SaaS-Dienst, abgestimmt auf Paddle als Merchant of Record,
>    inkl. Haftungsbegrenzung für fehlerhafte oder abgelehnte E-Rechnungen und Verfügbarkeit.
> 4. Auftragsverarbeitungsvertrag (Art. 28 DSGVO) inkl. Unterauftragsverarbeiter-Liste und der
>    Absicherung des Zugriffs aus Indien (z. B. Standardvertragsklauseln).
> 5. Klärung, ob ich einen Vertreter in der EU nach Art. 27 DSGVO benennen muss.
> 6. Prüfung der Werbeaussagen auf der Startseite (UWG) sowie der Rückerstattungsregelung
>    (14 Tage Geld-zurück bei der ersten Zahlung).
>
> Falls Sie Vorlagen (z. B. Ihr SaaS-B2B-Paket) als Grundlage verwenden, ist mir das recht;
> mir geht es um die Anpassung an die Punkte oben. Gewünschter Zeitrahmen: Fertigstellung
> bis [Datum, z. B. 15.11.2026]. Ein kurzes Vorgespräch per Video ist gern möglich.
>
> Vielen Dank und freundliche Grüße
> [Vollständiger Name]
> [Anschrift in Indien]
> [E-Mail] · [Telefon]

**English translation (for you):** Subject: fixed-price quote to review legal
texts for a B2B SaaS (e-invoices), provider based in India. The email
describes the service, hosting and data flows. It mentions that you
administer from India (a third-country transfer) and that Paddle is the
merchant of record. It asks for a fixed price for:
1. Impressum
2. Privacy policy
3. B2B terms with a liability cap
4. Data-processing agreement with safeguards for access from India
5. Whether an EU representative under Art. 27 GDPR is needed
6. A check of marketing claims and the 14-day refund policy

It asks for completion by mid-November 2026.

Points 4 and 5 are the reason to pay a lawyer rather than only use
templates. Administering a German service from India is a third-country data
transfer. A non-EU provider serving EU businesses may also need an EU
representative under the GDPR.

## What I could not do for you

These steps need your identity, your payment card or your signature:
- buying the domain and the server
- opening the Brevo, mailbox.org and Paddle accounts
- sending the lawyer email

Gmail is installed for your Claude account but not connected. If you
connect it in claude.ai settings, I can place the lawyer email in your
drafts.
