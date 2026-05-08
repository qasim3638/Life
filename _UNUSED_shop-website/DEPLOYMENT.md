# Tile Station E-commerce Shop

A Next.js e-commerce website for Tile Station - premium tiles and bathroom products.

## Features

- **SEO Optimized** - Server-side rendering, meta tags, sitemap, structured data
- **Guest Checkout** - No account required to purchase
- **Payment Options** - Stripe and PayPal integration
- **Wishlist** - Save favorite products (requires account)
- **Product Reviews** - Customer ratings and reviews
- **Tile Calculator** - Calculate tiles needed for your room
- **Free Samples** - Order up to 3 free samples (postage only)
- **Trade Account** - Apply for trade pricing
- **Order Tracking** - Track orders by number and email

## Deployment to Vercel

### 1. Push to GitHub

```bash
# In the shop-website directory
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/tilestation-shop.git
git push -u origin main
```

### 2. Deploy on Vercel

1. Go to [vercel.com](https://vercel.com)
2. Sign in with GitHub
3. Click "New Project"
4. Import your repository
5. Configure environment variables:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://tilestation.co.uk` (your backend URL) |
| `NEXT_PUBLIC_SITE_URL` | `https://shop.tilestation.co.uk` (your shop URL) |
| `NEXT_PUBLIC_SITE_NAME` | `Tile Station` |
| `NEXT_PUBLIC_SITE_DESCRIPTION` | `Premium tiles and bathroom products...` |

6. Click "Deploy"

### 3. Configure Custom Domain

1. In Vercel project settings → Domains
2. Add `shop.tilestation.co.uk`
3. In your DNS provider, add:
   - **Type**: CNAME
   - **Name**: shop
   - **Value**: cname.vercel-dns.com

## Environment Variables

Create a `.env.local` file for local development:

```env
NEXT_PUBLIC_API_URL=https://tilestation.co.uk
NEXT_PUBLIC_SITE_URL=https://shop.tilestation.co.uk
NEXT_PUBLIC_SITE_NAME=Tile Station
NEXT_PUBLIC_SITE_DESCRIPTION=Premium tiles and bathroom products. Quality craftsmanship at competitive prices. Free UK delivery on orders over £500.
```

## Local Development

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Build

```bash
npm run build
npm run start
```

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **API Client**: Axios
- **TypeScript**: Full type safety
