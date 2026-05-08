import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  Calendar, Truck, Shield, Zap, Phone, Package, CreditCard, MapPin, Star, 
  Clock, Check, Info, AlertCircle, Heart, Home, ChevronDown, ChevronUp, ArrowLeft
} from 'lucide-react';
import { ShopHeader, ShopFooter } from './TileStationHome';
import SeoHead from '../../components/seo/SeoHead';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ICON_MAP = { Calendar, Truck, Shield, Zap, Phone, Package, CreditCard, MapPin, Star, Clock, Check, Info, AlertCircle, Heart, Home };

const getIcon = (name) => ICON_MAP[name] || Info;

// Simple markdown bold renderer
const renderMarkdownText = (text) => {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="text-gray-900 font-semibold">{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
};

// Section Renderers
const TextSection = ({ section }) => (
  <div className="space-y-4">
    {section.title && <h2 className="text-2xl font-bold text-gray-900">{section.title}</h2>}
    <div className="text-gray-600 leading-relaxed whitespace-pre-line">{renderMarkdownText(section.content)}</div>
  </div>
);

const CardsSection = ({ section }) => (
  <div>
    {section.title && <h2 className="text-2xl font-bold text-gray-900 mb-6">{section.title}</h2>}
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {(section.cards || []).map((card, i) => {
        const Icon = getIcon(card.icon);
        return (
          <div key={i} className="bg-white border-2 border-gray-100 rounded-xl p-5 text-center hover:border-amber-200 hover:shadow-md transition-all">
            <div className="w-14 h-14 bg-amber-50 rounded-full flex items-center justify-center mx-auto mb-3">
              <Icon className="w-7 h-7 text-amber-600" />
            </div>
            <h3 className="font-bold text-gray-900 mb-2">{card.title}</h3>
            <p className="text-sm text-gray-500 whitespace-pre-line">{card.description}</p>
          </div>
        );
      })}
    </div>
  </div>
);

const TableSection = ({ section }) => (
  <div>
    {section.title && <h2 className="text-2xl font-bold text-gray-900 mb-4">{section.title}</h2>}
    <div className="border rounded-xl overflow-hidden">
      <table className="w-full">
        <tbody>
          {(section.rows || []).map((row, i) => (
            <tr key={i} className={`${i % 2 === 0 ? 'bg-gray-50' : 'bg-white'} border-b last:border-b-0`}>
              <td className="px-6 py-4 text-sm text-gray-700">{row.description}</td>
              <td className="px-6 py-4 text-sm font-bold text-right whitespace-nowrap">
                <span className={row.price?.toUpperCase() === 'FREE' ? 'text-green-600 bg-green-50 px-3 py-1 rounded-full' : 'text-gray-900'}>
                  {row.price}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const FaqSection = ({ section }) => {
  const [openIndex, setOpenIndex] = useState(null);
  return (
    <div>
      {section.title && <h2 className="text-2xl font-bold text-gray-900 mb-4">{section.title}</h2>}
      <div className="space-y-2">
        {(section.items || []).map((item, i) => (
          <div key={i} className="border rounded-xl overflow-hidden">
            <button
              onClick={() => setOpenIndex(openIndex === i ? null : i)}
              className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-gray-50 transition-colors"
            >
              <span className="font-medium text-gray-900">{item.question}</span>
              {openIndex === i ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
            </button>
            {openIndex === i && (
              <div className="px-6 pb-4 text-gray-600 leading-relaxed whitespace-pre-line border-t bg-gray-50">
                <div className="pt-4">{item.answer}</div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const SECTION_RENDERERS = {
  text: TextSection,
  cards: CardsSection,
  table: TableSection,
  faq: FaqSection,
};

export default function InfoPage() {
  const { slug } = useParams();
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPage = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/website-admin/info-pages/${slug}`);
        if (res.ok) {
          const data = await res.json();
          setPage(data.page);
        }
      } catch (err) {
        console.error('Error fetching info page:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchPage();
  }, [slug]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="flex items-center justify-center py-32">
          <div className="w-8 h-8 border-4 border-amber-400 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!page || page.enabled === false) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-4 py-16 text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Page Not Found</h1>
          <p className="text-gray-500 mb-6">This page is currently unavailable.</p>
          <Link to="/shop" className="text-amber-600 hover:text-amber-700 font-medium">Return to Shop</Link>
        </div>
      </div>
    );
  }

  // Build a meta-description from the first text section's content
  // (capped at 200 chars) so each info page has unique copy in search.
  const firstTextSection = (page.sections || []).find((s) => s.type === 'text');
  const metaDescription = firstTextSection?.content
    ? firstTextSection.content.replace(/\*\*/g, '').slice(0, 200)
    : `${page.title} — Tile Station information page. Free UK delivery, expert advice and showrooms in Kent and London.`;

  return (
    <div className="min-h-screen bg-gray-50" data-testid="info-page">
      <SeoHead
        title={`${page.title} — Tile Station`}
        description={metaDescription}
        canonical={`/shop/info/${slug}`}
        type="article"
      />

      {/* Hero */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 text-white py-12">
        <div className="container mx-auto px-4">
          <Link to="/shop" className="inline-flex items-center text-gray-400 hover:text-white text-sm mb-4 transition-colors">
            <ArrowLeft className="w-4 h-4 mr-1" /> Back to Shop
          </Link>
          <h1 className="text-3xl sm:text-4xl font-bold">{page.title}</h1>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-4 py-10">
        <div className="max-w-4xl mx-auto space-y-10">
          {(page.sections || []).map((section) => {
            const Renderer = SECTION_RENDERERS[section.type];
            if (!Renderer) return null;
            return <Renderer key={section.id} section={section} />;
          })}
        </div>
      </div>
    </div>
  );
}

// Default delivery content for when nothing is saved in DB
const DEFAULT_DELIVERY = {
  sections: [
    {
      id: 'delivery-cards',
      type: 'cards',
      title: 'Delivery Highlights',
      cards: [
        { title: 'Delivery Date', description: 'At the checkout, choose a delivery date that works for you', icon: 'Calendar' },
        { title: 'Truck Access', description: 'Access must be obstacle-free, wide enough and flat for safe delivery', icon: 'Truck' },
        { title: 'No Loose Surfaces', description: 'Surfaces must be hard and flat: tarmac, concrete or block paving', icon: 'Shield' },
        { title: 'Express Delivery', description: 'Need your tiles quicker? Upgrade to Express Delivery', icon: 'Zap' },
      ]
    },
    {
      id: 'delivery-times',
      type: 'text',
      title: 'Delivery Times',
      content: 'We aim to deliver all orders within 2-3 working days from Monday to Friday excluding Saturday and Sunday.\n\nPlease note that orders containing multiple samples or underfloor heating products will be delivered separately.'
    },
    {
      id: 'delivery-rates',
      type: 'table',
      title: 'Delivery Rates',
      rows: [
        { description: 'UK online orders over £499 (excluding Scotland)', price: 'FREE' },
        { description: 'Free Cut Sample Delivery', price: 'FREE' },
        { description: 'Small Full-Size Sample (Parcel up to 2 KG)', price: '£0.99' },
        { description: 'Small Orders (Less Than 18 Kg)', price: '£11.99' },
        { description: 'Pallet Delivery for orders under £499', price: 'Calculated at checkout' },
      ]
    },
  ]
};

// Compact delivery info for product detail page tab
export function DeliveryInfoCompact() {
  const [page, setPage] = useState(DEFAULT_DELIVERY);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/website-admin/info-pages/delivery`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.page) setPage(d.page); })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  return (
    <div className="space-y-6" data-testid="delivery-info-compact">
      {(page.sections || []).map(section => {
        if (section.type === 'cards') {
          return (
            <div key={section.id}>
              <h3 className="font-bold text-gray-900 mb-3">{section.title}</h3>
              <div className="grid grid-cols-2 gap-3">
                {(section.cards || []).map((card, i) => {
                  const Icon = getIcon(card.icon);
                  return (
                    <div key={i} className="flex items-start gap-2 p-3 bg-gray-50 rounded-lg">
                      <Icon className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-gray-900">{card.title}</p>
                        <p className="text-xs text-gray-500">{card.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        }
        if (section.type === 'table') {
          return (
            <div key={section.id}>
              <h3 className="font-bold text-gray-900 mb-2">{section.title}</h3>
              <div className="text-sm space-y-1">
                {(section.rows || []).map((row, i) => (
                  <div key={i} className="flex justify-between py-1.5 border-b border-gray-100 last:border-0">
                    <span className="text-gray-600">{row.description}</span>
                    <span className={`font-medium ${row.price?.toUpperCase() === 'FREE' ? 'text-green-600' : 'text-gray-900'}`}>{row.price}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        }
        if (section.type === 'text') {
          return (
            <div key={section.id}>
              <h3 className="font-bold text-gray-900 mb-2">{section.title}</h3>
              <p className="text-sm text-gray-600 whitespace-pre-line">{section.content}</p>
            </div>
          );
        }
        return null;
      })}
      <Link to="/shop/info/delivery" className="text-sm text-amber-600 hover:text-amber-700 font-medium">
        View full delivery information &rarr;
      </Link>
    </div>
  );
}
