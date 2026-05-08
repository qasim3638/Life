import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { User, Phone, Mail, MapPin, X, Search } from 'lucide-react';

/**
 * CustomerDetailsSection - Complete customer details with auto-suggestion
 * Shows suggestions when typing in Name, Phone, or Email fields
 * When a suggestion is selected, auto-fills all customer fields
 * Supports clearing/deleting all customer data
 */
export const CustomerDetailsSection = ({
  name,
  phone,
  email,
  address,
  onNameChange,
  onPhoneChange,
  onEmailChange,
  onAddressChange,
  onSelectCustomer,  // Callback when customer is selected: (customer) => void
  onClear,           // Callback to clear all customer data
  nameRequired = false,
  phoneRequired = false,
  emailRequired = false,
  addressRequired = false,
  namePlaceholder = "Customer name",
  phonePlaceholder = "Phone number",
  emailPlaceholder = "Email address",
  addressPlaceholder = "Full address",
  className = "",
  layout = "grid",   // "grid" or "stacked"
  showClearButton = true,  // Show clear/delete button
  showHeader = true,       // Show section header
  headerTitle = "Customer Details",
  toTitleCase = null       // Optional title case formatter
}) => {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeField, setActiveField] = useState(null);  // 'name', 'phone', 'email'
  const [loading, setLoading] = useState(false);
  const containerRef = useRef(null);
  const debounceRef = useRef(null);

  // Fetch suggestions when any searchable field changes
  const fetchSuggestions = async (searchTerm) => {
    if (!searchTerm || searchTerm.length < 2) {
      setSuggestions([]);
      return;
    }

    setLoading(true);
    try {
      // Fire both lookups in parallel — the legacy email-suggestions path
      // (returning customers from past invoices/quotations) AND the new
      // unified search (in-store users + online shop_customers). We merge,
      // de-dupe by email, prefer the online entry when present so the trade
      // chip + linked_shop_customer_id flow through correctly.
      const [legacyResp, unifiedResp] = await Promise.allSettled([
        api.getCustomerEmailSuggestions(searchTerm),
        api.unifiedCustomerSearch(searchTerm, 10),
      ]);
      const legacy = legacyResp.status === 'fulfilled' ? (legacyResp.value.data || []) : [];
      const unified = unifiedResp.status === 'fulfilled' ? (unifiedResp.value.data?.results || []) : [];

      const byEmail = new Map();
      legacy.forEach(c => {
        const key = (c.email || '').toLowerCase().trim();
        if (key) byEmail.set(key, { ...c, _origin: 'legacy' });
      });
      unified.forEach(c => {
        const key = (c.email || '').toLowerCase().trim();
        if (!key) return;
        const existing = byEmail.get(key) || {};
        // Unified result wins because it has trade fields + canonical address
        const addressStr = c.address
          ? [c.address.line1, c.address.line2, c.address.city, c.address.postcode].filter(Boolean).join(', ')
          : existing.address;
        byEmail.set(key, {
          ...existing,
          ...c,
          address: addressStr,
          _origin: c.source, // 'users' | 'shop' | 'users+shop'
          _is_online: (c.source || '').includes('shop'),
          _is_trade: !!c.is_trade,
        });
      });
      setSuggestions(Array.from(byEmail.values()));
    } catch (error) {
      console.error('Error fetching customer suggestions:', error);
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  };

  // Debounced search
  const debouncedSearch = (value) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(value);
    }, 300);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setShowSuggestions(false);
        setActiveField(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  const handleSelect = (customer) => {
    // Fill all fields with customer data
    if (onNameChange && customer.name) onNameChange(customer.name);
    if (onPhoneChange && customer.phone) onPhoneChange(customer.phone);
    if (onEmailChange && customer.email) onEmailChange(customer.email);
    if (onAddressChange && customer.address) onAddressChange(customer.address);
    
    setShowSuggestions(false);
    setActiveField(null);
    
    // Notify parent
    if (onSelectCustomer) {
      onSelectCustomer(customer);
    }
  };

  const handleFieldFocus = (field, value) => {
    setActiveField(field);
    if (value && value.length >= 2) {
      setShowSuggestions(true);
      debouncedSearch(value);
    }
  };

  const handleFieldChange = (field, value, onChange) => {
    onChange(value);
    setActiveField(field);
    if (value && value.length >= 2) {
      setShowSuggestions(true);
      debouncedSearch(value);
    } else {
      setSuggestions([]);
    }
  };

  // Handle blur event for title case conversion
  const handleBlur = (value, onChange) => {
    if (toTitleCase && value) {
      onChange(toTitleCase(value));
    }
  };

  // Clear all customer data
  const handleClearAll = () => {
    if (onClear) {
      onClear();
    } else {
      // Default clear behavior
      if (onNameChange) onNameChange('');
      if (onPhoneChange) onPhoneChange('');
      if (onEmailChange) onEmailChange('');
      if (onAddressChange) onAddressChange('');
    }
    setSuggestions([]);
    setShowSuggestions(false);
  };

  // Check if any field has data
  const hasData = name || phone || email || address;

  const gridClass = layout === "grid" 
    ? "grid grid-cols-1 md:grid-cols-2 gap-4" 
    : "space-y-4";

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Header with Clear Button */}
      {showHeader && (
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-lg flex items-center gap-2">
            <User className="h-5 w-5" />
            {headerTitle}
          </h3>
          {showClearButton && hasData && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleClearAll}
              className="text-red-600 hover:text-red-700 hover:bg-red-50"
              data-testid="clear-customer-btn"
            >
              <X className="h-4 w-4 mr-1" />
              Clear
            </Button>
          )}
        </div>
      )}

      <div className={gridClass}>
        {/* Name Field */}
        <div>
          <label className="text-sm text-muted-foreground flex items-center gap-1">
            Name {nameRequired && <span className="text-red-500">*</span>}
          </label>
          <Input
            value={name}
            onChange={(e) => handleFieldChange('name', e.target.value, onNameChange)}
            onFocus={() => handleFieldFocus('name', name)}
            onBlur={(e) => handleBlur(e.target.value, onNameChange)}
            placeholder={namePlaceholder}
            required={nameRequired}
            data-testid="customer-name-input"
            autoComplete="off"
            className={nameRequired && !name ? 'border-amber-300' : ''}
          />
        </div>

        {/* Phone Field */}
        <div>
          <label className="text-sm text-muted-foreground flex items-center gap-1">
            Phone {phoneRequired && <span className="text-red-500">*</span>}
          </label>
          <Input
            value={phone}
            onChange={(e) => handleFieldChange('phone', e.target.value, onPhoneChange)}
            onFocus={() => handleFieldFocus('phone', phone)}
            placeholder={phonePlaceholder}
            required={phoneRequired}
            data-testid="customer-phone-input"
            autoComplete="off"
            className={phoneRequired && !phone ? 'border-amber-300' : ''}
          />
        </div>

        {/* Email Field */}
        <div>
          <label className="text-sm text-muted-foreground flex items-center gap-1">
            Email {emailRequired && <span className="text-red-500">*</span>}
          </label>
          <Input
            type="email"
            value={email}
            onChange={(e) => handleFieldChange('email', e.target.value, onEmailChange)}
            onFocus={() => handleFieldFocus('email', email)}
            placeholder={emailPlaceholder}
            required={emailRequired}
            data-testid="customer-email-input"
            autoComplete="off"
            className={emailRequired && !email ? 'border-amber-300' : ''}
          />
        </div>

        {/* Address Field */}
        <div>
          <label className="text-sm text-muted-foreground flex items-center gap-1">
            Address {addressRequired && <span className="text-red-500">*</span>}
          </label>
          <Input
            value={address}
            onChange={(e) => onAddressChange(e.target.value)}
            onBlur={(e) => handleBlur(e.target.value, onAddressChange)}
            placeholder={addressPlaceholder}
            required={addressRequired}
            data-testid="customer-address-input"
            autoComplete="off"
            className={addressRequired && !address ? 'border-amber-300' : ''}
          />
        </div>
      </div>

      {/* Suggestions Dropdown */}
      {showSuggestions && (suggestions.length > 0 || loading) && (
        <div className="absolute z-50 w-full mt-1 bg-white border rounded-md shadow-lg max-h-60 overflow-auto">
          {loading ? (
            <div className="px-4 py-3 text-sm text-gray-500">
              Searching customers...
            </div>
          ) : suggestions.length > 0 ? (
            <>
              <div className="px-3 py-2 text-xs text-gray-500 bg-gray-50 border-b font-medium">
                🔄 Returning Customers - Click to auto-fill details
              </div>
              {suggestions.map((customer, index) => (
                <div
                  key={`${customer.email}-${index}`}
                  className="px-3 py-3 cursor-pointer hover:bg-blue-50 border-b last:border-b-0 transition-colors"
                  onClick={() => handleSelect(customer)}
                  data-testid={`customer-suggestion-${(customer.email || '').toLowerCase()}`}
                >
                  {(customer._is_online || customer._is_trade) && (
                    <div className="flex items-center gap-1 mb-1.5 flex-wrap">
                      {customer._is_online && (
                        <span
                          className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-sky-100 text-sky-800 border border-sky-200"
                          title={customer._origin === 'users+shop' ? 'Online account already linked to in-store record' : 'Online customer — picking will link this in-store invoice to their online account'}
                        >
                          🌐 Online
                        </span>
                      )}
                      {customer._is_trade && (
                        <span
                          className="inline-flex items-center gap-1 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200"
                          title={`Trade account ${customer.trade_account_number || ''}${customer.business_name ? ' · ' + customer.business_name : ''}`}
                        >
                          🏷️ Trade {customer.trade_account_number ? `· ${customer.trade_account_number}` : ''}
                        </span>
                      )}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-2">
                    {/* Name */}
                    {customer.name && (
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span className="text-sm font-medium truncate">{customer.name}</span>
                      </div>
                    )}
                    {/* Phone */}
                    {customer.phone && (
                      <div className="flex items-center gap-2">
                        <Phone className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span className="text-sm text-gray-600 truncate">{customer.phone}</span>
                      </div>
                    )}
                    {/* Email */}
                    <div className="flex items-center gap-2">
                      <Mail className="h-4 w-4 text-blue-500 flex-shrink-0" />
                      <span className="text-sm text-blue-600 truncate">{customer.email}</span>
                    </div>
                    {/* Address */}
                    {customer.address && (
                      <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span className="text-xs text-gray-500 truncate">{customer.address}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default CustomerDetailsSection;
