import Link from 'next/link';

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-slate-900 text-white mt-16">
      <div className="container mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* About */}
          <div>
            <h3 className="font-bold text-lg mb-4">Tile Station</h3>
            <p className="text-slate-400 text-sm">
              Your one-stop shop for luxury tiles and bathroom products. 
              Quality products at competitive prices.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-bold text-lg mb-4">Quick Links</h3>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link href="/products" className="hover:text-white transition-colors">
                  All Products
                </Link>
              </li>
              <li>
                <Link href="/products?clearance_only=true" className="hover:text-white transition-colors">
                  Clearance Sale
                </Link>
              </li>
              <li>
                <Link href="/stores" className="hover:text-white transition-colors">
                  Our Stores
                </Link>
              </li>
              <li>
                <Link href="/contact" className="hover:text-white transition-colors">
                  Contact Us
                </Link>
              </li>
            </ul>
          </div>

          {/* Customer Service */}
          <div>
            <h3 className="font-bold text-lg mb-4">Customer Service</h3>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>
                <Link href="/delivery" className="hover:text-white transition-colors">
                  Delivery Information
                </Link>
              </li>
              <li>
                <Link href="/returns" className="hover:text-white transition-colors">
                  Returns & Refunds
                </Link>
              </li>
              <li>
                <Link href="/faq" className="hover:text-white transition-colors">
                  FAQs
                </Link>
              </li>
              <li>
                <Link href="/terms" className="hover:text-white transition-colors">
                  Terms & Conditions
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-white transition-colors">
                  Privacy Policy
                </Link>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="font-bold text-lg mb-4">Contact Us</h3>
            <ul className="space-y-2 text-sm text-slate-400">
              <li>Email: info@tilestation.co.uk</li>
              <li>Phone: 01234 567890</li>
              <li>Mon-Sat: 9am - 5pm</li>
            </ul>
            <div className="mt-4">
              <p className="text-sm text-slate-400 mb-2">We accept:</p>
              <div className="flex gap-2 text-xs">
                <span className="bg-slate-800 px-2 py-1 rounded">Visa</span>
                <span className="bg-slate-800 px-2 py-1 rounded">Mastercard</span>
                <span className="bg-slate-800 px-2 py-1 rounded">PayPal</span>
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800 mt-8 pt-8 text-center text-sm text-slate-500">
          <p>© {currentYear} Tile Station. All rights reserved.</p>
        </div>
      </div>

      {/* Schema.org Organization markup */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'Organization',
            name: 'Tile Station',
            url: process.env.NEXT_PUBLIC_SITE_URL,
            logo: `${process.env.NEXT_PUBLIC_SITE_URL}/logo.png`,
            contactPoint: {
              '@type': 'ContactPoint',
              telephone: '+44-1234-567890',
              contactType: 'customer service',
              areaServed: 'GB',
              availableLanguage: 'English',
            },
            sameAs: [
              // Add your social media URLs here
            ],
          }),
        }}
      />
    </footer>
  );
}
