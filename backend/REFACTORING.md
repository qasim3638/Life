# Backend Refactoring Guide

## Current Structure

```
/app/backend/
├── server.py           # Main entry point (~5400 lines - reduced from 6500)
├── server.backup.py    # Backup of original server.py
├── config.py           # Database and environment configuration
├── models/             # Pydantic models
│   ├── __init__.py     # Exports all models
│   ├── user.py         # User, Auth, StaffPin models
│   ├── product.py      # Product, Category models
│   ├── invoice.py      # Invoice, LineItem, Deposit models
│   ├── order.py        # Order, OTP models
│   └── common.py       # Showroom, Analytics, BulkInquiry, etc.
├── routes/             # API route handlers (ACTIVE - being used)
│   ├── __init__.py     # Main router aggregator
│   ├── showrooms.py    # Showroom CRUD ✅
│   ├── staff_pins.py   # Staff PIN management ✅
│   ├── customers.py    # Customer management ✅
│   ├── admin.py        # Admin user management ✅
│   ├── audit.py        # Audit logs ✅
│   └── invites.py      # Customer & Staff invites ✅
├── services/           # Business logic services
│   ├── __init__.py     # Exports all services
│   ├── auth.py         # Authentication, password hashing, JWT
│   ├── audit.py        # Audit logging
│   └── email.py        # Email services (Resend)
└── utils/              # Utility functions
    └── __init__.py     # generate_id, generate_code, etc.
```

## Completed Refactoring (December 2025)

### Phase 1: Route Extraction ✅
The following routes have been extracted from `server.py` to `/routes/`:

1. **showrooms.py** - Showroom CRUD operations
   - `GET /showrooms` - List all showrooms
   - `POST /showrooms` - Create showroom
   - `PUT /showrooms/{id}` - Update showroom
   - `DELETE /showrooms/{id}` - Delete showroom

2. **staff_pins.py** - Staff PIN management
   - `POST /staff-pins` - Create staff PIN
   - `GET /staff-pins` - List all staff PINs
   - `GET /staff-pins/{id}` - Get specific staff PIN
   - `PUT /staff-pins/{id}` - Update staff PIN
   - `DELETE /staff-pins/{id}` - Delete staff PIN
   - `POST /staff-pins/verify` - Verify staff PIN

3. **customers.py** - Customer management
   - `GET /customers` - List customers with filters
   - `PUT /customers/{email}/showroom` - Assign customer to showroom

4. **admin.py** - Admin user management (Super Admin only)
   - `GET /admin/users` - List admin/staff users
   - `GET /admin/permissions` - Get available permissions
   - `PUT /admin/users/{email}/permissions` - Update user permissions
   - `POST /admin/users` - Create admin user
   - `DELETE /admin/users/{email}` - Delete admin user

5. **audit.py** - Audit log management (Super Admin only)
   - `GET /audit-logs` - List audit logs with filters
   - `GET /audit-logs/stats` - Get audit statistics
   - `GET /audit-logs/{id}` - Get audit log detail
   - `GET /audit-logs/entity/{type}/{id}` - Get entity audit history

6. **invites.py** - Customer & Staff invites
   - `POST /invites` - Create customer invite
   - `GET /invites` - List customer invites
   - `GET /invites/validate/{code}` - Validate customer invite
   - `DELETE /invites/{id}` - Delete customer invite
   - `POST /invites/send-email` - Send customer invite email
   - `POST /staff-invites` - Create staff invite
   - `GET /staff-invites` - List staff invites
   - `GET /staff-invites/{code}/validate` - Validate staff invite
   - `POST /staff-invites/{code}/register` - Register with staff invite
   - `DELETE /staff-invites/{id}` - Delete staff invite
   - `POST /staff-invites/send-email` - Send staff invite email

### Line Count Reduction
- **Before**: ~6,500 lines in server.py
- **After**: ~5,400 lines in server.py
- **Reduction**: ~1,100 lines (~17% reduction)

## Next Steps for Further Refactoring

### Phase 2: Extract More Routes (Medium Priority)
Remaining route groups in server.py that should be extracted:

1. **products.py** - Product CRUD and stock management (LARGE)
2. **invoices.py** - Invoice handling (LARGEST, most complex)
3. **orders.py** - Order management with OTP
4. **exports.py** - CSV/PDF export endpoints
5. **analytics.py** - Dashboard and analytics endpoints
6. **marketing.py** - Marketing campaign endpoints
7. **emails.py** - Email sending and inbox management

### Phase 3: Extract Helper Functions (Lower Priority)
- Move inline utility functions to `/utils/`
- Extract email templates to separate files
- Move PDF generation to a service

## Testing After Each Change

Always run these tests after any refactoring:

```bash
# Syntax check
python -c "import server; print('OK')"

# Health check
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
curl -s "$API_URL/api/health"

# Auth test
curl -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test"}'

# Route-specific tests
curl -s "$API_URL/api/showrooms" -H "Authorization: Bearer $TOKEN"
```

## Important Notes
- Routes in `/routes/` are now ACTIVE and being used
- The modular router is included via: `from routes import api_router as modular_router`
- All routes are prefixed with `/api` when included in the main app
- Keep server.backup.py until all testing is complete
- Refactor incrementally, test after each change
