/**
 * MetricInfoTooltip — small "ⓘ" badge that, on hover/focus, opens a
 * plain-English explainer card.
 *
 * Built on top of Radix-UI Tooltip (already in shadcn/ui at
 * components/ui/tooltip) for accessibility (keyboard focus, ARIA,
 * collision-aware positioning) without pulling in a new dep.
 *
 * Usage:
 *   <MetricInfoTooltip explainer={SEO_EXPLAINERS.ctr} />
 *
 * The explainer is a plain object so non-developers can edit copy
 * without touching JSX.
 */
import React from 'react';
import { Info } from 'lucide-react';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '../ui/tooltip';

export const MetricInfoTooltip = ({ explainer, side = 'top', align = 'start', testId }) => {
  if (!explainer) return null;
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            tabIndex={0}
            aria-label={`What is ${explainer.title}?`}
            className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full text-slate-400 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-400 align-middle ml-1"
            data-testid={testId || `info-${(explainer.title || '').toLowerCase().replace(/\s+/g, '-')}`}
            // The button must not submit any enclosing form.
            onClick={(e) => e.preventDefault()}
          >
            <Info className="w-3.5 h-3.5" strokeWidth={2.5} />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={12}
          className="max-w-[340px] bg-slate-900 text-white p-0 rounded-xl border border-slate-700 shadow-xl"
        >
          <div className="p-3.5 space-y-2 text-left">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-blue-300">
              {explainer.title}
            </div>
            <div className="text-sm text-slate-100 leading-relaxed">{explainer.what}</div>
            {explainer.why ? (
              <div className="text-xs text-slate-300 leading-relaxed">
                <span className="font-semibold text-amber-300">Why it matters:</span> {explainer.why}
              </div>
            ) : null}
            {explainer.good ? (
              <div className="text-xs text-slate-300 leading-relaxed">
                <span className="font-semibold text-emerald-300">A good number:</span> {explainer.good}
              </div>
            ) : null}
            {explainer.example ? (
              <div className="text-[11px] text-slate-400 italic leading-relaxed pt-1 border-t border-slate-700">
                {explainer.example}
              </div>
            ) : null}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// ────────────────────────────────────────────────────────────────────────
// Plain-English explainers — single source of truth, reusable across
// any admin metric chip / table column.
// ────────────────────────────────────────────────────────────────────────

export const SEO_EXPLAINERS = {
  clicks: {
    title: 'Clicks',
    what: 'The number of times someone actually clicked one of your pages on Google\'s search results — i.e. real visitors landing on your site from Google.',
    why: 'Clicks turn into shoppers. Every click is a chance for a sale. More clicks for the same effort = more revenue without more ad spend.',
    good: 'There\'s no universal number — but you want clicks to grow week-on-week. Even +10/week from a new city page is a great signal.',
    example: 'If 50 people searched "tile shop maidstone" and 5 clicked your result, that\'s 5 clicks.',
  },
  impressions: {
    title: 'Impressions',
    what: 'How many times your page appeared in someone\'s Google search results — even if they didn\'t click.',
    why: 'Impressions = visibility. They prove Google knows you exist and is showing you to searchers. Rising impressions mean your SEO is working even before clicks catch up.',
    good: 'Watch the trend, not the number. New pages start at 0 and climb as Google trusts them. A drop after a deploy is the warning sign you want to catch.',
    example: 'If your "tile shop london" page showed up on page 2 of Google 200 times this week, that\'s 200 impressions — even if nobody clicked.',
  },
  ctr: {
    title: 'CTR (Click-Through Rate)',
    what: 'The % of people who actually clicked after seeing your page in Google. Calculated as clicks ÷ impressions × 100.',
    why: 'CTR is the single best signal of how compelling your title and description are. Two pages can rank #5, but the one with a punchier title gets 3× the traffic.',
    good: 'Position #1: ~30%. #3: ~10%. #10: ~2.5%. If your CTR is well below the position-average, the page is being seen but the title isn\'t selling the click.',
    example: 'Page 1, position 4 with 1,000 impressions and 80 clicks = 8% CTR. Industry average for that slot is ~6%, so you\'re winning.',
  },
  avg_position: {
    title: 'Average position',
    what: 'Where your page typically ranks in Google search results, averaged across every query that surfaced it. Lower is better — position 1 is the top result.',
    why: 'Position is the #1 driver of clicks. Moving from position 11 (page 2) to position 9 (bottom of page 1) often doubles your clicks because most people never see page 2.',
    good: 'Top 3 = excellent (most clicks). 4-10 = good. 11-20 = "almost there" — usually the easiest page to push onto page 1 with small SEO improvements.',
    example: 'If your tile detail page ranks #5 for "matte black tiles" and #15 for "kitchen tiles", your average for that page might be ~10.',
  },
  queries_tracked: {
    title: 'Queries tracked',
    what: 'The number of distinct search terms (keywords) Google has shown your site for in the selected window.',
    why: 'A growing keyword count means Google is finding more reasons to show your site — typically because of new content like the AI-generated city pages or fresh product descriptions.',
    good: 'Steady growth week-on-week. A sudden drop usually means a content change that hurt relevance — e.g. removing important text from a page.',
  },
  // ── Used on individual rows (not totals) ────────────────────────────
  query_row: {
    title: 'Search query',
    what: 'The exact phrase someone typed into Google that brought them (or nearly brought them) to your page.',
    why: 'This is the language your customers actually use. Mining the query list reveals new product pages, FAQ topics, and ad-copy phrases that already work.',
    example: '"matte black bathroom floor tiles 60x60" → tells you customers think about size + colour + finish in that order. Match that order in titles.',
  },
  page_row: {
    title: 'Landing page',
    what: 'The specific URL on your site that Google ranked for one or more queries. The "page" you sent the visitor to.',
    why: 'Some pages punch way above their weight (e.g. a city landing page bringing 50% of city traffic). Doubling down on what already works compounds faster than starting new pages.',
  },
  position_row: {
    title: 'Position (this row)',
    what: 'The average rank Google gave THIS specific query or page in the window.',
    why: 'A position between 11-20 (i.e. page 2) is the cheapest win — small improvements can move it onto page 1, where 95% of clicks happen.',
  },
  // ── Sitemap section ─────────────────────────────────────────────────
  sitemap: {
    title: 'Sitemap',
    what: 'A machine-readable file (XML) that lists every page on your site you want Google to know about. Updated automatically here, served at /sitemap.xml.',
    why: 'Without a sitemap Google has to discover pages by following links, which can take weeks. With one, it can pick up new pages in hours.',
    example: 'When the AI generates a new "/tiles/tile-shop-leeds" page, the sitemap auto-updates and Google is nudged to recrawl on the next deploy.',
  },
  url_inspect_verdict: {
    title: 'Verdict',
    what: 'Google\'s overall assessment of one URL: PASS = indexed and ranking-eligible · NEUTRAL = known but not yet indexed · FAIL = blocked or broken · PARTIAL = indexed but with issues.',
    why: 'A FAIL or NEUTRAL is a direct cause of zero traffic from that page. Spotting it now (rather than via a missing-traffic mystery later) saves weeks.',
  },
  canonical: {
    title: 'Canonical URL',
    what: 'The "official" URL of a piece of content. If the same product is reachable via 3 URLs, the canonical tells Google which one to rank — preventing it from splitting credit between duplicates.',
    why: 'A mismatch between YOUR canonical and GOOGLE\'S canonical means Google has decided a different page is the master — usually a sign of duplicate content or a competing page on your domain.',
  },

  // ── Uptime / SLA ────────────────────────────────────────────────────
  sla_target: {
    title: '99.9% uptime target',
    what: '"Three nines" — the industry-standard reliability bar for live e-commerce. Means at most 8 hours 45 minutes of downtime allowed per YEAR (about 43 seconds per day on average).',
    why: 'Every minute the storefront is down = lost orders + frustrated returning customers + Google de-prioritising the site if it happens during a crawl. Tracking uptime catches a flapping deploy before customers notice.',
    good: 'Green ≥99.9% (target met). Amber 99-99.9% (degraded — one bad day per month). Red <99% (escalate immediately).',
    example: 'A 30-minute Stripe outage in a 30-day window = 99.93% — still inside the 99.9% target.',
  },
  uptime_current: {
    title: 'Current uptime today',
    what: 'The percentage of probes that succeeded since midnight UTC. Updates every 5 minutes as new probes complete.',
    why: 'A drop here BEFORE the rolling-30-day average dips is your earliest warning that something just broke.',
  },
  uptime_avg: {
    title: '30-day average uptime',
    what: 'The percentage of all probes that succeeded across the last 30 days. The rolling SLA snapshot.',
    why: 'Smooths out one-off blips so you can see whether reliability is trending up or down across the month.',
  },
  uptime_incidents: {
    title: 'Incident count',
    what: 'Number of days in the last 30 where this service\'s uptime fell below 99% — i.e. days a customer might have noticed something was off.',
    why: 'Counting incidents as "days affected" rather than "minutes of failure" matches how customers experience outages — they remember bad days, not bad minutes.',
  },

  // ── Conversion funnel stages ────────────────────────────────────────
  session: {
    title: 'Session',
    what: 'A single visit by one person — starting when they arrive, ending after 30 minutes of inactivity. The same person visiting twice in one day = 2 sessions.',
    why: 'Sessions (not pageviews) are the right denominator for conversion. 1 person who views 5 pages then buys = 1 converted session, not 5 converted pageviews.',
    example: 'A returning customer popping in at 9am to browse and again at 5pm to buy = 2 sessions, 1 paid.',
  },
  product_views: {
    title: 'Product views',
    what: 'Sessions where the visitor reached at least one /tiles/* or product-detail page. Browsers who got past the homepage and engaged with merchandise.',
    why: 'A big gap between sessions and product views means the homepage/landing isn\'t doing its job — visitors arrive, look, and leave without exploring.',
    good: 'For a tile site, expect 50-70% of sessions to hit a product page. Lower than 40% suggests the homepage messaging is too vague.',
  },
  checkout_reached: {
    title: 'Checkout reached',
    what: 'Sessions where the visitor loaded /checkout — i.e. clicked the "buy" button and saw the payment form.',
    why: 'This is "intent to buy". A shopper who reached checkout but didn\'t pay is the highest-value cart-abandonment audience for follow-up emails.',
    good: '8-15% of product viewers typically reach checkout. Lower means product pages aren\'t selling. Higher with a low paid % means checkout itself is broken.',
  },
  paid_orders: {
    title: 'Paid orders',
    what: 'Successful payments captured in the window. Counts orders with payment_status=paid OR status in (completed, paid, shipped, confirmed).',
    why: 'The bottom of the funnel. Everything above it exists to feed this number.',
  },
  conversion_rate: {
    title: 'Conversion rate',
    what: 'Of all visitors who arrived, what percentage actually paid? Calculated as paid orders ÷ sessions × 100.',
    why: 'The single most-watched e-commerce metric. A 1% lift on a £100k/month site = £1k/month with zero extra ad spend.',
    good: 'UK home-improvement average is 1.5-2.5%. Tile/stone trade typically lower (longer consideration) — 0.8-1.5%. Subscription or impulse-buy verticals run 3%+.',
    example: '7 sessions, 0 paid = 0% (too few sessions to draw conclusions). 1,000 sessions, 18 paid = 1.8% (right at the UK average).',
  },
  traffic_source: {
    title: 'Traffic source',
    what: 'Where the visitor came from. We classify referrers into Organic search (Google/Bing), Social (Facebook/Instagram/etc.), Email, Direct (typed the URL or clicked a bookmark), or Other.',
    why: 'Different sources convert at very different rates. Organic search converts 2-4× better than social on most ecommerce sites. Knowing the mix tells you where to invest.',
    example: 'If 80% of paid orders come from organic but you spend 90% of marketing budget on Facebook ads, that\'s an obvious reallocation signal.',
  },
};

// ────────────────────────────────────────────────────────────────────────
// Sales / EPOS dashboard explainers
// ────────────────────────────────────────────────────────────────────────
export const SALES_EXPLAINERS = {
  total_sales: {
    title: 'Total Sales (Gross Revenue)',
    what: 'The full amount customers paid you in the selected window — VAT included, before any costs are deducted. The "top line" of the business.',
    why: 'It\'s the easiest number to track, but on its own it can be misleading. A high-sales month with thin margins can be less profitable than a smaller month with healthier margins. Always read it alongside Net Profit.',
    example: 'Selling £15,678 of tiles this month doesn\'t tell you if you made or lost money — it tells you the cash that came in.',
  },
  net_profit: {
    title: 'Net Profit',
    what: 'What\'s left after stripping out VAT (which goes to HMRC) and the cost of the goods you sold. The actual money the business keeps.',
    why: 'This is the only number that pays the wages, the rent, and ultimately you. Two shops with identical sales can have wildly different net profit depending on supplier deals and discounting.',
    good: 'For UK tile retail, a healthy net margin (net profit ÷ ex-VAT revenue) sits at 15-25%. Below 10% means you\'re working hard for very little.',
    example: '£15,678 sales − £2,613 VAT − £8,542 cost of goods = £4,523 net profit. That\'s the money you actually earned.',
  },
  orders: {
    title: 'Orders',
    what: 'The total number of paid orders placed on the website in the selected window. Each completed checkout = 1 order, regardless of how many items it contains.',
    why: 'A growing order count signals demand growth. A flat order count with rising sales means people are buying bigger jobs — also good. Falling orders is the earliest warning that traffic or pricing has shifted against you.',
    example: '47 orders this month vs 32 last month = 47% growth in transactions, which usually means more new customers + repeat buyers.',
  },
  aov: {
    title: 'Average Order Value (AOV)',
    what: 'The average amount spent per order. Calculated as Total Sales ÷ Orders.',
    why: 'AOV is the cheapest lever to grow revenue. Lifting AOV by £20 across 47 orders = £940 extra revenue with zero new customers. Achieved via bundles, "buy 5 boxes save 5%", trim/edge upsells, and free-delivery thresholds.',
    good: 'For UK tile retail, AOV typically sits between £150-£400. Trade orders push it higher; small DIY orders pull it down.',
    example: '£15,678 ÷ 47 orders = £334 AOV.',
  },
  customers: {
    title: 'Customers',
    what: 'The number of distinct customers who placed at least one order in the window — counted by email/account, so the same person buying twice still counts as 1.',
    why: 'Customers and Orders together reveal repeat behaviour. Customers ≪ Orders means a loyal base buying multiple times (great). Customers ≈ Orders means everyone is one-and-done (a retention problem).',
    example: '32 customers placing 47 orders = 1.47 orders per customer, i.e. ~30% bought more than once.',
  },
  sales_conversion_rate: {
    title: 'Conversion Rate',
    what: 'Of every 100 visitors to the website, how many actually placed a paid order. Calculated as Orders ÷ Sessions × 100.',
    why: 'The single biggest revenue lever after traffic. A 1% lift on a £15k/month site = £150/month with zero ad spend. Driven by trust signals, clear pricing, fast pages, and frictionless checkout.',
    good: 'UK home-improvement average: 1.5-2.5%. Tile/stone (longer consideration cycle) usually 0.8-1.5%. Above 3% is exceptional.',
    example: '2.8% means roughly 28 out of every 1,000 visitors became paying customers.',
  },
  pending_orders: {
    title: 'Pending Orders',
    what: 'Orders that have been paid but not yet shipped — i.e. they\'re waiting on you to pick, pack, or arrange delivery.',
    why: 'Pending orders are unfulfilled promises. Each day one sits unshipped raises the risk of a refund request, a 1-star review, or a chargeback. This number should trend toward zero by end of day.',
    good: '0-3 = healthy fulfilment cadence. 5+ for more than 24h = a process bottleneck worth investigating.',
  },
  revenue_per_customer: {
    title: 'Revenue per Customer (LTV proxy)',
    what: 'Average money received per unique customer in the window. Calculated as Total Sales ÷ Customers.',
    why: 'A close cousin of AOV but counted per person, not per order — so it captures repeat spend. Rising figure means existing customers are coming back, the cheapest growth there is.',
    example: '£15,678 ÷ 32 customers = £490 per customer. If AOV is £334, then customers averaged ~1.5 orders each.',
  },
  // ── Profit Breakdown rows ───────────────────────────────────────────
  gross_revenue: {
    title: 'Gross Revenue (inc. VAT)',
    what: 'The full amount customers paid you, including the 20% VAT element you collect on Standard-Rated tiles. This is the headline "sales" figure.',
    why: 'Useful for cash-flow planning (this is what hits the bank account) but misleading for profitability — VAT here belongs to HMRC, not you.',
  },
  vat_collected: {
    title: 'VAT Collected (20%)',
    what: 'The VAT element baked into your gross revenue. UK Standard rate is 20% — so £100 of sales contains £16.67 of VAT.',
    why: 'VAT is HMRC\'s money you\'re holding temporarily. Subtract it before you ever look at "what we earned" — otherwise you\'ll mistake the taxman\'s share for your own.',
    example: '£15,678 gross ÷ 1.2 = £13,065 ex-VAT. The £2,613 difference is VAT to remit.',
  },
  cost_of_goods: {
    title: 'Cost of Goods (COGS)',
    what: 'What it cost you to acquire the tiles you sold — the supplier price you paid, before any margin or markup.',
    why: 'The single biggest controllable cost in retail. Negotiating 5% off COGS often delivers more profit than chasing a 5% sales lift, because every penny saved drops straight to net profit.',
    example: 'If you bought a tile for £20/m² and sold it for £35/m², the £20 is COGS — even though the customer paid £35.',
  },
  net_profit_row: {
    title: 'Net Profit',
    what: 'Revenue minus VAT minus cost of goods. The money the business actually keeps from this period — before overheads (rent, wages, ads).',
    why: 'This is the number to compound. A small increase here, sustained over months, is the difference between a struggling shop and a thriving one.',
  },
  profit_margin: {
    title: 'Profit Margin',
    what: 'Net Profit as a percentage of ex-VAT revenue. Tells you, for every £1 of real (ex-VAT) sales, how much you keep as profit.',
    why: 'Margin matters more than absolute profit. A 30% margin is durable; you can absorb a bad month or a discount campaign. A 5% margin can be wiped out by a single price war.',
    good: 'UK tile retail: 15-25% net margin is healthy. Trade-heavy mix tends lower (12-18%) due to bigger discounts. Boutique/design-led can run 30%+.',
  },
  // ── Tables ───────────────────────────────────────────────────────────
  top_products: {
    title: 'Top Selling Products',
    what: 'Your best performers by revenue in the window — what\'s actually paying the bills right now.',
    why: 'Stocking, marketing, and homepage decisions should follow this list. Most shops over-feature aspirational SKUs and under-stock the bread-and-butter winners. This table is the antidote.',
  },
  sales_by_category: {
    title: 'Sales by Category',
    what: 'Revenue broken down across product categories (Floor, Wall, Accessories, etc.) showing % share of total sales.',
    why: 'Reveals where the money really comes from. If 13% of sales come from accessories with 40%+ margins, that\'s a category to push harder, not a side-line.',
  },
};

export default MetricInfoTooltip;
