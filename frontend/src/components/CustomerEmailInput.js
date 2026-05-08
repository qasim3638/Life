import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { Input } from './ui/input';
import { User, Phone, Mail } from 'lucide-react';

/**
 * CustomerEmailInput - Auto-suggest email input with customer data
 * Shows suggestions from past customers as user types
 * When a suggestion is selected, can also fill name and phone fields
 */
export const CustomerEmailInput = ({
  value,
  onChange,
  onSelectCustomer,  // Optional callback when customer is selected: (customer) => void
  placeholder = "Email address",
  className = "",
  required = false,
  disabled = false,
  "data-testid": testId = "customer-email-input"
}) => {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);
  const debounceRef = useRef(null);

  // Fetch suggestions when value changes
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (!value || value.length < 2) {
      setSuggestions([]);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await api.getCustomerEmailSuggestions(value);
        setSuggestions(response.data || []);
      } catch (error) {
        console.error('Error fetching email suggestions:', error);
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [value]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        dropdownRef.current && 
        !dropdownRef.current.contains(event.target) &&
        inputRef.current &&
        !inputRef.current.contains(event.target)
      ) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (customer) => {
    onChange(customer.email);
    setShowSuggestions(false);
    
    // Notify parent to fill other fields if callback provided
    if (onSelectCustomer) {
      onSelectCustomer(customer);
    }
  };

  const handleFocus = () => {
    if (suggestions.length > 0 || (value && value.length >= 2)) {
      setShowSuggestions(true);
    }
  };

  return (
    <div className="relative">
      <Input
        ref={inputRef}
        type="email"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setShowSuggestions(true);
        }}
        onFocus={handleFocus}
        placeholder={placeholder}
        className={className}
        required={required}
        disabled={disabled}
        data-testid={testId}
        autoComplete="off"
      />
      
      {/* Suggestions Dropdown */}
      {showSuggestions && (suggestions.length > 0 || loading) && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-white border rounded-md shadow-lg max-h-60 overflow-auto"
        >
          {loading ? (
            <div className="px-4 py-3 text-sm text-gray-500">
              Searching customers...
            </div>
          ) : suggestions.length > 0 ? (
            <>
              <div className="px-3 py-2 text-xs text-gray-500 bg-gray-50 border-b">
                Returning Customers
              </div>
              {suggestions.map((customer, index) => (
                <div
                  key={`${customer.email}-${index}`}
                  className="px-3 py-2 cursor-pointer hover:bg-blue-50 border-b last:border-b-0"
                  onClick={() => handleSelect(customer)}
                >
                  <div className="flex items-center gap-2">
                    <Mail className="h-4 w-4 text-blue-500 flex-shrink-0" />
                    <span className="text-sm font-medium text-blue-600 truncate">
                      {customer.email}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-1 ml-6">
                    {customer.name && (
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <User className="h-3 w-3" />
                        {customer.name}
                      </div>
                    )}
                    {customer.phone && (
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <Phone className="h-3 w-3" />
                        {customer.phone}
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

export default CustomerEmailInput;
