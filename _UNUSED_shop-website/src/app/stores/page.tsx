import { Metadata } from 'next';
import { MapPin, Phone, Mail, Clock } from 'lucide-react';
import { api, Store } from '@/lib/api';

export const metadata: Metadata = {
  title: 'Our Showrooms | Tile Station UK',
  description: 'Visit one of our 4 UK showrooms in Gravesend, Tonbridge, Chingford, and Sydenham. Experience our premium tiles and bathroom products in person.',
  alternates: {
    canonical: '/stores',
  },
  openGraph: {
    title: 'Our Showrooms | Tile Station UK',
    description: 'Visit one of our 4 UK showrooms. Experience our premium tiles and bathroom products in person.',
    type: 'website',
  },
};

async function getStores(): Promise<Store[]> {
  try {
    return await api.getStores();
  } catch (error) {
    console.error('Failed to fetch stores:', error);
    return [];
  }
}

export default async function StoresPage() {
  const stores = await getStores();

  // JSON-LD for local business listings
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'Tile Station',
    url: process.env.NEXT_PUBLIC_SITE_URL,
    department: stores.map(store => ({
      '@type': 'LocalBusiness',
      name: `Tile Station ${store.name}`,
      address: {
        '@type': 'PostalAddress',
        streetAddress: store.address,
        addressCountry: 'GB',
      },
      telephone: store.phone,
      email: store.email,
      openingHours: store.opening_hours,
    })),
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-3xl mx-auto text-center mb-12">
        <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-4">Our Showrooms</h1>
        <p className="text-slate-500">
          Visit one of our showrooms to see our full range of tiles and bathroom products. 
          Our expert team is ready to help you find the perfect products for your project.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
        {stores.map((store) => (
          <article
            key={store.id}
            className="bg-white p-6 rounded-xl shadow-sm hover:shadow-lg transition-shadow"
          >
            <h2 className="text-xl font-bold text-slate-900 mb-4">{store.name}</h2>
            
            <div className="space-y-3 text-sm">
              {store.address && (
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                  <address className="text-slate-600 not-italic">{store.address}</address>
                </div>
              )}
              
              {store.phone && (
                <div className="flex items-center gap-3">
                  <Phone className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <a href={`tel:${store.phone}`} className="text-slate-600 hover:text-amber-600">
                    {store.phone}
                  </a>
                </div>
              )}
              
              {store.email && (
                <div className="flex items-center gap-3">
                  <Mail className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <a href={`mailto:${store.email}`} className="text-slate-600 hover:text-amber-600">
                    {store.email}
                  </a>
                </div>
              )}
              
              {store.opening_hours && (
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-amber-600 flex-shrink-0" />
                  <span className="text-slate-600">{store.opening_hours}</span>
                </div>
              )}
            </div>
          </article>
        ))}
      </div>

      {/* CTA Section */}
      <div className="mt-12 text-center bg-slate-100 rounded-2xl p-8 max-w-3xl mx-auto">
        <h3 className="text-xl font-bold text-slate-900 mb-2">Can't visit in person?</h3>
        <p className="text-slate-500 mb-4">
          Browse our full collection online and get free delivery on orders over £500.
        </p>
        <a
          href="/products"
          className="text-amber-600 hover:text-amber-700 font-medium inline-flex items-center gap-1"
        >
          Shop Online →
        </a>
      </div>

      {/* JSON-LD Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    </div>
  );
}
