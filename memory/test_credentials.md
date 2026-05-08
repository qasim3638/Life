# Test Credentials

## Admin Account
- Email: admin@test.com
- Password: admin123
- Role: super_admin
- Login URL: /admin/login

## Pallet pricing test fixture (Feb 7, 2026 — half/full pallet feature)
- Tile: Alabaster Polished 60x60cm — series `TestSeries`
- m2_per_pallet=32, m2_per_half_pallet=16, half_pallet_price=27.5, pallet_price=26.09, room_lot_price=28.99
- Storefront PDP: /shop/collection/TestSeries → click 60x60cm size → pallet-tier-selector card visible
- Product (admin): id `3ab24973-a23e-4805-8164-9186e5888146` (Adhesive 20kg) — used by pallet PUT/GET round-trip tests
