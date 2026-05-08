import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Package, LogIn, UserPlus, CheckCircle, Gift, Eye, EyeOff } from 'lucide-react';

export const AuthPage = () => {
  const [searchParams] = useSearchParams();
  const inviteCode = searchParams.get('invite');
  
  const [isLogin, setIsLogin] = useState(!inviteCode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [name, setName] = useState('');
  const [role, setRole] = useState('customer');
  const [loading, setLoading] = useState(false);
  const [inviteValid, setInviteValid] = useState(null);
  const [inviteNote, setInviteNote] = useState('');
  
  // Additional customer fields
  const [companyName, setCompanyName] = useState('');
  const [companyRegNumber, setCompanyRegNumber] = useState('');
  const [vatNumber, setVatNumber] = useState('');
  const [addressLine1, setAddressLine1] = useState('');
  const [addressLine2, setAddressLine2] = useState('');
  const [city, setCity] = useState('');
  const [postcode, setPostcode] = useState('');
  const [country, setCountry] = useState('United Kingdom');
  
  const { login, register } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (inviteCode) {
      validateInvite();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inviteCode]);

  const validateInvite = async () => {
    try {
      const response = await api.validateInvite(inviteCode);
      setInviteValid(true);
      setInviteNote(response.data.note || '');
      setIsLogin(false);
      setRole('customer');
    } catch (error) {
      setInviteValid(false);
      toast.error(error.response?.data?.detail || 'Invalid or expired invite link');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      let result;
      if (isLogin) {
        result = await login(email, password);
        toast.success('Welcome back!');
      } else {
        // Prepare additional data for registration
        const additionalData = {
          company_name: companyName || null,
          company_reg_number: companyRegNumber || null,
          vat_number: vatNumber || null,
          address: {
            line1: addressLine1,
            line2: addressLine2 || null,
            city: city,
            postcode: postcode,
            country: country
          }
        };
        result = await register(email, password, name, role, inviteCode || undefined, additionalData);
        toast.success('Account created successfully!');
      }
      // Use the actual user role from server response for redirection
      const userRole = result.user?.role || role;
      const adminRoles = ['admin', 'super_admin', 'manager', 'staff'];
      const isAdminUser = adminRoles.includes(userRole);
      navigate(isAdminUser ? '/admin' : '/customer/products');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2">
      <div 
        className="hidden md:block relative bg-gray-800"
      >
        <div className="relative h-full flex flex-col justify-center items-center p-12">
          <img 
            src="https://customer-assets.emergentagent.com/job_tilestock/artifacts/5ouxe3s6_clear%20logo%20-%20Tile%20Station%20Only.png" 
            alt="Tile Station Logo" 
            className="w-80 h-auto mb-8"
          />
          <p className="text-lg text-yellow-400">One Stop for luxury and quality tiles</p>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 bg-secondary">
        <div className="w-full max-w-md space-y-8">
          {/* Invite Banner */}
          {inviteCode && inviteValid === true && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
              <Gift className="h-6 w-6 text-green-600 mt-0.5" />
              <div>
                <p className="font-semibold text-green-800">You&apos;re Invited!</p>
                <p className="text-sm text-green-700">
                  {inviteNote || 'Create your account to start ordering from Tile Station.'}
                </p>
              </div>
            </div>
          )}

          {inviteCode && inviteValid === false && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="font-semibold text-red-800">Invalid Invite Link</p>
              <p className="text-sm text-red-700">
                This invite link is invalid or has expired. Please contact the sender for a new link.
              </p>
            </div>
          )}

          <div className="text-center">
            <h2 className="text-3xl font-heading font-bold tracking-tightest mb-2">
              {isLogin ? 'Welcome Back' : (inviteCode ? 'Complete Your Registration' : 'Create Account')}
            </h2>
            <p className="text-muted-foreground">
              {isLogin ? 'Sign in to your account' : 'Sign up to get started'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="name" data-testid="name-label">Full Name</Label>
                  <Input
                    id="name"
                    data-testid="name-input"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required={!isLogin}
                    placeholder="John Doe"
                    className="h-11"
                  />
                </div>

                {/* Company Details */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="companyName">Company Name</Label>
                    <Input
                      id="companyName"
                      data-testid="company-name-input"
                      type="text"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="ABC Ltd"
                      className="h-11"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="companyRegNumber">Company Registration No.</Label>
                    <Input
                      id="companyRegNumber"
                      data-testid="company-reg-input"
                      type="text"
                      value={companyRegNumber}
                      onChange={(e) => setCompanyRegNumber(e.target.value)}
                      placeholder="12345678"
                      className="h-11"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="vatNumber">VAT Number</Label>
                  <Input
                    id="vatNumber"
                    data-testid="vat-number-input"
                    type="text"
                    value={vatNumber}
                    onChange={(e) => setVatNumber(e.target.value)}
                    placeholder="GB123456789"
                    className="h-11"
                  />
                </div>

                {/* Address Details */}
                <div className="space-y-2">
                  <Label htmlFor="addressLine1">Address Line 1</Label>
                  <Input
                    id="addressLine1"
                    data-testid="address-line1-input"
                    type="text"
                    value={addressLine1}
                    onChange={(e) => setAddressLine1(e.target.value)}
                    required={!isLogin}
                    placeholder="123 High Street"
                    className="h-11"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="addressLine2">Address Line 2</Label>
                  <Input
                    id="addressLine2"
                    data-testid="address-line2-input"
                    type="text"
                    value={addressLine2}
                    onChange={(e) => setAddressLine2(e.target.value)}
                    placeholder="Suite 100"
                    className="h-11"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="city">City</Label>
                    <Input
                      id="city"
                      data-testid="city-input"
                      type="text"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      required={!isLogin}
                      placeholder="London"
                      className="h-11"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="postcode">Postcode</Label>
                    <Input
                      id="postcode"
                      data-testid="postcode-input"
                      type="text"
                      value={postcode}
                      onChange={(e) => setPostcode(e.target.value)}
                      required={!isLogin}
                      placeholder="SW1A 1AA"
                      className="h-11"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Input
                    id="country"
                    data-testid="country-input"
                    type="text"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    required={!isLogin}
                    placeholder="United Kingdom"
                    className="h-11"
                  />
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="email" data-testid="email-label">Email</Label>
              <Input
                id="email"
                data-testid="email-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="h-11"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" data-testid="password-label">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  data-testid="password-input"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="h-11 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {isLogin && (
                <a 
                  href="/forgot-password" 
                  className="text-xs text-muted-foreground hover:text-primary hover:underline float-right"
                  data-testid="forgot-password-link"
                >
                  Forgot password?
                </a>
              )}
            </div>

            {!isLogin && !inviteCode && (
              <div className="space-y-2">
                <Label htmlFor="role" data-testid="role-label">Role</Label>
                <select
                  id="role"
                  data-testid="role-select"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="flex h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="customer">Customer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            )}

            {/* Show invite code badge when registering with invite */}
            {!isLogin && inviteCode && inviteValid && (
              <div className="flex items-center gap-2 p-3 bg-accent/10 rounded-lg">
                <CheckCircle className="h-5 w-5 text-accent" />
                <div>
                  <p className="text-sm font-medium">Invite Code Applied</p>
                  <p className="text-xs text-muted-foreground font-mono">{inviteCode}</p>
                </div>
              </div>
            )}

            <Button
              type="submit"
              data-testid="submit-button"
              className="w-full h-11 bg-primary hover:bg-primary/90 font-medium"
              disabled={loading || (inviteCode && inviteValid === false)}
            >
              {loading ? (
                'Processing...'
              ) : isLogin ? (
                <><LogIn className="mr-2 h-4 w-4" /> Sign In</>
              ) : (
                <><UserPlus className="mr-2 h-4 w-4" /> {inviteCode ? 'Create Account' : 'Sign Up'}</>
              )}
            </Button>
          </form>

          <div className="text-center">
            <button
              type="button"
              data-testid="toggle-auth-mode"
              onClick={() => setIsLogin(!isLogin)}
              className="text-sm text-muted-foreground hover:text-accent hover:underline"
            >
              {isLogin ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
