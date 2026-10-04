# Distribution Channels and Payment Setup for a Solo Developer Launching an Automated Micro-Product (late 2026)

Research date: 2026-10-04. Method note: The session's web-search budget ran out partway through, and the egress proxy blocked WebFetch for almost every primary domain tried (shopify.dev, atlassian.com, docs.stripe.com, docs.lemonsqueezy.com, polar.sh, docs.creem.io, docs.dodopayments.com, docs.apify.com, help.figma.com, dev.wix.com, developer.monday.com, sparktoro.com, seranking.com, rbi.org.in, taxmann.com, winvesta.in, extensionpay.com). So most findings below come from search-result snippets of the cited pages, not full-page reads. Where a figure comes only from a competitor's marketing blog (Dodo Payments and Fungies both publish "review"/"alternative" posts about rival merchants of record), that is flagged. Treat exact fee numbers as "verify on the vendor page before committing."

---

## 1. App marketplaces as built-in distribution: fees, earnings, discoverability, saturation

### Takeaway
At $1k–$5k MRR, the major billing-enabled marketplaces charge a solo developer **0% revenue share**: Shopify (first $1M lifetime), Atlassian Forge (first $1M lifetime from 2026), monday.com (first $200k lifetime) and Wix (first year). They also handle billing, which partly gets around the problem of Indian founders not having Stripe. Chrome Web Store has huge reach, but monetization is poor: most extensions earn nothing. Apify Store is a strong fit for an "automated product" (scrapers and automations) because it pays 80% with usage billing built in and has proven payout volume. ChatGPT's app directory and Claude's connectors directory give distribution but, per the sources found, no native way to charge for digital goods yet.

### Cited Findings

**Shopify App Store**
- Since June 16, 2025, a developer keeps 100% of the **first $1,000,000 of lifetime** App Store revenue, counted from Jan 1, 2025. Shopify takes 15% above that. The previous rule was a $1M exemption that reset every year — [Shopify.dev changelog](https://shopify.dev/changelog/update-to-shopifys-app-developer-revenue-share); [Hyper.ai summary](https://hyper.ai/en/headlines/4927cc8277cf29bbb5f930997db0fae5)
- Developers who earned ≥$20M through the App Store in the prior calendar year, or whose company revenue is ≥$100M, pay 15% on all app revenue with no exemption — [Shopify.dev changelog](https://shopify.dev/changelog/update-to-shopifys-app-developer-revenue-share)
- The change was abrupt, and developers reported having to redo their 2026 budgets — [Business Insider NL](https://www.businessinsider.nl/shopify-rolled-back-a-lifeline-it-extended-to-app-developers-during-the-pandemic); [Shopify community thread](https://community.shopify.dev/t/shopify-app-store-rev-share-coming-back/14247)
- Shopify said it paid developers more than $1B in the past year and has 16,000+ apps (secondary report; the exact year is unclear, likely 2024) — [Hyper.ai](https://hyper.ai/en/headlines/4927cc8277cf29bbb5f930997db0fae5); [Branvas Shopify ecosystem stats 2026](https://branvas.com/blogs/news/shopify-ecosystem-statistics)

**Atlassian Marketplace (Jira/Confluence)**
- From 2026, partners pay **0% revenue share on eligible Forge earnings up to $1M lifetime Forge revenue**, calculated across all of a partner's Forge apps — [Atlassian blog: Updates to Marketplace revenue share 2026](https://www.atlassian.com/blog/developer/updates-to-marketplace-revenue-share-2026); [Atlassian developer community](https://community.developer.atlassian.com/t/marketplace-revenue-share-updates-2026/91727)
- Standard rates rise in steps. The original plan was Connect 15%→20% on Jan 1, 2026 and →25% on Jul 1, 2026, with Forge 15%→16%→17%. **The timeline was extended**: Forge 15→16% on Apr 1, 2026 and 16→17% on Oct 1, 2026; Connect 15→20% on Apr 1, 2026 and 20→25% on Oct 1, 2026. New apps should therefore be built on Forge, not Connect — [Atlassian: Extended timelines](https://www.atlassian.com/blog/developer/extended-timelines-for-marketplace-revenue-share-changes); [Community thread](https://community.developer.atlassian.com/t/extended-timelines-for-marketplace-revenue-share-changes/96668)
- The Marketplace passed $4B lifetime sales in late Jan 2024, with the 4th billion taking just over a year, and later reportedly $6B. It lists 5,700–6,000+ apps from 1,800–2,000+ vendors, with ~20,000 app installs per week — [Getint](https://getint.io/atlassian-marketplace-how-to-scale-a-platform-and-ecosystem-to-10b/); [Atlassian partner program update, July 2024](https://www.atlassian.com/blog/developer/july-2024-marketplace-partner-program-tier-membership-update)

**monday.com apps marketplace**
- Developers keep 100% until an app reaches **$200,000 lifetime revenue**, then the split is 85/15. The program launched Sept 1, 2024, and monday says the 0/100 split "may change in the future" — [monday developer changelog](https://developer.monday.com/apps/changelog/announcing-the-revshare-program); [monday.com monetization page](https://monday.com/appdeveloper/monetization)

**Wix App Market**
- Developers get 100% of sales in the first year and 80% after that (20% to Wix). The share is calculated after a 2.5% transaction fee and sales tax, and payouts are net 30 EOM. Wix handles checkout. Pricing can be free trial, recurring, or usage-based — [Wix dev docs: Payments & Billing FAQ](https://dev.wix.com/docs/build-apps/launch-your-app/pricing-and-billing/payments-and-billing-faqs); [Wix: Monetize your app](https://dev.wix.com/docs/build-apps/launch-your-app/pricing-and-billing/about-monetizing-your-app)
- The App Market reportedly generated ~$140M from direct sales and partner commissions and hosts 600+ apps (secondary/aggregator source, low confidence) — [Style Factory Wix statistics](https://www.stylefactoryproductions.com/blog/wix-statistics); [Small Business Trends](https://smallbiztrends.com/wix-unveils-new-features-at-devstudio-conference-to-empower-app-developers/)
- *Inference from the 600+ figure:* that is far fewer apps than Shopify's 16k+, so there is likely less competition per category, though also smaller merchant spend.

**HubSpot App Marketplace**
- A listing needs **≥3 active unique installs**, OAuth as the only auth method, a unique use case, and passes manual review by HubSpot's Ecosystem Quality team (doc last modified Aug 22, 2025) — [HubSpot listing requirements](https://developers.hubspot.com/docs/apps/developer-platform/list-apps/listing-your-app/app-marketplace-listing-requirements)
- HubSpot runs a tiered App Partner program (partner/rising/leading/premier) based on an "influenced revenue" model rather than in-marketplace billing. Developers bill customers themselves — [HubSpot App Partner program](https://www.hubspot.com/partners/app?EPU=false); [HubSpot app-partners set-up](https://developers.hubspot.com/app-partners/set-up)

**Chrome Web Store**
- Google shut down Chrome Web Store payments (2020–21). Paid extensions now use external license keys, freemium subscriptions, or a companion web app — [Konabayev: Extension monetization statistics 2026](https://konabayev.com/blog/extension-monetization-statistics-2026/); [ExtensionPay: CWS Payments replacement](https://extensionpay.com/articles/extensionpay-is-the-chrome-web-store-payments-replacement)
- The store has ~111,933 extensions. Per Exstats, **70.4% of extensions have ≤100 users and the median extension has 18 users** — [Konabayev](https://konabayev.com/blog/extension-monetization-statistics-2026/)
- Of 112 revenue-verified browser extensions, **57.1% earn nothing and only 6.3% clear $1,000/month** (small, self-selected sample) — [Konabayev](https://konabayev.com/blog/extension-monetization-statistics-2026/)
- ExtensionPay (built on Stripe, 5% fee) says its developers have earned $500k+ in total. Free-to-paid conversion across its extensions is ~0.8%, and 0.5–2% is "realistic" — [ExtensionPay](https://extensionpay.com/); [Konabayev](https://konabayev.com/blog/extension-monetization-statistics-2026/); [DEV.to freemium extension numbers](https://dev.to/_350df62777eb55e1/real-numbers-freemium-chrome-extension-monetization-after-6-months-5hga)
- ExtensionPay publishes case studies of indie extensions with substantial revenue — [ExtensionPay: 8 Chrome extensions with impressive revenue](https://extensionpay.com/articles/browser-extensions-make-money)

**Apify Store (scrapers and automations, a natural fit for "automated" products)**
- Developers commonly receive **80% of eligible Actor revenue**. Pricing models are pay-per-result, pay-per-event, and (legacy) rental — [Apify docs: Monetize](https://docs.apify.com/platform/actors/publishing/monetize); [use-apify.com](https://use-apify.com/docs/apify-for-developers/monetize-actors)
- **The rental model is being retired**: no new rental listings from Apr 1, 2026, fully retired Oct 1, 2026. New Actors should use pay-per-event or pay-per-result — [use-apify.com](https://use-apify.com/docs/apify-for-developers/monetize-actors); [Apify docs](https://docs.apify.com/platform/actors/publishing/monetize)
- Developer payouts hit **$563K in September 2025, 6x the prior year**, and total developer payouts exceed $4M. Apify ran a $1M challenge for new Store Actors through Jan 31, 2026 — [Peerlist: The Apify $1M Challenge](https://peerlist.io/fabianmume/project/the-apify-1m-challenge); [Indie Hackers: Apify](https://www.indiehackers.com/product/apify)

**Figma Community**
- Figma takes a **15% fee** on paid Community resources. Plugins can be one-time or subscription, with a $2.00 minimum price. Selling is limited to "eligible creators" — [Figma Help: About selling Community resources](https://help.figma.com/hc/en-us/articles/12067637274519-About-selling-Community-resources). This is **contradicted** by a third-party comparison that calls it "curated, invite-only, pays 40%" — [Dodo Payments blog: Sell Figma plugins](https://dodopayments.com/blogs/sell-figma-plugins-templates). A Figma forum thread asks whether native payments are still available to plugins — [Figma forum](https://forum.figma.com/ask-the-community-7/can-plugins-still-use-figma-native-payments-monetization-54336)

**Google Workspace Marketplace**
- Google does not handle payments or verify pricing. Developers collect payment directly, and a listing can be marked Free, Paid with free trial, Paid with free features, or Paid — [Google Marketplace help](https://support.google.com/marketplace/answer/6067029?hl=en-GB); [Google Developers Blog: app pricing update](https://developers.googleblog.com/2021/10/app-pricing-update-details-and-editors.html)

**Slack Marketplace**
- Slack's App Directory is a discovery engine with no built-in checkout or subscription management, so developers build their own billing (source is a payments vendor's blog) — [Dodo Payments: How to monetize a Slack app](https://dodopayments.com/blogs/monetize-slack-app)

**Microsoft AppSource / commercial marketplace**
- Since July 2021, transactable offers (including SaaS on AppSource) pay a **3% store service fee**, down from 20% — [ITPro](https://itpro.com/cloud/platform-as-a-service-paas/360220/microsoft-lowers-marketplace-transaction-fee-to-3); [Petri](https://petri.com/microsoft-is-significantly-reducing-its-commerical-marketplace-fees/)

**ChatGPT apps (Apps SDK) directory**
- OpenAI opened app submissions to third-party developers, and the app directory launched in December 2025, with reviewed apps rolling out in early 2026. Apps are built on the Apps SDK and MCP — [VentureBeat](https://venturebeat.com/technology/openai-now-accepting-chatgpt-app-submissions-from-third-party-devs-launches); [The Decoder](https://the-decoder.com/openai-launches-app-submissions-and-rolls-out-store-in-the-new-year/)
- **Monetization is limited**: apps may link out to complete purchases **for physical goods only**. Digital goods, subscriptions, and in-app services were not yet allowed, and OpenAI said it was "exploring" more options — [Moburst](https://www.moburst.com/blog/chatgpt-app-directory-explained-what-brands-need-to-know/); [The Decoder](https://the-decoder.com/openai-launches-app-submissions-and-rolls-out-store-in-the-new-year/)
- OpenAI scaled back Instant Checkout after weak merchant uptake and moved to retailer-run apps that send users to the merchant's site — [Retail Insight Network](https://www.retail-insight-network.com/newsletters/openai-shifts-chatgpt-shopping-plans-to-retailer-run-apps-report); [Shopifreaks](https://www.shopifreaks.com/openai-scales-back-its-integrated-commerce-plans/)
- ChatGPT has 800M+ weekly active users — [Moburst](https://www.moburst.com/blog/chatgpt-app-directory-explained-what-brands-need-to-know/)

**Claude Connectors Directory**
- The directory lists verified, reviewed **remote** MCP servers (HTTP/SSE) that work across Claude.ai, Desktop, Mobile, Claude Code, and Cowork. Local npm/PyPI MCP servers cannot be listed and go to the Desktop Extensions (MCPB) gallery or the plugin directory instead. **Submitting requires a Team or Enterprise organization** with directory-management access, via Claude.ai admin settings. After publication, a dashboard shows server health and usage — [Claude docs: Connectors directory](https://claude.com/docs/connectors/directory); [Claude docs: Connectors](https://claude.com/docs/connectors)
- A third-party index counts ~1,625 connectors (unofficial) — [claudemarket.ai](https://claudemarket.ai/connectors)

### Inferences
- **The economics favor marketplaces at micro scale.** Every billing marketplace above is at or near 0% for a product earning $12k–$60k ARR: Shopify, Atlassian Forge, monday.com, Wix in year 1, and AppSource at 3%. A self-billed MoR costs ~6–10% by comparison (see Section 5). The real cost of a marketplace is platform risk: Shopify changed its terms abruptly in 2025, and Atlassian and monday both say terms can change.
- **Billing-enabled marketplaces partly solve the India payment problem.** The marketplace collects from customers worldwide and pays the developer, which removes the need for Stripe or global VAT registration. I could not verify each marketplace's payout options for India (see Gaps).
- **Ranking for "first $1k–5k MRR with minimal manual effort"** (my judgment from the evidence):
  1. Atlassian Forge, monday.com, and Shopify: business buyers, built-in billing, intent-driven search inside the store.
  2. Apify Store: usage billing, proven payout volume, and an exact fit for automation and scraping products.
  3. Wix: smaller catalog, so probably less crowded.
  4. Chrome Web Store: reach but weak monetization, so it works best as a funnel to a paid web app.
  5. HubSpot, Slack, Google Workspace, and Zapier: discovery only, so you bring your own billing.
  6. ChatGPT and Claude directories: distribution and brand exposure, but not a direct revenue channel as of these sources. The Claude directory also needs a Team/Enterprise org to submit.
- On saturation, Atlassian's 6k apps across 2k vendors is moderately crowded, but the Forge incentive suggests Atlassian wants more Forge apps. That probably means newer or less-covered Forge categories (Jira Service Management, Confluence automation, compliance/audit) have room, but I found no data to confirm specific underserved categories.

### Gaps
- I found **no reliable category-level saturation or "underserved category" data** for any marketplace. Third-party app-store analytics (e.g., Shopify app counts by category, Atlassian Marketplace category install counts) could not be searched before the budget ran out.
- **Median or typical developer earnings** per marketplace are mostly undisclosed. Only aggregates exist: Shopify ~$1B+/yr, Atlassian $6B lifetime, Apify $563K/month.
- **Payout support for India-resident developers** (bank wire vs PayPal vs Payoneer, FIRA availability) was not verified for Shopify, Atlassian, monday.com, Wix, Figma, or Apify.
- Zapier and WordPress.org: no fee or earnings data found. From pre-2026 background knowledge, unverified here: Zapier's app directory has no billing or revenue share, and WordPress.org hosts free plugins only, with monetization through freemium upsells off-directory.
- The Chrome Web Store developer registration fee could not be verified in this session.
- **ChatGPT app monetization status as of Oct 2026**: the sources found date from Dec 2025–early 2026, and I could not check whether OpenAI has since allowed digital goods or subscriptions.
- Claude directory: no data on traffic or installs that listed connectors receive.
- Figma: whether new sellers can still sign up, and whether the fee is 15% or something else, is unresolved (conflicting sources).

---

## 2. Search in the AI-answer era: AI Overviews / AI Mode click loss, LLM referral traffic, "get recommended by LLMs" tactics

### Takeaway
Google is still the largest traffic source, but it sends far fewer clicks. Ahrefs measured AI Overviews cutting the top result's CTR by ~34.5% (Apr 2025), then ~58% (Dec 2025), and AI Mode is ~93% zero-click. LLM referrals are growing fast (16x from 2024 to 2026) but are still tiny, at ~0.3% of all web traffic, with ChatGPT the dominant sender. The strongest measured predictors of being mentioned by LLMs are **brand mentions across the web (especially YouTube)** and **inclusion in "best X" listicles**, not backlinks.

### Cited Findings

**Google AI Overviews / AI Mode click loss**
- Ahrefs (April 2025; 300k keywords, Search Console data from March 2025) found AI Overviews correlated with a **34.5% lower CTR** for the #1 page — [eMarketer](https://www.emarketer.com/content/google-ai-overviews-decrease-ctrs-by-34-5-per-new-study); [PPC Land](https://ppc.land/googles-ai-overviews-cut-organic-clicks-by-34-5-despite-company-claims/)
- Ahrefs (December 2025; 150k AIO keywords vs 150k informational keywords without AIO) found a **~58% lower CTR**. Position-1 CTR on AIO keywords fell from 0.073 (Dec 2023) to 0.016 (Dec 2025) — [PPC Land](https://ppc.land/googles-ai-summaries-now-swallow-58-of-clicks-that-once-went-to-websites/); [MediaNama, Feb 2026](https://www.medianama.com/2026/02/223-google-ai-overviews-click-through-rates-58-study/); [Business Wire via Morningstar, May 2026](https://www.morningstar.com/news/business-wire/20260518322756/new-research-googles-ai-overviews-now-cost-websites-58-of-their-clicks)
- Seer Interactive (3,119 informational queries, 42 organizations, Jun 2024–Sep 2025) found organic CTR on AIO queries fell from **1.76% to 0.61%** — as reported by [Digitaleer](https://www.digitaleer.com/ai-impact-google-search-traffic-2026/) and [Passionfruit](https://www.getpassionfruit.com/blog/how-ai-overviews-are-affecting-click-rates-on-google-and-best-practices-to-navigate-through-them)
- **AI Mode has a ~93% zero-click rate** (Semrush / Seer research) — [Digitaleer](https://www.digitaleer.com/ai-impact-google-search-traffic-2026/)
- Users clicked a traditional result in **8% of visits with an AI Overview vs 15% without** one. AI Overviews appear on 20%+ of searches — [Digitaleer](https://www.digitaleer.com/ai-impact-google-search-traffic-2026/)
- SparkToro, using Similarweb US desktop and mobile panel data for Jan–Apr 2026, found **fewer than one-third of Google searches still send a click** to the open web — [SparkToro](https://sparktoro.com/blog/in-2026-less-than-one-third-of-google-searches-still-send-a-click/?hl=en-US); [Search Engine Land](https://searchengineland.com/google-zero-click-searches-2026-study-479717)
- Chartbeat (March 2026) found search referrals down **60% for small publishers, 47% for medium, 22% for large** — [Gist](https://gist.ai/blog/zero-click-crisis-publisher-traffic); [WebProNews](https://www.webpronews.com/googles-ai-search-push-leaves-publishers-fighting-for-every-click/)

**LLM referral traffic volumes (2025–2026)**
- AI platforms account for **0.32% of all website traffic in 2026**, up from 0.24% in 2025 and 0.02% in 2024 (16x growth). By AI referrals, SE Ranking puts ChatGPT at 74.78%, Gemini 11.56%, Perplexity 7.23%, Copilot 3.51%, and Claude 2.62% — [SE Ranking AI traffic study](https://seranking.com/blog/ai-traffic-research-study/)
- Previsible's third AI Traffic Study (6.77M LLM sessions across 166 sites, including SaaS) found monthly LLM sessions grew **9.9x to ~644,478 in May 2026**, with **92.4% from ChatGPT**. Gemini grew 3.2x. **Claude grew 64x and passed Perplexity in March 2026**, with particular strength among developers and technical buyers. Tech, SaaS, and finance lead AI-traffic adoption at 18–25% (metric definition unclear) — [Las Vegas Sun / Previsible release, Jul 2026](https://lasvegassun.com/news/2026/jul/06/previsibles-2026-state-of-ai-discovery-report-find/); [SEO-Day](https://www.seo-day.de/news/article/chatgpt-commands-92-of-ai-referral-traffic-heres-what-677?lang=en); [Search Engine Land](https://searchengineland.com/chatgpt-ai-referral-traffic-sessions-data-481630)
- ChatGPT referral traffic rose **36.7% in May 2026**, an all-time high, after ChatGPT began showing more prominent brand links around May 7. Referral visits rose ~150% comparing the week before May 7 with the period after — [SE Ranking, May 2026](https://seranking.com/blog/chatgpt-referral-traffic-may-2026/)
- In **B2B specifically** (Goodie, Mar–Apr 2026), ChatGPT's share of measurable AI referrals fell to 62.6%, with **Claude at 18.5%**, Gemini 10.6%, and Perplexity 7.3% — [Goodie AI search traffic report 2026](https://higoodie.com/blog/ai-search-traffic-report-2026/)
- Similarweb, measuring visits *to* AI platforms rather than referrals, found ChatGPT's share fell from ~76% (Jun 2025) to ~53% (May 2026), Gemini rose to ~27–28%, and Claude to ~9% — [Similarweb AI search stats](https://aisearch.similarweb.com/blog/gen-ai-stats/)
- **The sources conflict on ChatGPT's share of AI referrals**: 92.4% (Previsible), 74.78% (SE Ranking), and 62.6% for B2B (Goodie). The differences come from methodology and site mix — [Something Inc: why AI market share numbers disagree](https://somethinginc.com/blog/ai-search-market-share-numbers-disagree/)

**"Get recommended by LLMs" tactics (evidence-based)**
- Ahrefs studied 75,000 brands. For AI Overview visibility, **branded web mentions** correlated at 0.664, branded search volume at 0.392, and **backlinks at only 0.218**. Domain rating and page count were weak — [Ahrefs: AI brand visibility correlations](https://ahrefs.com/blog/ai-brand-visibility-correlations); [Ahrefs: AI Overview brand correlation](https://ahrefs.com/blog/ai-overview-brand-correlation/?cId=cj)
- **YouTube mentions** were the strongest single correlate (Spearman ~0.737) of brand visibility across ChatGPT, AI Mode, and AI Overviews — [The Next Web](https://thenextweb.com/news/ahrefs-youtube-mentions-ai-visibility-brand-search); [LetsDataScience](https://letsdatascience.com/news/youtube-mentions-drive-brand-ai-visibility-e09aea79)
- Google appears more biased toward big brands than ChatGPT and Perplexity are — [Ahrefs](https://ahrefs.com/blog/branded-web-mentions-visibility-ai-search/)
- **"Best X" listicles were 43.8% of all cited pages** (Ahrefs, 26,283 URLs). In AIVO's June 2026 test of 138 ChatGPT queries, **every commercial "best X for Y" answer cited at least one listicle**. Profound (~730k ChatGPT conversations) found citations are long-tail: the top 10 domains get only 12%, Wikipedia ~5%. Reddit and LinkedIn are ~10% of citations — as compiled by [Reditus: How to get cited by LLMs](https://getreditus.com/blog/how-to-get-cited-by-llms) and [DataDab SaaS AI Citation Index, Apr 2026](https://www.datadab.com/research/saas-ai-citation-index) (secondary compilations; the primary studies were not read)
- One compilation claims "corporate sites account for more than 77% of citations," which sits uneasily with the listicle figures. The likely explanation is that different studies measure different things: listicles on corporate blogs count as both — [Reditus](https://getreditus.com/blog/how-to-get-cited-by-llms)

### Inferences
- For a new micro-product, **Google organic is still worth targeting for bottom-of-funnel, tool-intent and comparison queries**, but informational blog content is now a poor bet because AIO and AI Mode absorb most of those clicks.
- **LLM referral traffic is small but high-intent and growing quickly**, and it is tilting toward Claude among developers and B2B buyers. A practical, low-maintenance playbook from the correlations above:
  - get listed in third-party "best X for Y" listicles, including small niche blogs;
  - publish your own honest "best X" and "X vs Y" pages;
  - earn YouTube mentions (demos, reviews);
  - answer in relevant Reddit threads;
  - keep docs, pricing, and integration pages crawlable and factual.
- Being a listed ChatGPT app or Claude connector is a separate, in-product route to LLM visibility, with a different mechanism from citations.

### Gaps
- No reliable 2025–2026 study isolating **conversion rates of LLM-referred visitors vs organic visitors for SaaS** was retrieved (the search budget was exhausted before that query).
- No absolute numbers for how much referral traffic Claude.ai or Perplexity send to a *typical small* SaaS site; the studies above are aggregates across larger sites.
- The primary Ahrefs listicle study, AIVO, and Profound data were seen only through secondary compilations.

---

## 3. Community and launch channels (Product Hunt, Show HN, Reddit, X, niche forums, cold email, LinkedIn)

### Takeaway
Launch platforms (Product Hunt, Show HN) produce a **one-time spike of hundreds to thousands of visitors and tens to hundreds of signups**, but paid conversion is often weak. They are best treated as a backlink and social-proof event, not as recurring acquisition. Reddit is high-intent but punishes self-promotion. Cold email still works for B2B, but since Nov 2025 Gmail actively *rejects* non-compliant bulk mail, and Microsoft has enforced authentication since May 2025, so it now needs proper infrastructure and low volume per inbox. I found no hard data on X build-in-public or LinkedIn outcomes.

### Cited Findings

**Product Hunt**
- Typical ranges (from a playbook compilation, not primary data): **#1 Product of the Day gets 5k–15k uniques and 500–3,000 signups**; top 3 get 3k–8k uniques and 200–1,000 signups; top 5 get 2k–5k uniques and 100–500 signups. The long tail (digest, backlinks, SEO) can add 2–5x more traffic over the following weeks — [DEV.to: Product Hunt playbook](https://dev.to/insightlab/the-product-hunt-playbook-turning-a-one-day-launch-into-months-of-growth-for-bootstrapped-saas-1hl3)
- Founder-reported results:
  - Claap: 1,400 upvotes, ~1,000 signups in launch week, 3,000 signups over 6 weeks, ~$60k revenue.
  - A bootstrapped time-tracking SaaS: #2 of the day with 1,847 upvotes, 140 signups, 22 paid.
  - The Hack Stack: 133 launch-day signups at a 10.73% conversion rate.

  Sources: [Founderpath](https://founderpath.com/blog/launch-on-product-hunt); [The Hack Stack](https://thehackstack.substack.com/p/a-successful-product-hunt-launch); [Indie Hackers: 800 new users from PH](https://www.indiehackers.com/post/how-we-got-800-new-users-thanks-to-the-product-hunt-launch-c37d21b850)
- A counter-example: "400 signups from Product Hunt, 1 paying customer" — [Indie Hackers](https://www.indiehackers.com/post/400-signups-from-product-hunt-1-paying-customer-what-4-days-taught-me-about-launch-vs-traction-7c0aacf745)

**Hacker News (Show HN)**
- Founder-reported results:
  - Routific (61 points): 6,899 visits, 9,300 pageviews, 125 early-access signups, 99 API accounts.
  - Front: 6,174 uniques, 96 company signups, 65 qualified leads.
  - Aidlab front-page postmortem: ~6k pageviews and ~500+ uniques directly from HN.

  Sources: [Routific](https://www.routific.com/blog/what-61-points-on-hacker-news-did-for-my-startup); [Indie Hackers: front page postmortem](https://www.indiehackers.com/post/front-page-of-hn-the-full-postmortem-traffic-lessons-surprises-cbe9e0a7f6); [Indie Hackers: first place on HN](https://www.indiehackers.com/post/first-place-on-hackernews-stats-traffic-and-regs-46b8b95333)
- A 2026 playbook estimates **50–500 signups in 24h** for a successful Show HN and recommends posting **Tue–Thu, 7–10am PT** — [Causo: Show HN playbook 2026](https://hub.causo.ai/guides/show-hn-launch-playbook-technical-founders-2026); [Flowjam](https://www.flowjam.com/blog/how-to-get-on-the-front-page-of-hacker-news-in-2025-the-complete-up-to-date-playbook)

**Reddit**
- Agency playbooks (low-quality sources with commercial bias) recommend **3–6 months of community-first participation before promoting**, a 90/10 value-to-promotion ratio, data-led posts, and AMAs. They claim Reddit B2B CPCs of $0.50–$2 vs LinkedIn's $8–10+, and say Reddit now ranks prominently in Google and feeds ChatGPT, Perplexity, and Gemini answers. The ROI case studies ("$500K+ ARR") come from agencies and are unverified — [Dupple: Reddit for B2B SaaS 2026](https://dupple.com/learn/reddit-marketing-b2b-saas-playbook); [Indie Hackers: Reddit marketing services 2026](https://www.indiehackers.com/post/best-reddit-marketing-services-for-saas-in-2026-fc8ba5da02)
- Reddit and LinkedIn together make up ~10% of LLM citations (see Section 2) — [Reditus](https://getreditus.com/blog/how-to-get-cited-by-llms)

**Cold email and deliverability rules**
- **Gmail**: from **November 2025**, non-compliant bulk mail is rate-limited or rejected with 5xx errors, no longer just filtered to spam. Senders of 5,000+/day to Gmail need SPF, DKIM, DMARC alignment, one-click unsubscribe, and a spam rate **below 0.3% (target <0.1%)**. Above 0.3%, a sender loses mitigation support until the rate stays under 0.3% for 7 consecutive days — [PowerDMARC](https://powerdmarc.com/gmail-enforcement-email-rejection/); [Red Sift](https://redsift.com/resources/blog/gmails-enforcement-ramps-up-what-bulk-senders-need-to-know); [CaptainDNS](https://www.captaindns.com/en/blog/gmail-bulk-sender-2025)
- **Microsoft (Outlook.com / Hotmail / Live)**: from **May 5, 2025**, senders of 5,000+/day must pass SPF and DKIM and publish DMARC (at least p=none, aligned with SPF or DKIM). They also need valid From/Reply-To addresses, one-click unsubscribe, and list hygiene. Non-compliant mail goes to Junk, and rejections like "550 5.7.515" are possible — [Resend](https://resend.com/blog/microsoft-bulk-sending-requirements-2025); [dmarcian](https://dmarcian.com/microsoft-enforces-spf-dkim-dmarc/); [BuzzStream](https://buzzstream.com/blog/microsoft-email-requirements/)
- **Benchmarks** (Instantly 2026 Cold Email Benchmark): average reply rate **3.43%**, top quartile 5.5%+, top 10% 10.7%+. 58% of replies come from the first email. The best sequences are 4–7 steps with emails under 80 words, and consistent sending volume gets 15–20% more replies than erratic sending — [Instantly: Email sequence benchmarks 2026](https://instantly.ai/blog/email-sequence-benchmarks-2026-whats-a-good-open-rate-reply-rate-and-cost-per-meeting/); [Lemlist cold email benchmarks](https://lemlist.com/blog/cold-email-benchmarks/)

### Inferences
- For "minimal ongoing manual effort," **launches are a one-time effort**: Product Hunt plus Show HN plus a few niche subreddits in launch week. They are worth doing for backlinks, listicle pickup, and LLM mention signals, but should not be relied on for MRR.
- At a ~3.4% average reply rate, cold email to ~1,000 well-targeted prospects gives ~34 replies. That can plausibly yield a handful of early B2B customers. It is the most *controllable* B2B channel but the opposite of "automated": it needs separate sending domains, warm-up, and low per-inbox volume to stay well under the 5,000/day bulk thresholds and the 0.3% spam ceiling.
- **Combined with Section 1**, marketplace listings and SEO/LLM-visibility assets are the channels that compound with near-zero ongoing effort. Launches and cold email are bursts.

### Gaps
- **X / build-in-public**: no quantitative 2025–2026 data retrieved on follower-to-customer conversion or reach changes.
- **LinkedIn organic**: no data retrieved.
- **Niche forums** (e.g., IndieHackers, vertical communities): no data retrieved.
- Product Hunt and HN figures are founder self-reports and playbook estimates, several from before 2025. No large-sample 2025–2026 dataset on PH/HN-to-paid conversion was found.

---

## 4. Programmatic SEO done right: data-backed pSEO still ranking in 2025–2026

### Takeaway
The cited pSEO successes are big brands with **proprietary or structured data behind each page**: Zapier integration pages, G2 comparisons, TripAdvisor locations. Templated pages that add no unique data are what Google's spam policies target. For a solo developer, pSEO works best when each page is backed by real data the product generates, such as integration pairs, tool outputs, or benchmarks.

### Cited Findings
- **Zapier** has 70,000+ programmatic integration pages, ranks for 400k+ keywords, and gets ~6.3M monthly organic visits — [Gracker.ai: pSEO case studies 2025](https://gracker.ai/blog/10-programmatic-seo-case-studies--examples-in-2025) (vendor blog; figures not verified against Ahrefs or Semrush)
- **G2** saw traffic grow 300% in a year after adding programmatic comparison pages, which convert 1.7x better than its editorial content — [Gracker.ai](https://gracker.ai/blog/10-programmatic-seo-case-studies--examples-in-2025)
- **TripAdvisor** ranks for 15M+ keywords via algorithmic location pages — [Gracker.ai](https://gracker.ai/blog/10-programmatic-seo-case-studies--examples-in-2025)
- Claims that pSEO lifts organic traffic "212% on average in year one" come from marketing-statistics compilations of unclear provenance (treat as unreliable) — [Gracker.ai](https://gracker.ai/blog/10-programmatic-seo-case-studies--examples-in-2025); [Shno pSEO stats](https://www.shno.co/marketing-statistics/programmatic-seo-statistics)
- AI Overviews hit informational queries hardest (Seer's sample was informational queries; Ahrefs compared AIO keywords with informational keywords), so pSEO pages aimed at tool, transactional, or comparison intent face less AIO click loss — [Digitaleer](https://www.digitaleer.com/ai-impact-google-search-traffic-2026/); [PPC Land](https://ppc.land/googles-ai-summaries-now-swallow-58-of-clicks-that-once-went-to-websites/)

### Inferences
- Good pSEO patterns for a micro-product, by analogy to Zapier and G2:
  - "[Your tool] + [integration]" pages;
  - "[X] vs [Y]" comparisons built from real feature and pricing data;
  - per-entity data pages where the product computes something unique, such as a calculator output, a dataset slice, or live stats.
- Because LLMs cite listicles and comparison pages heavily (Section 2), data-backed comparison pages likely do double duty, serving both Google and LLM citation.

### Gaps
- The search budget ran out before I could retrieve **2025–2026 primary evidence on Google's "scaled content abuse" enforcement** (spam policy introduced March 2024, per background knowledge, not verified here) or small-site pSEO examples still ranking after the 2025 core updates.
- No independent, recent (2025–2026) traffic verification for the Zapier, G2, and TripAdvisor figures.

---

## 5. Payments for non-US (India-based) solo founders: Stripe, MoR options, US LLC route, GST/LUT, FIRA/e-BRC, RBI/FEMA

### Takeaway
New Indian businesses still can't self-onboard to Stripe. It has been **invite-only since May 2024**, and the promised H2-2025 reopening had not happened per current Stripe docs. The practical default for an Indian solo founder selling globally in USD is a **Merchant of Record**, which collects payment, remits worldwide VAT/GST/sales tax, and pays out to India:
- Paddle: 5% + $0.50
- Lemon Squeezy / Stripe Managed Payments: 5% + $0.50
- Creem: 3.9% + $0.40, plus payout fees
- Dodo Payments (India-founded): 4% + $0.40 + 1.5% international
- Polar: 5% + $0.50 since May 2026
- Gumroad: 10% + $0.50

On the Indian side, exports of services are zero-rated under GST with an annual LUT. Each remittance needs a purpose code and FIRA/e-FIRA proof. **New FEMA export regulations took effect on October 1, 2026**: SOFTEX is replaced by a unified EDF, and the services realisation period is 9 months after a June 2026 amendment. The US-LLC/Stripe Atlas route triggers ODI rules and Indian worldwide taxation and is not simple for an Indian resident.

### Cited Findings

**Stripe in India**
- Since May 2024, new Indian businesses can't open Stripe accounts directly and must request an invite. Accounts created before May 2024 continue to work. Stripe cited the evolving regulatory landscape and said it would build infrastructure to support more users by H2 2025 — [Outlook Business](https://www.outlookbusiness.com/corporate/stripe-shifts-to-invite-only-model-in-india-plans-infrastructure-boost-by-2025); [MediaNama](https://www.medianama.com/2024/06/223-stripe-invite-only-services-in-india-temporarily-citing-regulations/); [The Paypers](https://thepaypers.com/payments/news/stripe-moves-to-invite-only-in-india)
- Stripe's India exports doc is still labelled **"Invite only."** Invites go mainly to businesses focused on international expansion. For exports, services sellers don't need an IEC unless they accept AMEX from international customers or claim Foreign Trade Policy benefits — [Stripe docs: Accept international payments from India](https://docs.stripe.com/india-exports); [Stripe support](https://support.stripe.com/questions/accepting-international-payments-from-stripe-accounts-in-india)

**Stripe Managed Payments / Lemon Squeezy (acquired by Stripe in 2024)**
- Timeline: Lemon Squeezy announced Stripe Managed Payments in **January 2026**; a public preview opened in **February 2026**; by **April 2026** Stripe had added a `managed_payments` flag to Checkout Sessions and Payment Links. Stripe acts as MoR for VAT, GST, and sales tax, plus fraud and customer transaction support. Pricing is **5% + $0.50**, the same as Lemon Squeezy. As of April 2026, Lemon Squeezy still runs as a standalone product — [Fungies](https://fungies.io/lemon-squeezy-stripe-acquisition-saas-founders-2026/); [Dodo Payments blog](https://dodopayments.com/blogs/lemon-squeezy-vs-stripe/) (both are competitor blogs; not verified on stripe.com)
- Lemon Squeezy payouts are bank wire (79 countries) or PayPal (200+ countries), twice a month. Reported payout fees are 1% for bank and 3% (up to $30) for PayPal. Indian merchants may need to use PayPal for payouts — [Lemon Squeezy docs: Supported countries](https://docs.lemonsqueezy.com/help/getting-started/supported-countries); [Lemon Squeezy docs: Getting paid](https://docs.lemonsqueezy.com/help/getting-started/getting-paid); [LearnWithHasan](https://learnwithhasan.com/payment-gateways/lemonsqueezy/)

**Paddle**
- **5% + $0.50 per transaction**, covering processing, global tax compliance, fraud, and chargebacks — [ERP Research: Paddle pricing](https://erpresearch.com/erp-add-ons/billing-subscriptions/paddle/pricing); [Paddle: India](https://www.paddle.com/billing/india)
- Payouts are monthly: the balance converts on the 1st and is paid by the 15th, via **wire transfer or Payoneer**. Paddle generates a **"Reverse Invoice"** for each payout. The seller's sale to Paddle is a cross-border B2B supply under reverse charge — [Paddle help: When and how do I get paid](https://www.paddle.com/help/manage/get-paid/when-and-how-do-i-get-paid); [Paddle help: Do I need to invoice Paddle](https://www.paddle.com/help/manage/get-paid/do-i-need-to-invoice-paddle-for-my-payout); [Paddle: Should I charge Paddle VAT](https://paddle.com/support/should-i-charge-paddle-vat-tax-for-payouts)

**Polar.sh**
- Open-source MoR built on Stripe Connect Express (payouts) and Stripe Payments. It launched v1.0 in Sept 2024 and raised a $10M Accel-led seed in 2025. **On May 27, 2026 Polar moved from a flat 4% + $0.40 to tiered plans; the free Starter plan is 5% + $0.50.** Reported surcharges: +1.5% for international cards, +0.5% for subscriptions, $15 per chargeback, and Stripe payout fees passed through — [Polar blog: Introducing Polar Plans](https://polar.sh/blog/introducing-polar-plans); [Fungies: Polar review 2026](https://fungies.io/polar-sh-review-2026); [Dodo Payments: Polar review](https://dodopayments.com/blogs/polar-sh-review) (surcharge details come from competitor blogs)

**Creem**
- **3.9% + $0.40** per transaction. Payout fee is $7/€7 or 1% of the payout, whichever is higher, plus 2% for USDC payouts. Payouts go out on the 1st and 15th with a $50/€50 minimum, to merchants in 86 countries (India appears to be included). Creem reportedly lacks UPI for Indian buyers — [Creem docs: Supported countries](https://docs.creem.io/merchant-of-record/supported-countries); [Creem docs: Payouts](https://docs.creem.io/merchant-of-record/finance/payouts); [Fungies comparison](https://fungies.io/dodo-payments-vs-creem-vs-fungies-mor-indie-hackers-2026)

**Dodo Payments (India-founded MoR)**
- Founded in 2023 by Rishabh Goel and Ayush Agarwal; India-based — [Skydo: Dodo Payments features and fees](https://web.skydo.com/blog/dodo-payments-features-and-fees)
- Fees: **4% + $0.40** for US customers, **+1.5%** for international customers outside the US, and 4% + 15¢ for domestic India payments (cards and UPI). Payouts for India merchants cost ₹5 per domestic payout and "$5 + 1%" per international payout (wording ambiguous). It supports 25+ local payment methods including UPI and 150+ buyer countries — [Dodo Payments pricing](https://dodopayments.com/de/pricing); [Dodo docs: Pricing and fee structure](https://docs.dodopayments.com/miscellaneous/pricing-and-fee-structure); [Dodo blog: Stripe alternatives India](https://dodopayments.com/blogs/stripe-alternatives-india)

**Gumroad**
- Gumroad has been a **full MoR since January 2025**. It charges **10% + $0.50** on direct sales and **30%** on sales through Gumroad Discover, with no monthly fee — [Checkoutpage](https://checkoutpage.com/blog/gumroad-fees); [SchoolMaker](https://schoolmaker.com/blog/gumroad-pricing). The sources **conflict** on whether processing is extra: one estimates ~12.9% + $0.80 all-in by adding ~2.9% + $0.30 processing; another says processing is bundled — [Dodo Payments blog](https://dodopayments.com/blogs/gumroad-fees-explained)

**US LLC / Stripe Atlas route for an Indian resident**
- Stripe's own guide says Atlas "is not designed to support Indian founders." An Indian resident is expected to set up an **Indian LLP first**, obtain a UIN for the US company, and buy its stock through the LLP's AD bank under the **2022 ODI regulations**. Creating a foreign entity as an individual can breach FEMA. Even paying the incorporation fee can count as ODI. Annual RBI reporting applies — [Stripe docs: Indian founder guide](https://docs.stripe.com/atlas/indian-founder-guide.md); [Stripe support: Can I use Atlas if I live in India?](https://support.stripe.com/questions/can-i-use-stripe-atlas-if-i-live-in-india)
- India taxes residents on worldwide income, so US-LLC income is generally taxable in India. Business Today (Mar 2026) notes that forming a US LLC to get Stripe is "legitimate" but creates substantial compliance work — [Business Today, Mar 10, 2026](https://www.businesstoday.in/amp/impact-feature/story/forming-a-us-llc-to-access-stripe-is-a-legitimate-move-the-tax-compliance-it-creates-is-not-small-519932-2026-03-10); [Dinesh Aarjav & Associates](https://www.dineshaarjav.com/blog-detail/us-llc-corporate-tax-in-india)

**GST: export of services / LUT**
- A SaaS supply is an **export of services** under Sec 2(6) of the IGST Act only if all of these hold:
  - the supplier is in India;
  - the recipient is outside India;
  - the place of supply is outside India;
  - payment is received in convertible foreign exchange;
  - the parties are not merely establishments of the same entity.

  Valid exports are **zero-rated**: 0% GST with input tax credit kept and refundable. The exporter either files an **LUT** (no IGST upfront; renewed annually before March 31) or pays 18% IGST and claims a refund. Place of supply for SaaS/OIDAR is the recipient's location. FIRC/BRC and compliant export invoices are required — [Tally: GST for software/SaaS exports](https://tallysolutions.com/gst/gst-software-saas-exports-international-clients/); [Patron Accounting: GST on SaaS exports & LUT](https://www.patronaccounting.com/blog/gst-on-saas-exports-lut); [Xflow: GST on software services](https://www.xflowpay.com/blog/gst-on-software-services)
- If the money arrives in India as INR rather than foreign exchange, export status and 0% GST can be at risk — [Skydo: How GST affects foreign payments](https://web.skydo.com/blog/how-does-gst-affect-foreign-payments)

**FIRA / e-BRC / purpose codes**
- FIRA (Foreign Inward Remittance Advice) is issued by the AD bank to confirm foreign export proceeds arrived through banking channels. It supports FEMA compliance, GST zero-rating, and income tax filings. e-BRC ties goods and software exports to realised proceeds — [Skydo: Importance of FIRA](https://web.skydo.com/blog/importance-of-fira-for-freelancers); [Winvesta: FIRC vs FIRA vs e-BRC 2026](https://www.winvesta.in/blog/businesses/firc-vs-fira-vs-e-brc-which-proof-of-foreign-payment-do-you-actually-need); [PhonePe Business: FIRA](https://business.phonepe.com/articles/what-is-fira-foreign-inward-remittance-advice-how-exporters-use-it-for-gst-filing)
- RBI requires a **purpose code** on each inward remittance. Common ones are **P0802** (software implementation/consultancy) and **P0807** (off-site software exports) — [Xflow: Purpose codes for freelancers](https://beta.xflowpay.com/blog/purpose-code-for-freelancers); [Tazapay changelog 2025](https://developer.tazapay.com/changelog/2025/purpose-codes-update-for-inr-payouts.md)
- Razorpay International auto-generates an eFIRC per transaction for Indian-entity accounts — [Sprintzeal (secondary)](https://www.sprintzeal.com/blog/stripe-alternatives-indian-saas-global-payments); [Razorpay blog](https://razorpay.com/blog/upwork-fiverr-payments-indian-freelancers/)

**RBI / FEMA: new 2026 export regulations (very fresh; took effect 3 days before this note)**
- The **Foreign Exchange Management (Export and Import of Goods and Services) Regulations, 2026** (notification **FEMA 23(R)/2026-RB**) were gazetted on **Jan 13, 2026** and took effect on **Oct 1, 2026**. They replace 167 circulars and the 2015 framework.
  - **SOFTEX is abolished** and replaced by a unified Export Declaration Form (EDF).
  - Software is treated as a sub-category of services.
  - AD banks are recognised as a "Specified Authority" alongside STPI, so software exporters outside SEZs can have exports certified by their bank.

  Sources: [Winvesta: SOFTEX is dead](https://www.winvesta.in/blog/businesses/softex-is-dead-indias-new-export-filing-system-explained); [iSPIRT: EDF replaces SOFTEX](https://pn.ispirt.in/tag/saas/); [Mondaq](https://www.mondaq.com/article/1736644); [CalcGuru](https://calcguru.in/?p=3760)
- **Realisation period**: originally **15 months** from invoice for services (18 months if invoiced in INR), then **reduced to 9 months by a June 2026 amendment** for software and services exports — [Taxmann: RBI restores realisation period to 9 months](https://www.taxmann.com/post/blog/rbi-restores-export-proceeds-realisation-period-to-9-months/); [RBI FEMA notification](https://rbi.org.in/SCRIPTS/BS_FemaNotifications.aspx?Id=13277); [TaxGuru](https://taxguru.in/?p=1021425)

**Income tax (simplest option for a solo resident individual)**
- Under **Section 44AD presumptive taxation**, eligible resident individuals, HUFs, and partnership firms (not LLPs or companies) declare **6% of turnover** as profit for digital or banking receipts (8% otherwise). The turnover cap is ₹2 crore, or **₹3 crore if ≥95% of receipts come through banking channels**, which foreign receipts via bank satisfy. No books or audit are required, and the scheme locks in for 5 years once chosen — [Xflow: Section 44AD](https://www.xflowpay.com/blog/44ad-income-tax-act); [Bajaj Finserv](https://bajajfinserv.in/investments/section-44ad-of-income-tax-act)

### Inferences
- **Effective fee per $20/month subscription**, computed from the cited rate cards (before payout and FX fees):

  | Provider | Rate | Cost | Effective |
  |---|---|---|---|
  | Paddle | 5% + $0.50 | $1.50 | 7.5% |
  | Lemon Squeezy / Stripe Managed Payments | 5% + $0.50 | $1.50 | 7.5% |
  | Creem | 3.9% + $0.40 | $1.18 | 5.9% (plus 1% payout, min $7) |
  | Dodo (non-US buyer) | 4% + 1.5% + $0.40 | $1.50 | 7.5% |
  | Polar Starter (intl card, subscription) | 5% + 1.5% + 0.5% + $0.50 | $1.90 | ~9.5% |
  | Gumroad | 10% + $0.50 | $2.50 | 12.5%+ |

  At $1k–$5k MRR, the spread between the cheapest and dearest is ~$40–$330/month. **Payout reliability to India and FIRA availability matter more than headline fees.**
- **Recommended stack for an India-resident solo founder (inference):**
  1. Sell through an MoR. Paddle has the most established reverse-invoice process. Dodo is India-native with UPI and INR features. Creem is cheapest per transaction.
  2. Receive payouts into an Indian bank account in foreign currency with the right purpose code (P0807 or P0802) and obtain FIRA/e-FIRA.
  3. Get GST registration and an annual LUT so the supply to the MoR is a zero-rated export.
  4. Use 44AD at 6% while turnover stays under ₹3 crore.
  5. Under the new 2026 FEMA rules, file EDF/declarations via the AD bank and make sure proceeds arrive within 9 months. MoRs pay out monthly or twice monthly, so this is easy to meet.
  6. Avoid the US-LLC route at this revenue level unless an LLP-based ODI structure is acceptable.
- **A key unresolved structural point**: when an Indian founder sells *through an MoR*, the founder's legal customer is the MoR (Paddle is UK/US; Creem's and Dodo's MoR entity jurisdictions were not verified). Export-of-services status, and so 0% GST, depends on that MoR entity being **outside India** and paying in foreign currency. If an MoR contracts through an Indian entity or pays out in INR, GST treatment could differ. This needs a CA's confirmation per provider.
- Billing marketplaces (Shopify, Atlassian, monday, Wix, Apify, AppSource) work the same way: the marketplace is the foreign customer paying the founder. They avoid MoR fees entirely at micro scale (Section 1).

### Gaps
- Primary fee pages could not be fetched (egress blocked). Polar's and Stripe Managed Payments' details come partly from **competitor blogs** (Dodo, Fungies). **Whether Stripe Managed Payments is open to India-based accounts** was not found.
- **India payout specifics** (supported rails, FX markup, FIRA issuance) for Polar (Stripe Connect Express cross-border payouts to India), Creem, and Lemon Squeezy (bank vs PayPal) were not confirmed from primary docs.
- **The legal entity and jurisdiction of each MoR's contracting party** (Dodo, Creem), which drives the GST export test, was not found.
- **The GST registration threshold** for a small exporter of services, and whether registration or an LUT is mandatory below it, was not retrieved. Get CA confirmation.
- **The RBI cross-border payment aggregator (PA-CB) framework** and how it applies to MoRs or platforms paying Indian sellers was not retrieved. I also have no detail on low-value EDF exemptions under the 2026 FEMA regulations.
- I could not open the primary RBI notification (rbi.org.in blocked). The 15→9-month amendment comes from search snippets of Taxmann, RBI, and TaxGuru pages. Some reports describe it as "restoring" 9 months, and the exact amendment date was not confirmed.

---

## 6. Pricing patterns for micro-SaaS that convert (free tier vs trial, annual, usage-based)

### Takeaway
Benchmark data shows a clear trade-off. **Card-required (opt-out) trials** get the fewest signups but convert ~49–51% to paid. **No-card (opt-in) trials** convert ~17–18%. **Freemium** converts only ~2.6–2.8% of free users. Per 100 visitors, card-required trials produce the most paying customers. Browser-extension freemium converts lower still, at ~0.5–2%. Marketplaces such as Wix support trial, recurring, and usage-based plans natively, and Apify's move away from rentals to pay-per-event/pay-per-result signals a platform-level shift to usage pricing.

### Cited Findings
- Benchmarks (First Page Sage's multi-year study of 86 SaaS companies plus Kyle Poyar's analysis of 1,000+ products, via secondary write-ups):

  | Model | Visitor → signup (organic / paid) | Signup → paid (organic / paid) |
  |---|---|---|
  | Opt-in trial (no card) | ~8.5% / 7.1% | ~18.2% / 17.4% |
  | Opt-out trial (card required) | ~2.5% / 2.2% | ~48.8% / 51% |
  | Freemium | ~13.3% / 15.9% | ~2.6% / 2.8% |

  Sources: [Userpilot: Free trial conversion rate](https://userpilot.com/blog/free-trial-conversion-rate/); [Sybill: Freemium vs free trial](https://www.sybill.ai/blogs/freemium-vs-free-trial); [Monetizely](https://www.getmonetizely.com/articles/freemium-vs-free-trial-choosing-the-right-customer-acquisition-model-for-saas-success); [Dodo Payments: Trial vs freemium 2026](https://dodopayments.com/blogs/saas-free-trial-vs-freemium)
- Illustrative per-cohort outputs from the same compilations:
  - standard trial: 45 signups → 3.6 paying;
  - ungated freemium: 70 signups → 5.6 paying;
  - card-required trial: 35 signups → 10.5 paying.

  The input base is unspecified, and these numbers are not fully consistent with the conversion rates above — [Dodo Payments](https://dodopayments.com/blogs/saas-free-trial-vs-freemium); [Saasfactor](https://saasfactor.co/blogs/freemium-vs-trial-models-in-saas-what-really-boosts-conversions)
- Chrome extensions: freemium free-to-paid is ~0.8% across ExtensionPay extensions, and 0.5–2% is "realistic" — [Konabayev](https://konabayev.com/blog/extension-monetization-statistics-2026/)
- Stripe Managed Payments supports subscription free trials without collecting a payment method upfront, i.e. opt-in trials — [Fungies](https://fungies.io/lemon-squeezy-stripe-acquisition-saas-founders-2026/)
- Wix lets app developers offer free trials, recurring, or usage-based plans — [Smallbiztrends](https://smallbiztrends.com/wix-unveils-new-features-at-devstudio-conference-to-empower-app-developers/); [Wix dev docs](https://dev.wix.com/docs/build-apps/launch-your-app/pricing-and-billing/about-monetizing-your-app)
- Apify is retiring rental (flat monthly) pricing in favor of pay-per-event and pay-per-result (no new rentals from Apr 1, 2026; fully retired Oct 1, 2026) — [use-apify.com](https://use-apify.com/docs/apify-for-developers/monetize-actors)
- Product Hunt counter-evidence on the launch-to-paid gap: 400 signups led to 1 paying customer — [Indie Hackers](https://www.indiehackers.com/post/400-signups-from-product-hunt-1-paying-customer-what-4-days-taught-me-about-launch-vs-traction-7c0aacf745)

### Inferences
- For a low-touch micro-SaaS aiming at $1k–$5k MRR, a **card-required 7–14-day trial**, or a small permanently free tier with a hard usage cap, plus monthly and annual USD plans, is the evidence-backed default for maximizing payers per visitor. Freemium makes sense mainly where free users create distribution, such as extensions, embeds, or watermark/branding loops.
- **Usage-based pricing fits automated products** (API calls, runs, results) and is the native model on Apify. It also works through MoR checkouts, but metered billing support varies by MoR and was not verified.
- Each MoR's fixed fee ($0.40–$0.50) is a large share of very low prices. At $5/month, Paddle's 5% + $0.50 is 15%, which argues for **price points of $9–$29+/month or annual billing** to dilute fixed per-transaction fees (my arithmetic from the cited rate cards).

### Gaps
- No 2025–2026 primary data was retrieved on **annual-plan uptake rates, annual discount norms, or the churn difference between annual and monthly plans** for micro-SaaS (e.g., ChartMogul or Paddle/ProfitWell benchmarks); the search budget was exhausted.
- No primary data on usage-based pricing adoption among small SaaS, or on the conversion impact of showing USD-only vs localized pricing (purchasing-power parity) to non-US buyers.
- The trial and freemium benchmarks were seen via secondary compilations, not the original First Page Sage or Kyle Poyar reports.
