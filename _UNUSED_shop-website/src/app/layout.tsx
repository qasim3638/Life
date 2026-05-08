import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Header } from '@/components/Header';
import { Footer } from '@/components/Footer';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || 'https://tilestation.co.uk'),
  title: {
    default: 'Tile Station | Premium Tiles & Bathroom Products UK',
    template: '%s | Tile Station',
  },
  description: 'Discover premium tiles and bathroom products at Tile Station. Quality craftsmanship, competitive prices. Free UK delivery on orders over £500. Visit our 4 showrooms.',
  keywords: ['tiles', 'bathroom tiles', 'floor tiles', 'wall tiles', 'ceramic tiles', 'porcelain tiles', 'UK tiles', 'bathroom products', 'tile shop', 'tile showroom'],
  authors: [{ name: 'Tile Station' }],
  creator: 'Tile Station',
  publisher: 'Tile Station',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  openGraph: {
    type: 'website',
    locale: 'en_GB',
    url: process.env.NEXT_PUBLIC_SITE_URL,
    siteName: 'Tile Station',
    title: 'Tile Station | Premium Tiles & Bathroom Products UK',
    description: 'Discover premium tiles and bathroom products at Tile Station. Quality craftsmanship, competitive prices. Free UK delivery on orders over £500.',
    images: [
      {
        url: '/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'Tile Station - Premium Tiles & Bathroom Products',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Tile Station | Premium Tiles & Bathroom Products UK',
    description: 'Discover premium tiles and bathroom products at Tile Station. Quality craftsmanship, competitive prices. Free UK delivery on orders over £500.',
    images: ['/og-image.jpg'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  verification: {
    // Add your verification codes here
    // google: 'your-google-verification-code',
    // bing: 'your-bing-verification-code',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-GB">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#0f172a" />
      </head>
      <body className={`${inter.className} bg-gray-50 min-h-screen flex flex-col`}>
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
