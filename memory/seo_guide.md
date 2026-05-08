# Tile Station SEO — A Beginner's Guide
## Everything Your Website Does To Get Free Google Traffic

**Written for: someone brand new to SEO**
**Date: May 2026**
**About: Every SEO feature that's running on tilestation.co.uk right now**

---

## How To Use This Guide

You don't need to read it all in one go. Each chapter explains ONE feature in plain English, why it matters, and where to find it in your admin panel. If you only have 10 minutes, read **Chapter 1** (what SEO actually is) and **Chapter 4** (the killer feature: Stealth Keywords). The rest you can come back to whenever you want.

---

# Chapter 1 — What Is SEO, Really?

Imagine your shop is on a street with 100 other tile shops. People walk past, and you want them to come into YOUR shop instead of next door's.

Now replace "the street" with **Google**, and "people walking past" with **people searching for tiles**. SEO (Search Engine Optimisation) is the work you do to make Google show YOUR shop higher up in the search results, so MORE customers click YOUR link instead of the competition's.

Every time someone Googles "marble tiles uk" or "bathroom tiles brighton" and lands on tilestation.co.uk **without paying for a Google ad**, that's a win. That's free customers. The point of SEO is to multiply those free customers.

### The 3 things Google looks at to rank you

| What Google looks at | What it means for you |
|---|---|
| **Relevance** | Does your page actually match what they searched for? |
| **Authority** | Do other websites link to yours? Have you been around long? |
| **User experience** | Does your page load fast? Does it work on phones? Do customers stay on it? |

Almost everything we've built tackles **Relevance** — making sure when someone searches for ANY tile-related thing, your page comes up high.

---

# Chapter 2 — Why "Hidden" SEO Keywords Are A Big Deal

Here's a problem you didn't know you had:

You buy tiles from suppliers. The supplier calls them things like *"Opal"*, *"LP-6611"*, or *"Onyx White"*. You re-name them on your website to *"Artisan Marble"* or *"Alabaster"* — nicer names, premium feel, your brand.

But here's the catch: **trade buyers and architects often Google the SUPPLIER name** because that's what they saw in a brochure or catalogue. When they search *"Opal porcelain tile"*, Google has no idea your *"Artisan Marble"* page is the same thing — so Google sends them to your competitor instead. **You lose the sale before they even see your website.**

### The fix: tell Google the secret name, but hide it from customers

Imagine you wrote in tiny invisible ink at the bottom of your shop window: *"Also known as Opal"*. Customers walking by don't see it (the window still says "Artisan Marble" big and proud), but a robot reading the window would see both names. Google is the robot.

We do this in three places that are **invisible to customers but visible to Google**:

1. **Meta keywords tag** — code in the page header
2. **Structured data (JSON-LD)** — invisible markup Google reads to understand your page
3. **Open Graph tags** — what Pinterest, Slack, etc. read when someone shares your link

Customers visiting your page see ONLY "Artisan Marble". The supplier name never appears. But Google sees BOTH names and starts ranking your page for both searches.

### Result

> Customer Googles *"Opal porcelain tile UK"* → Your *Artisan Marble* page ranks → They click → They see your premium re-branded product → They buy at YOUR price.

You stole the supplier's organic search traffic. The supplier doesn't know. Competitors can't tell where your products come from. Your customers see the premium name and pay your price, not the supplier's.

This is what we call **Stealth-Keyword SEO**.

### Where to use it

`/admin/seo` → **Stealth-Keyword SEO Targeting** card (purple/fuchsia header)

---

# Chapter 3 — The "Auto-Fill" Button: Your 1-Click Stealth Setup

Setting stealth keywords on every product manually would take hours — you've got 775 of them. We built a button that does it all in one click.

### What it does

It walks through every product in your catalogue and adds two stealth keywords automatically:

1. The **supplier-original name** (e.g. "Onyx White")
2. The **supplier code** (e.g. "LP-6611")

Both already exist in your product data — we're just telling Google to ALSO show your page when someone searches those names.

### How to use it (literally one click)

1. Go to `/admin/seo`
2. Find the "Stealth-Keyword SEO Targeting" card
3. Click the pink button labelled **"Auto-fill all 775"**
4. A preview pops up: *"Will add 1170 alt-names across 761 products. Continue?"*
5. Click yes → done.

Now Google can find your pages for ALL those supplier names, not just your branded ones.

### Important

- It's **idempotent**. Big word — means safe to click 100 times. Already-done products are skipped. Nothing gets duplicated.
- It writes to a hidden field called `hidden_seo_keywords`. Customers never see it.
- Google takes 2-4 weeks to crawl and re-index. Patience.

### Why this is a 5-figure-per-year feature

If you imagine each supplier name brings in even 1 extra click per month, and 775 products × 1 click × £200 average sale × 1% conversion = ~£18,000/year of "free" traffic that wouldn't exist without this button.

---

# Chapter 4 — City Pages: Catching The "Tiles Near Me" Searches

About **40% of tile searches** include a town or postcode. People search "**tile shop gravesend**", "**tiles tunbridge wells**", "**bathroom tiles brighton near me**". If you don't have a page that mentions Gravesend, Google has no reason to send searchers to you.

So we built **168 auto-generated city landing pages**.

### What they look like

For 34 UK towns × 8 different "intents" (tile-shop, porcelain-tiles, bathroom-tiles, kitchen-tiles, marble-tiles, tile-suppliers, tile-delivery, tiles-online), we have a page like:
- `/tile-shop-gravesend`
- `/bathroom-tiles-brighton`
- `/porcelain-tiles-tunbridge-wells`

Each one:
- Mentions the town name multiple times
- Has location-specific content
- Has a **JSON-LD LocalBusiness** structured data block (tells Google "this is a real business serving this area")
- Links back to your collections so Google sees how the pages connect

Google **loves** local-intent pages. People Googling local terms convert to sales 3-4× higher than generic searches because they're ready to buy nearby.

### Where to manage them

`/admin/seo/city-pages` — you can review, approve, edit headings, etc.

### The "Local Seeder" automation

When someone Googles something like "**tiles gravesend**" and lands on a less-relevant page (or doesn't land on you at all), we detect it and automatically add "tiles gravesend" as a stealth keyword on the matching city page. It's all hands-off. We'll explain this more in Chapter 9.

---

# Chapter 5 — Structured Data (JSON-LD): What Google Reads About Each Page

When Google's robot reads your website, it tries to figure out things like *"what is this page about?"*, *"is this a product?"*, *"what's the price?"*, *"is it in stock?"*. The more clearly you answer those questions, the better Google ranks you.

We answer them with something called **JSON-LD** — a standardised format Google understands. Think of it as a label you stick on every page that tells Google EXACTLY what the page is.

### What we generate for each page

| Page type | JSON-LD labels we attach |
|---|---|
| Product page | Product name, price, currency, in-stock status, brand, image, SKU, supplier alt-names |
| Collection page | Collection name, list of products, breadcrumbs |
| City page | LocalBusiness (business hours, area served, geo coordinates) + Article (the page content) |
| Blog article | Article (author, publish date, headline, image) |
| Homepage | Organization (your business details, social links, logo) |

### Why it matters

Pages with proper JSON-LD show up with **rich snippets** in Google — those nice cards with star ratings, prices, "in stock" badges. Studies show rich snippets get **30% more clicks** than plain blue links. And Google can't generate them unless you give it the JSON-LD.

We build all this automatically. You don't have to write any code.

### Where to see it

It's invisible to customers but you can verify it works by:
1. Going to your live site (e.g. `https://tilestation.co.uk/tiles/alabaster-polished-60x60cm`)
2. Right-click → "View page source"
3. Search for `application/ld+json` — you'll see the structured data block

Or simpler: paste your URL into Google's [Rich Results Test](https://search.google.com/test/rich-results) — it'll show what Google sees.

---

# Chapter 6 — The Marketing Studio: AI That Makes SEO Content For You

Writing fresh content keeps Google interested. New blog posts, new banners, new product images — they all signal "this site is alive and updated".

We built a **Marketing Studio** that creates this content for you with AI.

### What's inside

**1. AI Banner Generator** — `/admin/marketing-studio`
- Type a prompt like "modern bathroom with marble tiles, soft lighting"
- AI creates a hero banner image
- Built-in "safe zones" so your text never gets cropped on mobile

**2. Sora 2 Video Generator** — `/admin/video-studio`
- Same idea, but video clips for social media
- 5-10 seconds, perfect for Instagram/TikTok

**3. Editorial Autopilot** — runs automatically every Monday at 7am
- Pulls competitor blog posts (via Ahrefs)
- Identifies trending topics in your niche
- Uses Claude AI to write a fresh blog article
- Auto-publishes to `/blog/[slug]`
- Each post is optimised with the right title, meta description, JSON-LD, internal links — all done

The blog at `/blog` grows by itself. You wake up Tuesday to a new post. Over a year that's 50+ articles, each ranking for new keywords.

### Why fresh content matters for SEO

Google has signals for "freshness". A site that publishes a new blog post weekly is treated as more authoritative than one that hasn't been updated in 6 months. Your competitors' blogs sit dormant. Yours doesn't.

---

# Chapter 7 — The Health Monitor: Catching Problems Before Google Does

Google penalises slow, broken websites. We have a **Health Monitor** that pings every page every 5 minutes and tells you the moment something breaks.

### What it watches

- Server response time (is the site loading fast?)
- HTTP errors (are pages returning 404 or 500 errors?)
- Sitemap availability (can Google find your pages?)
- Critical pages (homepage, key collections, top products)
- Stripe webhook (are payments working?)
- Cron job status (are the scheduled jobs running?)

### What you see

`/admin/seo` → **System Health** card (top of the page)

Green = everything fine. Amber = something needs attention. Red = active problem (you'd also get an email).

### Why this matters for SEO

Google's bots crawl your site daily. If they hit errors twice in a row, they slow down crawling. If they hit errors for a week, they de-rank you. The Health Monitor catches these issues before Google notices.

---

# Chapter 8 — The "Performance" Card: Are Stealth Keywords Working?

Adding stealth keywords is great — but how do you KNOW they're working? You need data.

We pull live **Google Search Console** data and break down where every click came from.

### The 3 KPI cards

When you open `/admin/seo` → "Stealth-Keyword Performance" → click Open:

| Bucket | Meaning |
|---|---|
| **Stealth wins** | Clicks from supplier names you added (your secret weapon working) |
| **Brand wins** | Clicks from your re-branded names (your branding working) |
| **Other** | Generic searches like "porcelain tile uk" |

Watching these numbers over weeks tells you the stealth-keyword strategy is paying off.

### "Missed Wins" — the gold

Below the KPIs there's a table of **queries Google is showing your site for, but where you don't yet have a stealth keyword**. These are the supplier names (or local terms, or material names) you SHOULD add — Google is already noticing your site for them, you just need to tell Google "yes, that page is a perfect match".

Each row has a `+ Add` button. Click it → pick a collection → done. You just promoted a missed-win to a stealth keyword.

### "Underperformers"

Stealth keywords you set but with no GSC traffic. Could mean:
- Google hasn't crawled the change yet (give it 2-4 weeks)
- Nobody actually searches that supplier name (drop it)
- The page doesn't rank well for it (boost the page with internal links)

---

# Chapter 9 — The Auto-Promote: SEO On Autopilot

Manually clicking "+ Add" on missed-wins every week is fine for 5 a week. What about 50? 500?

Enter **Auto-Promote**.

### What it does

Every Monday at 8 AM, before sending you the weekly digest email, the system:

1. Looks at this week's missed-wins (queries Google showed you for but you don't target yet)
2. Picks the top one (highest impressions)
3. Checks if it cleanly matches an existing collection name
4. Adds it as a stealth keyword on that collection — automatically

You wake up Monday morning, check the email, see *"This week we auto-promoted 'spanish tiles' → Spanish collection"*. If you disagree, click [Undo] in the email, done. If you agree, do nothing — it's already live.

### Batch Mode — 5× the gains

By default, Auto-Promote does ONE per week. There's a "Batch Mode" toggle that lets it do up to 5 per week — but with a stricter bar (must have 2× the impressions threshold). Same safety, 5× the volume.

### Local Seeder — bonus for city pages

There's a sister feature called **Local Keyword Seeding**. When a missed-win contains a UK town name (like "tiles gravesend"), it goes to the matching city-landing-page instead of a collection. Catches the 40% of tile searches with local intent.

### The safety rails

- All three (Auto-Promote, Batch, Local Seed) are OFF by default. You opt in.
- Every promotion is reversible — there's an [Undo] link in every digest email + on the dashboard
- Skips already-existing keywords (idempotent)
- Skips queries that don't match a collection cleanly (no junk added)
- One promotion per collection per week (no spamming)

### Where to find it

`/admin/seo` → Stealth-Keyword Performance → Open → Weekly Digest section → toggles for Auto-Promote, Batch Mode, Local Seeding

---

# Chapter 10 — The Weekly Digest Email: SEO Without Logging In

The dashboard is great, but you don't always have time to log in. The **Weekly Digest** comes to you instead.

Every Monday at 8 AM you get an email with:

- 📈 **Stealth clicks this week vs last** — green if up, red if down
- 🏆 **Top 5 winning supplier names** — which kws drove the most clicks
- 🎯 **New missed wins** — queries to consider adding next
- ⚠️ **Auto-promotions made this week** with [Undo] links
- 📊 **Underperformer count**

In 30 seconds you know whether your SEO is winning.

### Where to manage it

`/admin/seo` → Stealth Performance → Open → "Weekly digest email" section. You can:
- Pause it
- Add multiple recipients (your team, your accountant, etc.)
- Click "Send now" to test it instantly
- See when the last one was sent

---

# Chapter 11 — The Attribution Timeline: Which Keywords Actually Work?

OK so you've added 100+ stealth keywords. **Which specific ones are paying off?** That's what the Attribution Timeline answers.

For every tracked stealth keyword (auto-promoted or manually added), you see:
- The day you added it
- How many days it's been live
- Total clicks + impressions over the last 28 days
- A **mini-chart (sparkline)** showing daily click trend
- An **ROI score** (winner / ok / slow / quiet)

### How to read the ROI badge

| Badge | Meaning |
|---|---|
| 🟢 **Winner** | This keyword brings 1.5× more clicks than the median. Double down — add more variants. |
| 🔵 **OK** | Pulling its weight. Leave it. |
| 🟡 **Slow** | Below average. Wait another month, then re-evaluate. |
| ⚫ **Quiet** | Zero or near-zero clicks. Either Google hasn't crawled (wait) or no demand (drop it). |

### The killer use-case

In 6-8 weeks of data, you can see:
- *"Spanish tiles is doing 47 clicks/week, ROI 3.2× — let me add 5 more Spanish-themed keywords"*
- *"LP-6611 is quiet — drop it from the auto-fill suggestions"*

You're now optimising your SEO with **hard data**, not gut feel.

### Where

`/admin/seo` → "Keyword → Click Attribution" card (violet) → Open

---

# Chapter 12 — Margin Intelligence: Not Strictly SEO, But Critical

This isn't on the SEO page — it's on `/admin/products-hub` — but it ties into SEO data.

Every product in your catalogue has:
- A **cost price** (what you pay your supplier)
- A **retail price** (what customers pay)
- A **margin %** (the difference)
- **Organic traffic** (GSC impressions for its stealth keywords)

The Margin Intelligence widget multiplies these together with the formula:

> **Score = margin % × log(1 + impressions this week)**

Why this formula: a product with 80% margin but 0 traffic is useless (no demand). A product with 5% margin and 5,000 impressions is also useless (loss leader). The sweet spot is **40-60% margin AND 100-1000 impressions** — those products print money.

### What it surfaces

1. **Top 20 rev-generators** — fat margin + real demand. Push these on trade calls.
2. **Price-test candidates** — high impressions but thin margin. Try a 10% price lift.
3. **Supplier league table** — which suppliers carry the most margin-adjusted traffic. Your trade-call priority list.

### Use case

Before a sales call you 30-second-glance the dashboard:
- *"Push the Marble Effect collection (LEPORCE supplier) — they're driving 80% of organic traffic at 64% margin"*
- *"Don't bother with Verona this quarter — only 2 products and zero demand"*

This is sales intelligence + SEO + margin in one panel.

---

# Chapter 13 — Sitemap & Search Console Submission: Telling Google You Exist

Every website needs a **sitemap** — a file that lists every page on your site. Google reads it to know what to crawl.

We auto-generate yours at `https://tilestation.co.uk/sitemap.xml`. It includes:
- Every product
- Every collection
- Every city page
- Every blog article
- The homepage + key landing pages

Whenever a new product or page is added, the sitemap auto-updates AND we **automatically tell Google Search Console** about the change. You don't have to do anything.

### Where you connect Google Search Console

`/admin/seo` → "Connect Google Search Console" card (green button) → walks you through OAuth (one-time setup, 30 seconds)

After this, ALL the data feeding the Performance / Attribution / Auto-Promote features comes from your real GSC account.

---

# Chapter 14 — The Pinterest Auto-Pin: Free Social Traffic (PENDING)

This one's built but waiting on credentials from you.

When the Editorial Autopilot publishes a new blog post (Chapter 6), the system can automatically share it to a Pinterest board you choose. Pinterest is the **#2 traffic source for interior design** queries — particularly bathroom and kitchen tile inspiration.

The integration is fully built; we're just waiting on:
- `PINTEREST_APP_ID`
- `PINTEREST_APP_SECRET`

…both available free at https://developers.pinterest.com/. Once you provide them, every new blog post auto-pins itself with a beautiful card. Free social traffic, zero effort.

---

# Chapter 15 — The 5-Minute Daily Routine

You don't need to spend hours on SEO. Here's the daily/weekly routine:

### Daily (1-2 minutes)

- Open the email digest if it arrived (Mondays only)
- Click [Undo] on any auto-promotions you disagree with

### Weekly (10 minutes)

- `/admin/seo` → Performance card → Open
- Skim the "Missed Wins" — click + Add on 1-2 obvious wins if Auto-Promote didn't catch them
- Skim the "Underperformers" — anything stale? remove it
- Check Health Monitor at the top — anything red?

### Monthly (30 minutes)

- Open the Attribution Timeline — see which 5 keywords are winners
- For each winner, ask: *"can I add 2-3 variants?"* (e.g. if "spanish tiles" wins, try "spanish wall tiles", "spanish floor tiles", "spanish kitchen tiles")
- Open the Margin Intelligence widget — note the top 5 supplier-ranked products. Mention them on next sales call.

That's it. **5-10 hours/year of SEO work, with everything else automated**, and your traffic compounds month over month.

---

# Chapter 16 — Glossary

**Backlink** — Another website linking to yours. Each one is a "vote" Google counts.

**Bot / Crawler** — A program (Googlebot, Bingbot) that visits your pages to read them.

**Canonical URL** — The "official" URL when the same content can be reached via multiple paths. Stops duplicate-content penalties.

**CTR (Click-Through Rate)** — Of the people who SAW your link in Google, what % clicked it. CTR = clicks ÷ impressions.

**GSC (Google Search Console)** — Free Google tool showing what searches your site appears for, how many clicks, what position. The source of truth for SEO data.

**Impressions** — How many times your link appeared in Google search results, whether anyone clicked or not.

**JSON-LD** — A standardised invisible markup on your page that tells Google what the page is about (product, business, article, etc.).

**Long-tail keywords** — Specific multi-word phrases like "spanish marble tiles brighton". Less search volume but MUCH higher conversion than broad terms.

**Meta description** — The short paragraph under your title in Google results. We auto-write these.

**Organic traffic** — Free traffic from search engines (vs paid ads).

**Position / Rank** — Your average position in Google for a search. Position 1 is top of page 1. Position 11 is top of page 2 (terrible — almost no clicks).

**Sitemap** — XML file listing every page on your site. Helps Google find them all.

**SSR (Server-Side Rendering)** — Sending a fully-built page from your server vs a half-built one that needs JavaScript to finish. Google handles SSR'd pages MUCH better. Your site does SSR for all SEO-important routes.

**Stealth Keyword** — A search term added to your page invisibly (only crawlers see it) so the page ranks for that term without the customer-facing UI mentioning it. Your secret weapon for capturing supplier-name traffic.

---

# What To Do Right Now

If you read NOTHING else, do these 3 things:

1. **Click the "Auto-fill all 775" button** (Chapter 3). 5 seconds. Adds 1170 stealth alt-names. Compounds over 4-6 weeks of Google crawls.
2. **Enable Auto-Promote + Batch Mode + Local Seeding** (Chapter 9). 30 seconds of toggles. Your SEO becomes self-writing.
3. **Connect Google Search Console** if you haven't (Chapter 13). 1 minute OAuth. Without this the Performance / Attribution / Auto-Promote features have no data to work with.

That's it. Your website now has a self-writing SEO engine that'll keep growing organic traffic month after month while you focus on the parts of the business only you can do.

— end —
