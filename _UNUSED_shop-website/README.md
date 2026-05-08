# Tile Station E-Commerce Website

A standalone Next.js e-commerce website for Tile Station, optimized for SEO and designed to connect to the existing Tile Station backend API.

## Features

- **SEO Optimized**: Server-side rendering, meta tags, Open Graph, structured data (JSON-LD)
- **Dynamic Sitemap**: Auto-generated sitemap.xml including all products and categories
- **Robots.txt**: Properly configured for search engine crawling
- **Product Catalog**: Browse products with filters, search, and sorting
- **Shopping Cart**: Local storage cart for guest users
- **Responsive Design**: Mobile-first, works on all devices
- **Fast Performance**: Next.js App Router with optimized images

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **Language**: TypeScript
- **Icons**: Lucide React
- **API Client**: Axios

## Environment Variables

Create a `.env.local` file with:

```env
# Backend API URL (your Railway deployment)
NEXT_PUBLIC_API_URL=https://your-api.railway.app

# Site URL (for sitemap, canonical URLs)
NEXT_PUBLIC_SITE_URL=https://tilestation.co.uk

# Site metadata
NEXT_PUBLIC_SITE_NAME=Tile Station
NEXT_PUBLIC_SITE_DESCRIPTION=Premium tiles and bathroom products...
```

## Development

```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Deployment Options

### Option 1: Vercel (Recommended for Next.js)

1. Push this folder to a GitHub repository
2. Connect to Vercel: https://vercel.com/new
3. Import the repository
4. Add environment variables in Vercel dashboard
5. Deploy

### Option 2: Railway

1. Create new project on Railway
2. Connect GitHub repository
3. Add environment variables
4. Deploy

### Option 3: Netlify

1. Run `npm run build`
2. Deploy the `.next` folder to Netlify
3. Configure environment variables

## Connecting to Backend

This website connects to your existing Tile Station backend API. Ensure the following:

1. Backend CORS allows requests from your shop domain
2. API endpoints are prefixed with `/api/shop/`
3. Products, categories, and stores are synced automatically

## SEO Features

### Meta Tags
- Title templates for all pages
- Description meta tags
- Open Graph tags for social sharing
- Twitter Card support

### Structured Data (JSON-LD)
- Organization schema
- Product schema with pricing and availability
- WebSite schema with search action
- LocalBusiness schema for stores

### Sitemap
- Auto-generated at `/sitemap.xml`
- Includes all products, categories, and static pages
- Updated on each build

### Robots.txt
- Allows search engine crawling
- Blocks private pages (cart, checkout, account)
- References sitemap location

## Folder Structure

```
src/
├── app/
│   ├── layout.tsx         # Root layout with SEO metadata
│   ├── page.tsx           # Homepage
│   ├── products/
│   │   ├── page.tsx       # Product listing
│   │   └── [id]/page.tsx  # Product detail
│   ├── stores/page.tsx    # Store locations
│   ├── cart/page.tsx      # Shopping cart
│   ├── sitemap.ts         # Dynamic sitemap
│   └── robots.ts          # Robots.txt config
├── components/
│   ├── Header.tsx
│   ├── Footer.tsx
│   └── ProductCard.tsx
└── lib/
    ├── api.ts             # API client
    └── utils.ts           # Utility functions
```

## Next Steps

After initial deployment:

1. **Add Custom Domain**: Configure your domain (e.g., tilestation.co.uk)
2. **Set Up Google Search Console**: Verify ownership and submit sitemap
3. **Add Analytics**: Google Analytics or Vercel Analytics
4. **Add Payment Integration**: Stripe checkout for purchases
5. **Add Customer Auth**: Login/registration for checkout

## Support

For issues or questions, contact the development team.
