import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { UserPlus, Building2, Shield, Check, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';

// Permission labels for display
const PERMISSION_LABELS = {
  dashboard: 'Dashboard',
  products: 'Products',
  categories: 'Categories',
  orders: 'Orders',
  epos: 'EPOS (Invoices)',
  customer_pricing: 'Customer Pricing',
  customer_invites: 'Customer Invites',
  bulk_inquiries: 'Bulk Inquiries',
  marketing: 'Marketing',
  showrooms: 'Stores',
  reports: 'Reports',
  user_management: 'User Management'
};

export const StaffRegister = () => {
  const { code } = useParams();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [inviteData, setInviteData] = useState(null);
  const [error, setError] = useState(null);
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });

  useEffect(() => {
    validateInvite();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  const validateInvite = async () => {
    try {
      const result = await api.validateStaffInvite(code);
      setInviteData(result.data);
      setError(null);
    } catch (error) {
      setError(error.response?.data?.detail || 'Invalid or expired invite link');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      toast.error('Please enter your name');
      return;
    }
    
    if (!formData.email.trim()) {
      toast.error('Please enter your email');
      return;
    }
    
    if (formData.password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    
    if (formData.password !== formData.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    setSubmitting(true);
    try {
      const result = await api.registerWithStaffInvite(code, {
        name: formData.name,
        email: formData.email,
        password: formData.password
      });
      
      // Store token and user
      localStorage.setItem('token', result.data.token);
      setUser(result.data.user);
      
      toast.success('Account created successfully!');
      navigate('/admin');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Registration failed');
    } finally {
      setSubmitting(false);
    }
  };

  const getRoleBadge = (role) => {
    const badges = {
      admin: <span className="px-3 py-1 text-sm font-medium rounded-full bg-blue-100 text-blue-800">Admin</span>,
      manager: <span className="px-3 py-1 text-sm font-medium rounded-full bg-green-100 text-green-800">Manager</span>,
      staff: <span className="px-3 py-1 text-sm font-medium rounded-full bg-gray-100 text-gray-800">Staff</span>
    };
    return badges[role] || <span className="px-3 py-1 text-sm rounded-full bg-gray-100">{role}</span>;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Validating invite link...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="max-w-md w-full p-8 text-center">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold mb-2">Invalid Invite Link</h1>
          <p className="text-muted-foreground mb-6">{error}</p>
          <Button onClick={() => navigate('/')} variant="outline">
            Go to Login
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="max-w-lg w-full p-8">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-4">
            <UserPlus className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold">Join Tile Station</h1>
          <p className="text-muted-foreground mt-1">Create your staff account</p>
        </div>

        {/* Invite Details */}
        <div className="bg-gray-50 rounded-lg p-4 mb-6 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Role:</span>
            {getRoleBadge(inviteData.role)}
          </div>
          
          {inviteData.showroom_name && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Store:</span>
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{inviteData.showroom_name}</span>
              </div>
            </div>
          )}
          
          <div>
            <span className="text-sm text-muted-foreground block mb-2">Permissions:</span>
            <div className="flex flex-wrap gap-1">
              {inviteData.permissions?.map(p => (
                <span key={p} className="px-2 py-0.5 text-xs bg-white border rounded">
                  {PERMISSION_LABELS[p] || p}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Registration Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-1 block">
              Full Name <span className="text-red-500">*</span>
            </label>
            <Input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Enter your full name"
              data-testid="staff-reg-name"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium mb-1 block">
              Email Address <span className="text-red-500">*</span>
            </label>
            <Input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="your.email@tilestation.co.uk"
              data-testid="staff-reg-email"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium mb-1 block">
              Password <span className="text-red-500">*</span>
            </label>
            <Input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              placeholder="Create a strong password"
              data-testid="staff-reg-password"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium mb-1 block">
              Confirm Password <span className="text-red-500">*</span>
            </label>
            <Input
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
              placeholder="Confirm your password"
              data-testid="staff-reg-confirm-password"
            />
          </div>
          
          <Button type="submit" className="w-full" disabled={submitting} data-testid="staff-reg-submit">
            {submitting ? 'Creating Account...' : 'Create Account'}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground mt-6">
          Already have an account?{' '}
          <a href="/" className="text-primary hover:underline">
            Sign in
          </a>
        </p>
      </Card>
    </div>
  );
};

export default StaffRegister;
