# Tile Station — Launch Morning Live-Order Test
**~5 minutes. Do this BEFORE flipping marketing live.**

---

## Pre-flight (60 seconds)
1. Open admin in one tab: https://feature-verification-7.preview.emergentagent.com/admin/login
2. Sign in (your normal admin credentials)
3. Quick health check:
   - [ ] Homepage loads — no "Heads up" maintenance ribbon visible
   - [ ] Top ribbon reads "Free delivery on orders over **£499**"
   - [ ] Sales Hub `/admin/sales-hub` loads, Daily Reconciliation tile visible

If anything looks broken — **STOP, ping me, do not flip marketing on**.

---

## The £20 Live-Money Test (3 minutes)
Place a real order paid with a real card (it's *your* shop, your money cycles back).

1. **In a fresh incognito window**: open the storefront homepage.
2. Pick a low-priced essential — e.g. a sample, a single small accessory, or set qty so the line total is ~£20. Aim under the £499 free-delivery threshold so we test that delivery fee actually applies (and we'll refund anyway).
3. **Add to Basket** → **Checkout**.
4. Step 1 — fill **your own** name + email (one you check on phone). Use a phone number that exists.
5. Step 2 — your real billing address.
6. Step 3 — payment:
   - [ ] **Card**: real Visa/Mastercard. Complete the Stripe redirect.
   - Total to land roughly £20 + £79.99 delivery = **~£100**. (Or pick a £499+ basket if you want to test the free-delivery path instead — your call.)
7. After the Stripe success redirect, expect the order-success page with **order number visible** (e.g. `TS-260428-XXXXXX`). **Screenshot it.**

---

## 4 Verification Points (60 seconds)
Now switch to the admin tab and the email tab in parallel:

| Check | Where to look | Pass criteria |
|---|---|---|
| 1. Order email lands | Inbox of the email you used at checkout | Subject contains the order number; total matches |
| 2. Warehouse sees it | `/admin/online-orders` | Top row is your order, status `Awaiting Dispatch` (or `Awaiting Collection` if you picked Collect), Method column matches |
| 3. Trade buyer flag (if your test account is trade) | Same row | "Trade Buyer" badge column populated |
| 4. Mark dispatched | Click the order → status dropdown → **Dispatched** → Save | Row updates, dispatched-at timestamp visible |

If all 4 ✅ — **launch is GO**.

---

## Cleanup (60 seconds)
1. Refund the order via Stripe dashboard:
   - Go to https://dashboard.stripe.com/payments
   - Find the payment by amount + last-4 of card
   - **Refund full amount**
2. In `/admin/online-orders`, find the order, click **Mark refunded** (if dropdown supports) or annotate in notes: *"Launch-day live test order — refunded via Stripe."* So your reconciliation tile tomorrow morning shows clean.

---

## If Something Fails Mid-Test
- **Stripe redirect fails / blank page**: ping me with the exact URL you landed on
- **Email never arrives**: check spam, then check `/admin/customer-emails` log if available
- **Order doesn't appear in admin within 30s**: refresh — Stripe webhook may be a moment behind
- **Wrong total / wrong delivery fee**: screenshot the cart page AND the order-success page and ping me

---

## Post-Launch (minutes after flipping marketing on)
- [ ] Send 1 staff member a "test the search" task — put 3 different searches through the site
- [ ] Watch live-visitor counter in admin for first 10 minutes
- [ ] Have the maintenance toggle tab open at `/admin/page-maintenance` — if anything goes sideways, you can flip the kill-switch in 2 clicks

🟢 **You've got this. Go launch.**
