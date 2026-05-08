/**
 * PromoBanner — site-wide image-strip banner above the announcement
 * ribbon. Pulled from /api/website/promo-banner (which respects
 * manual on/off + scheduled window). When hidden, renders nothing.
 *
 * Use case: bank-holiday sale image, seasonal campaign, etc. The
 * admin generates the image in Marketing Studio and 1-click publishes
 * it here.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

const PromoBanner = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancel = false;
    axios.get(`${API}/api/website/promo-banner`)
      .then((r) => { if (!cancel && r.data?.enabled) setData(r.data); })
      .catch(() => {});
    return () => { cancel = true; };
  }, []);

  if (!data?.image_url) return null;

  const imgSrc = data.image_url.startsWith('http')
    ? data.image_url
    : `${API}${data.image_url}`;

  const inner = (
    <img
      src={imgSrc}
      alt={data.alt_text || 'Promotional banner'}
      className="block w-full h-auto"
      loading="eager"
      data-testid="promo-banner-image"
    />
  );

  return (
    <div className="w-full relative" data-testid="promo-banner">
      {data.link_url ? (
        <a href={data.link_url} className="block hover:opacity-95 transition" data-testid="promo-banner-link">
          {inner}
        </a>
      ) : inner}
    </div>
  );
};

export default PromoBanner;
