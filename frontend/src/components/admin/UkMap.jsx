/**
 * UkMap — proper Leaflet map (OpenStreetMap tiles) with a single visitor pin.
 *
 * Rendered inside the visitor detail modal. Defaults to a UK-bounded view
 * when the pin is in the UK; otherwise centres on the pin globally.
 *
 * Why Leaflet over our previous stylised SVG: the user wanted real
 * recognisable geography. Leaflet's tiny footprint (~150KB gz) is fine
 * because this map only loads on the admin live-visitors page.
 */
import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Leaflet's bundled icon URLs break under bundlers (CRA/webpack). Inline SVG.
const PinIcon = L.divIcon({
  className: '',
  html: `
    <div style="position:relative; transform:translate(-50%, -100%);">
      <div style="width:18px; height:18px; border-radius:50%; background:#10B981; border:3px solid white; box-shadow:0 2px 8px rgba(16,185,129,0.5);"></div>
      <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); width:36px; height:36px; border-radius:50%; background:#10B981; opacity:0.25; animation:tspulse 1.8s ease-out infinite;"></div>
    </div>
    <style>
      @keyframes tspulse {
        0% { transform:translate(-50%,-50%) scale(0.5); opacity:0.6; }
        100% { transform:translate(-50%,-50%) scale(2); opacity:0; }
      }
    </style>
  `,
  iconSize: [0, 0],
  iconAnchor: [0, 0],
});

/** Re-fits the map when the pin changes (so swapping visitors recentres). */
function FitToPin({ lat, lon, inUk }) {
  const map = useMap();
  useEffect(() => {
    if (typeof lat === 'number' && typeof lon === 'number') {
      map.flyTo([lat, lon], inUk ? 9 : 5, { duration: 0.6 });
    }
  }, [lat, lon, inUk, map]);
  return null;
}

const UK_CENTER = [54.5, -3.0];
const UK_BOUNDS = [
  [49.5, -10.5], // SW
  [60.9, 2.5],   // NE
];

function isInUk(lat, lon) {
  return (
    typeof lat === 'number' && typeof lon === 'number' &&
    lat >= 49.5 && lat <= 60.9 && lon >= -10.5 && lon <= 2.5
  );
}

export default function UkMap({ pin, height = 240 }) {
  const hasPin = pin && typeof pin.lat === 'number' && typeof pin.lon === 'number';
  const inUk = hasPin && isInUk(pin.lat, pin.lon);

  return (
    <div className="rounded-xl overflow-hidden border border-gray-200 relative" style={{ height }} data-testid="uk-map">
      <MapContainer
        center={hasPin ? [pin.lat, pin.lon] : UK_CENTER}
        zoom={hasPin ? (inUk ? 9 : 5) : 5}
        bounds={hasPin ? undefined : UK_BOUNDS}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%' }}
        attributionControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {hasPin && (
          <>
            <Marker position={[pin.lat, pin.lon]} icon={PinIcon}>
              <Popup>
                <div className="text-xs">
                  <strong>{pin.label || 'Visitor'}</strong>
                  {pin.flag_emoji && <span className="ml-1">{pin.flag_emoji}</span>}
                </div>
              </Popup>
            </Marker>
            <FitToPin lat={pin.lat} lon={pin.lon} inUk={inUk} />
          </>
        )}
      </MapContainer>

      {!hasPin && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 text-xs text-gray-500 italic pointer-events-none">
          Location unavailable
        </div>
      )}
    </div>
  );
}
