'use client';

import { Truck, Package, BadgePercent, Headphones, Scissors, Clock } from 'lucide-react';

const usps = [
  {
    icon: Truck,
    title: 'Free UK Delivery',
    subtitle: 'On orders over £500',
  },
  {
    icon: Scissors,
    title: 'Free Samples',
    subtitle: 'Try before you buy',
  },
  {
    icon: Clock,
    title: 'Next Day Available',
    subtitle: 'Fast dispatch',
  },
  {
    icon: BadgePercent,
    title: 'Price Match',
    subtitle: 'Best prices guaranteed',
  },
  {
    icon: Package,
    title: 'Click & Collect',
    subtitle: '4 UK showrooms',
  },
  {
    icon: Headphones,
    title: 'Expert Support',
    subtitle: 'Call us anytime',
  },
];

export function USPBar() {
  return (
    <section className="bg-slate-900 py-4 border-b border-slate-800" data-testid="usp-bar">
      <div className="container mx-auto px-4">
        <div className="flex overflow-x-auto gap-8 md:gap-0 md:grid md:grid-cols-6 scrollbar-hide">
          {usps.map((usp, index) => (
            <div
              key={index}
              className="flex items-center gap-3 flex-shrink-0 md:justify-center px-4 md:px-2"
            >
              <usp.icon className="w-5 h-5 text-teal-500 flex-shrink-0" />
              <div className="text-white">
                <p className="text-sm font-semibold whitespace-nowrap">{usp.title}</p>
                <p className="text-xs text-slate-400 whitespace-nowrap">{usp.subtitle}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
