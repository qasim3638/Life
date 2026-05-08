# Domain Cutover — tilestation.co.uk

**Started**: 2026-04-28 ~22:00 UK
**Registrar**: Namecheap
**Hosting**: Railway (production service)
**Goal**: `https://carefree-friendship-production-ee2b.up.railway.app` → `https://www.tilestation.co.uk`

## Status

- [x] Railway custom domain `www.tilestation.co.uk` added
- [x] Railway custom domain `tilestation.co.uk` added
- [x] Cloudflare DNS — CNAME `www` → `p3l2rn1f.up.railway.app` (DNS only, grey cloud)
- [x] Cloudflare DNS — CNAME `@` → `e3yvig76.up.railway.app` (DNS only, grey cloud)
- [x] Both Railway-verify TXT records added
- [x] Old Wix records deleted (`A` 185.230.63.x, `CNAME www → initial.wixdns.net`)
- [x] DNS propagated globally (verified via 1.1.1.1, 8.8.8.8)
- [x] Railway SSL certs issued (200 OK on both www + apex)
- [x] `https://www.tilestation.co.uk` loads with padlock 🟢
- [x] `https://tilestation.co.uk` loads with padlock 🟢
- [x] Email DNS untouched (mx1/mx2.privateemail.com, SPF, DMARC, resend._domainkey all intact)
- [x] Railway env vars updated (frontend `REACT_APP_BACKEND_URL` set to backend Railway URL; `CORS_ORIGINS` includes new domains)
- [x] Frontend rebuilt + redeployed with correct API target
- [x] CORS preflight verified passing from `https://www.tilestation.co.uk`
- [x] End-to-end smoke test: both URLs return 200 OK on the live storefront
- [ ] Stripe webhook URL updated in Stripe dashboard
- [ ] Resend domain `tilestation.co.uk` verified (DKIM key already in DNS)
- [ ] Sentry DSN dashboards confirmed receiving events from new domain
- [ ] Live test order placed end-to-end on www.tilestation.co.uk

## ⚠️ EMAIL DNS SNAPSHOT (taken 2026-04-28 22:50 UK — restore these after switching DNS)

| Type      | Host                       | Value                                                                                              | Priority |
|-----------|----------------------------|----------------------------------------------------------------------------------------------------|----------|
| MX        | `@`                        | `mx1.privateemail.com.`                                                                            | 10       |
| MX        | `@`                        | `mx2.privateemail.com.`                                                                            | 20       |
| TXT (SPF) | `@`                        | `v=spf1 +a +mx +ip4:185.61.154.212 +ip4:185.61.154.213 include:spf.web-hosting.com ~all`           | —        |
| TXT       | `_dmarc`                   | `v=DMARC1; p=none; rua=mailto:online@tilestation.co.uk`                                            | —        |

If email breaks after the cutover, restore these three and email works again. Namecheap Private Email handles DKIM at their end, no DKIM records were published publicly.

## DNS targets from Railway

- TARGET_A (for `www`): `p3l2rn1f.up.railway.app`
- TARGET_B (for apex `@`): `e3yvig76.up.railway.app`

## All 4 DNS records to add at Namecheap

| # | Type  | Host                  | Value                                                                                |
|---|-------|-----------------------|--------------------------------------------------------------------------------------|
| 1 | CNAME | `www`                 | `p3l2rn1f.up.railway.app`                                                            |
| 2 | TXT   | `_railway-verify.www` | `railway-verify=1ea013fd501cacd308716308c7295e3e28458445598e35913ef366eef0f82e2e`    |
| 3 | CNAME | `@`                   | `e3yvig76.up.railway.app`                                                            |
| 4 | TXT   | `_railway-verify`     | `railway-verify=ade16328b612e23caaaa61c776713c4ac6342952a91cbc30d7e2c1f4cf62ea4c`    |

## Post-cutover env vars to update on Railway

```
REACT_APP_BACKEND_URL=https://www.tilestation.co.uk
PUBLIC_PREVIEW_URL=https://www.tilestation.co.uk
SHOP_WEBSITE_URL=https://www.tilestation.co.uk
ALLOWED_ORIGINS=https://www.tilestation.co.uk,https://tilestation.co.uk
```

## Stripe dashboard updates

- Webhook endpoint URL → `https://www.tilestation.co.uk/api/stripe/webhook`
- Confirm events still subscribed (payment_intent.succeeded, etc.)

## Resend (email)

- Domain `tilestation.co.uk` must be verified with SPF + DKIM + DMARC TXT records.
- If not already done, Resend dashboard → Domains → Add → tilestation.co.uk → it'll spit out 3 TXT records to add to Namecheap.
