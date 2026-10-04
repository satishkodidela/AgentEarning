# Stripe App: E-Rechnungsbote (OAuth)

This folder is the Stripe App definition. The app has no Dashboard UI; Stripe
only handles the install and permissions, and everything else happens on
the website. The install flow itself lives in the web app
(`src/einvoice_bridge/stripe_oauth.py`, routes `/stripe/install`,
`/stripe/oauth/callback`, `/stripe/webhook`).

## One-time setup in your Stripe account

1. The manifest is set up for `erechnungsbote.de`: the app ID is
   `de.erechnungsbote.app` and the redirect URI is
   `https://erechnungsbote.de/stripe/oauth/callback`. The redirect URI must
   match exactly. Stripe does not allow "Stripe" in app names; the app is
   called "E-Rechnungsbote".
2. Install the Stripe CLI and its apps plugin, then upload:

   ```bash
   stripe login
   stripe plugin install apps
   cd stripe-app && stripe apps upload
   ```

3. In the Dashboard (Apps > your app):
   - **External test** tab: copy the test-mode OAuth install link. It
     contains `chnlink_...` and works before the app is published.
   - **Settings**: note the client ID (`ca_...`).
4. Webhook for all installed accounts: Developers > Webhooks > Add endpoint
   - URL: `https://erechnungsbote.de/stripe/webhook`
   - "Listen to events on Connected accounts"
   - Events: `invoice.finalized`, `invoice.paid`, `credit_note.created`,
     `credit_note.voided`, `account.application.deauthorized`
   - Copy the signing secret (`whsec_...`).
5. Server environment (`/etc/einvoice-bridge.env`):

   ```
   STRIPE_APP_SECRET_KEY=sk_test_...        # same mode as the install link
   STRIPE_APP_INSTALL_LINK=https://marketplace.stripe.com/oauth/v2/chnlink_.../authorize?client_id=ca_...
   STRIPE_CONNECT_WEBHOOK_SECRET=whsec_...
   ```

   For live mode, use the live secret key and either the live install link or
   `STRIPE_APP_CLIENT_ID=ca_...` (the default link is built from it). One
   deployment runs in one mode.

6. Restart the app. The landing page now shows "Mit Stripe verbinden".

## How it works

| Step | What happens |
|---|---|
| Click "Mit Stripe verbinden" | `/stripe/install` sets a state cookie and redirects to Stripe's install page |
| Approve in Stripe | Stripe redirects to `/stripe/oauth/callback?code=…&state=…`; state is checked against the cookie (marketplace installs arrive without state) |
| Code exchange | `POST https://api.stripe.com/v1/oauth/token` with the app secret key → access token (1 h), refresh token (1 yr, rotated), `stripe_user_id` |
| Onboarding | The seller enters what Stripe lacks (VAT ID, Steuernummer, contact, IBAN); the newest 10 invoices are converted once, without e-mailing anyone |
| Daily use | Stripe sends invoice events for every installed account to `/stripe/webhook`; tokens are refreshed when they expire |
| Sign in again | `/anmelden` runs the same OAuth round trip, so there are no passwords |
| Uninstall | `account.application.deauthorized` (or a revoked refresh token) deletes the tokens; profile and archive stay for retention duties |

## Before publishing to the App Marketplace

- Stripe reviews public apps. Have the live site, legal pages and support
  contact ready (see `docs/launch-setup.md`), plus listing text and
  screenshots.
- Test-mode install links work before publication. Live install links work
  only after the app is published.
- Check the current permission names against Stripe's permissions reference
  before uploading. The CLI rejects unknown ones.
