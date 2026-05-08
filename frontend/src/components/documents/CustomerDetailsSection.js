import React from 'react';
import { Input } from '../ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { User, Search } from 'lucide-react';
import { Button } from '../ui/button';

/**
 * Shared Customer Details Section for Invoice/Quotation
 */
export const CustomerDetailsSection = ({
  customerName,
  customerPhone,
  customerEmail,
  customerAddress,
  onNameChange,
  onPhoneChange,
  onEmailChange,
  onAddressChange,
  customers = [],
  showCustomerSearch = false,
  customerSearchTerm = '',
  onCustomerSearchChange,
  onCustomerSelect,
  onToggleSearch,
  className = ''
}) => {
  // Filter customers based on search
  const filteredCustomers = customers.filter(c =>
    c.name?.toLowerCase().includes(customerSearchTerm.toLowerCase()) ||
    c.phone?.includes(customerSearchTerm) ||
    c.email?.toLowerCase().includes(customerSearchTerm.toLowerCase())
  ).slice(0, 8);

  return (
    <Card className={className}>
      <CardHeader className="pb-4">
        <CardTitle className="text-lg flex items-center justify-between">
          <span className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Customer Details
          </span>
          {onToggleSearch && customers.length > 0 && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={onToggleSearch}
              data-testid="find-customer-btn"
            >
              <Search className="h-4 w-4 mr-1" />
              Find Customer
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Customer Search Dropdown */}
        {showCustomerSearch && (
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg mb-4">
            <Input
              placeholder="Search by name, phone, or email..."
              value={customerSearchTerm}
              onChange={(e) => onCustomerSearchChange?.(e.target.value)}
              autoFocus
              data-testid="customer-search-input"
            />
            {filteredCustomers.length > 0 && (
              <div className="mt-2 max-h-48 overflow-y-auto border rounded bg-white">
                {filteredCustomers.map(customer => (
                  <div
                    key={customer.id}
                    className="p-2 hover:bg-gray-100 cursor-pointer border-b last:border-b-0"
                    onClick={() => onCustomerSelect?.(customer)}
                    data-testid={`customer-option-${customer.id}`}
                  >
                    <div className="font-medium">{customer.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {customer.phone} • {customer.email}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {customerSearchTerm && filteredCustomers.length === 0 && (
              <p className="mt-2 text-sm text-muted-foreground">No customers found</p>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">Name</label>
            <Input
              value={customerName}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="Customer name"
              data-testid="customer-name-input"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">Phone</label>
            <Input
              value={customerPhone}
              onChange={(e) => onPhoneChange(e.target.value)}
              placeholder="Phone number"
              data-testid="customer-phone-input"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">Email</label>
            <Input
              value={customerEmail}
              onChange={(e) => onEmailChange(e.target.value)}
              placeholder="Email address"
              data-testid="customer-email-input"
            />
          </div>
        </div>
        <div>
          <label className="text-sm font-medium mb-1 block">Address</label>
          <Input
            value={customerAddress}
            onChange={(e) => onAddressChange(e.target.value)}
            placeholder="Full address"
            data-testid="customer-address-input"
          />
        </div>
      </CardContent>
    </Card>
  );
};

export default CustomerDetailsSection;
