# Go-live checklist: erechnungsbote.de

The steps run in order. Every item needs your login, card or signature, so
nobody else can do them for you. The commands are prepared, and
`einvoice-bridge doctor` tells you after each phase what is still missing.

> **Secrets** (passwords, API keys, tokens, the encryption key) go only into
> the server's `~/.einvoice-bridge.env` and your password manager. Never put
> them into chat, e-mail, screenshots or GitHub.

## Phase A: development site online (today, about 60–90 min)

Follow `docs/deploy-namecheap.md`:

- [ ] SSL activated and Force HTTPS on (10 min)
- [ ] Private Email mailboxes `rechnung@`, `kontakt@`, `dmarc@`, with MX,
      SPF, DKIM and DMARC records (15 min)
- [ ] Code cloned to `~/einvoice` (10 min)
- [ ] cPanel Python app created (Python ≥ 3.11), `install.sh` run (15 min)
- [ ] `SMTP_PASSWORD` set, encryption key saved in the password manager
- [ ] `einvoice-bridge doctor --send-test-to <you>`: 0 errors, and the test
      mail arrives
- [ ] https://erechnungsbote.de opens and the free validator works

**Done when:** the site is live with the free validator and rule pages, and
the waitlist sends its confirmation e-mail. You can already submit the
sitemap to Google Search Console (https://erechnungsbote.de/sitemap.xml).

## Phase B: Stripe test mode end-to-end (about 30–45 min)

Needs the Stripe CLI on your own computer. Follow `stripe-app/README.md`.

- [ ] `stripe apps upload` from `stripe-app/`
- [ ] Copy the test install link and app client ID from the "External test"
      tab
- [ ] Add the Connect webhook `https://erechnungsbote.de/stripe/webhook`
      with `invoice.finalized`, `invoice.paid`, `credit_note.created`,
      `credit_note.voided` and `account.application.deauthorized`
- [ ] Add `STRIPE_APP_SECRET_KEY` (sk_test_…), `STRIPE_APP_INSTALL_LINK`
      and `STRIPE_CONNECT_WEBHOOK_SECRET` to the env file, then restart
- [ ] On the site, click "Mit Stripe verbinden", install on a Stripe test
      account and fill in the company details
- [ ] In Stripe test mode, create and finalise an invoice for a test
      customer with a full German address. The ZUGFeRD PDF and XRechnung
      appear in **Konto**, and the e-mail arrives.
- [ ] Refund part of it with a credit note. A "Rechnungskorrektur" appears.

## Phase C: Paddle sandbox (about 30 min)

Follow `docs/launch-setup.md`, "Paddle billing setup":

- [ ] Products Starter €9 and Business €29, tax exclusive, 14-day trial
- [ ] Client-side token, API key, webhook
      `https://erechnungsbote.de/paddle/webhook`, default payment link
      `https://erechnungsbote.de/bezahlen`
- [ ] Add the `PADDLE_*` variables to the env file, then restart
- [ ] Start a trial in **Konto > Tarif und Abrechnung** with test card
      4242 4242 4242 4242. The plan changes within seconds.

## Phase D: before the first paying customer

These steps take days, so start them in parallel with A–C:

- [ ] **Legal texts** (send the lawyer e-mail in `docs/launch-setup.md`):
      Impressum, Datenschutzerklärung, AGB, Rückerstattung as HTML files in
      `~/einvoice-data/legal/`. `doctor` warns until all four exist.
- [ ] **EU hosting for real invoice data.** German customers' invoices
      contain personal data, and a USA server makes the GDPR paperwork (data
      processing agreement, transfer safeguards) much harder. Choose one:
      - ask Namecheap to move the Stellar account to its EU datacenter, or
      - run `deploy/setup-server.sh` on a Hetzner server in Germany
        (~€7/month). This is recommended: a real server without Passenger
        idle stops.

      Then point the domain's A record to the new server.
- [ ] **Paddle live:**
      - apply with the live site; Paddle checks the pages listed in
        `docs/launch-setup.md`;
      - after approval, create live products, keys and webhook;
      - set `PADDLE_ENVIRONMENT=production`.
- [ ] **Stripe App live:**
      - submit the app for review;
      - after publication, set the live secret key and install link or
        client ID;
      - add the live Connect webhook.
- [ ] Final `einvoice-bridge doctor --smtp` on the production server shows
      0 errors and 0 warnings.

## When you're stuck

Run `einvoice-bridge doctor` and look at `~/einvoice-data/passenger.log`
(Namecheap) or `journalctl -u einvoice-bridge` (Hetzner). Paste only the
error lines, never the env file.
