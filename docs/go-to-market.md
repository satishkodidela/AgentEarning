# Go-to-market: E-Rechnung für Stripe

Status: product core built and tested (October 2026). This note answers three
questions: is it worth building, where to market it, and whether to cold-email
customers.

## 1. Is it worth building? A cautious yes, as a capped experiment

**What changed since the research report.** The report assumed the "Stripe →
German e-invoice" slot was thin. A check on 2026-10-04 showed otherwise:
Stripe does not create e-invoices itself, but it officially points users to
App Marketplace partners. Billit is its preferred partner, and Invopop and
Pennylane are also listed. Billit has a free plan and paid plans from about
€7.50/month (25 documents). Invopop targets developers and enterprises
(Pro from ~€500/month). So we would not be alone, and Stripe's own preferred
partner is cheap.

**Why it can still work:**

- **The hard part is done and reusable.** The generator and validator pass
  the official KoSIT test suite. The same engine works for any billing
  source (Chargebee, Lago, WooCommerce, CSV upload), for an API product, or
  for other countries' formats later.
- **Demand is forced by law on fixed dates:** 1 Jan 2027 for firms above
  €800k turnover, 1 Jan 2028 for everyone.
- **The free validator and rule pages are a channel of their own.** Anyone
  whose invoice is rejected, not just Stripe users, searches for "XRechnung
  prüfen" or "BR-DE-15". That traffic does not depend on the Stripe
  marketplace.
- **Billit is Belgian and Peppol-first.** German B2B practice is mostly a
  ZUGFeRD PDF sent by e-mail. A German-first product can compete on German
  depth: ZUGFeRD hybrid, Kleinunternehmer, Leitweg-ID, German fix-list
  e-mails and a German UI. *Unverified:* we could not open Billit's own
  pages, so test its German output before relying on this.

**Risks to accept up front:**

- Stripe could ship native output, or promote Billit harder.
- Many German SMEs already use lexoffice or sevDesk, which issue e-invoices
  themselves. Our segment is narrower: German businesses that bill through
  Stripe (SaaS, agencies, course sellers, freelancers with subscriptions).
- German buyers want a German-looking vendor. That means an Impressum, GDPR
  terms, a data-processing agreement (AV-Vertrag) and EU hosting.
- Liability if an e-invoice is wrong. Limit it in the terms, and keep
  sending to customers opt-in (the default is seller-only).

**Kill criteria (decide by 28 Feb 2027, two months after the first mandate
wave):** continue if any of these is true; otherwise repurpose the engine
(another billing source, an API, or France's Sept 2027 SME wave):

- ≥ 15 paying accounts, or
- ≥ 300 confirmed waitlist sign-ups, or
- ≥ 1,000 validator uses per month.

## 2. Where to market it, ranked by expected return for a solo founder

1. **The free validator plus 1,600+ rule pages (SEO, already built).**
   Target high-intent German searches: "XRechnung prüfen", "XRechnung
   Validator", "ZUGFeRD prüfen", "E-Rechnung prüfen kostenlos", "XRechnung
   Fehler BR-DE-15", "Leitweg-ID fehlt". Each rule page ends with a call to
   action for the Stripe product. Submit the sitemap to Google Search Console
   and Bing on day one. Plain-German hints exist for about 55 rules so far;
   extend them as real rejection reasons come in.
2. **One deep guide page:** "E-Rechnung mit Stripe: Checkliste für
   2027/2028" (what Stripe does and does not do, Leitweg-ID custom field,
   customer address and e-mail, Kleinunternehmer, reverse charge). This is
   the page that ranks for "Stripe E-Rechnung" / "Stripe XRechnung" and gets
   cited by AI answers.
3. **Stripe App Marketplace listing (month 2–3).** This is where Stripe users
   look, and Billit and Invopop are already there. It needs a small Stripe
   App with Connect OAuth for onboarding instead of the CLI.
4. **Tax advisors and bookkeepers (Steuerberater, Buchhaltungsbüros).** They
   tell SMEs what to do and handle many clients each, so build a
   multi-client tier for them. Reach them through content, LinkedIn posts,
   webinars, and paid placements in their association newsletters or events.
   Not cold e-mail (see section 3).
5. **Communities where the questions are asked:** r/selbststaendig,
   r/de_EDV, Indie Hackers, Stripe and SaaS founder groups in the DACH
   region, and German freelancer forums. Answer questions with the free tool
   and don't post ads.
6. **Open-source the validator core on GitHub and PyPI.** It builds developer
   trust and backlinks, and a Show HN works well for that audience. The paid
   product is the hosted automation.
7. **A small paid-search test (€5–10/day) on exact phrases** such as
   "XRechnung Stripe" and "E-Rechnung Stripe". Stop if the cost per waitlist
   sign-up is above about €20.
8. **Listicles:** ask authors of "beste XRechnung Tools 2027" articles to
   include you.

**Timing:** publish the guide and rule pages in October–November 2026.
Search interest should peak around the 1 Jan 2027 deadline and again during
2027 ahead of the 2028 wave.

## 3. Should you write e-mails to customers? Not cold ones to German businesses

German competition law (§ 7 UWG) treats e-mail advertising sent without the
recipient's *prior express consent* as an unreasonable nuisance. This applies
**to businesses as well as consumers.** A single unsolicited sales e-mail can
draw a formal warning letter (Abmahnung) with legal costs, typically sent by a
competitor or a consumer or competition association. The GDPR applies on top
when the address belongs to a person. The German Chambers of Commerce (IHK)
publish exactly this guidance. So:

- **Don't** buy lists or send cold sequences to German companies, even
  "personal" one-to-one e-mails. The research report's plan to e-mail 30–50
  founders in the first days is **replaced** by the inbound channels above.
- **Do** e-mail people who opted in. The waitlist on the landing page uses
  double opt-in and stores the consent timestamp, which is the German
  standard of proof.
- **Do** reply to people who contact you first, and e-mail your existing
  customers about similar products of your own (the § 7(3) UWG exception,
  with an opt-out in every mail).
- **LinkedIn:** publish posts and comment publicly. Treat unsolicited sales
  DMs with the same caution as e-mail.

This is general information, not legal advice. Have a German lawyer review
the terms, privacy policy and marketing setup before launch.

## 4. Pricing (adjusted to Billit's €7.50 entry price)

| Plan | Price | Includes |
|---|---|---|
| Free | €0 | Validator, rule pages, 3 conversions/month |
| Starter | €9/month | Up to 30 invoices/month, ZUGFeRD + XRechnung, archive, fix-list e-mails |
| Business | €29/month | Up to 300 invoices/month, sending to customers, Leitweg-ID handling |
| Kanzlei | €79/month | Multi-client dashboard for bookkeepers and tax advisors |

Use a 14-day trial that requires a card; card-required trials convert far
better than open freemium. About 100–150 paying accounts at a blended
~€20–25 gives roughly $2.5–3.5k MRR.

## 5. Launch checklist (owner: you)

- [ ] .de domain and EU hosting (e.g. a German data centre), HTTPS
- [ ] Impressum, Datenschutzerklärung, AGB with liability cap, AV-Vertrag
      (data-processing agreement): legal texts reviewed
- [ ] SMTP with SPF, DKIM and DMARC for the sending domain
- [ ] Merchant of record for subscriptions (Paddle, or Dodo Payments /
      Creem as fallback), plus GST registration under a Letter of Undertaking
      (LUT, the GST filing that zero-rates exports) if invoicing from India
- [ ] Test end to end with a Stripe test-mode account (restricted key and
      webhook)
- [ ] Compare Billit's German output side by side (is a ZUGFeRD PDF sent by
      e-mail? Are Kleinunternehmer and Leitweg-ID handled?) and write the
      positioning from what you find
- [ ] Google Search Console with the sitemap submitted, and the Stripe guide
      page published
