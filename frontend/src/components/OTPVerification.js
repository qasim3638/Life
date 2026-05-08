import React, { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card } from './ui/card';
import { Shield, Clock, Phone, MessageSquare } from 'lucide-react';

export const OTPVerification = ({ 
  onRequestOTP,
  onVerify, 
  onCancel, 
  loading = false, 
  expiresInMinutes = 5,
  smsSent = false,
  initialPhoneNumber = ''
}) => {
  const [step, setStep] = useState(smsSent ? 'verify' : 'phone');
  const [phoneNumber, setPhoneNumber] = useState(initialPhoneNumber);
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');

  const handlePhoneSubmit = async (e) => {
    e.preventDefault();
    
    // Basic validation for international format
    if (!phoneNumber.startsWith('+')) {
      setError('Please enter phone number in international format (e.g., +44XXXXXXXXXX)');
      return;
    }
    if (phoneNumber.length < 10) {
      setError('Please enter a valid phone number');
      return;
    }
    
    setError('');
    const result = await onRequestOTP(phoneNumber);
    if (result && result.success) {
      setStep('verify');
    }
  };

  const handleOtpSubmit = (e) => {
    e.preventDefault();
    if (otp.length !== 6) {
      setError('Please enter a 6-digit OTP');
      return;
    }
    setError('');
    onVerify(otp, phoneNumber);
  };

  const handleOtpChange = (e) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
    setOtp(value);
    setError('');
  };

  const handlePhoneChange = (e) => {
    let value = e.target.value;
    // Allow + at the start and digits only
    if (value && !value.startsWith('+')) {
      value = '+' + value.replace(/[^\d]/g, '');
    } else {
      value = '+' + value.slice(1).replace(/[^\d]/g, '');
    }
    setPhoneNumber(value);
    setError('');
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="p-6 w-full max-w-md">
        {step === 'phone' ? (
          <>
            <div className="text-center mb-6">
              <div className="mx-auto w-12 h-12 bg-accent/10 rounded-full flex items-center justify-center mb-4">
                <Phone className="h-6 w-6 text-accent" />
              </div>
              <h2 className="text-xl font-heading font-bold tracking-tightest mb-2">
                Verify Your Order
              </h2>
              <p className="text-sm text-muted-foreground">
                Enter your phone number to receive a verification code via SMS
              </p>
            </div>

            <form onSubmit={handlePhoneSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Phone Number</label>
                <Input
                  type="tel"
                  placeholder="+44 7XXX XXXXXX"
                  value={phoneNumber}
                  onChange={handlePhoneChange}
                  className="text-lg"
                  autoFocus
                  data-testid="phone-input"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Include country code (e.g., +44 for UK, +1 for US)
                </p>
                {error && (
                  <p className="text-sm text-red-600 mt-1" data-testid="phone-error">
                    {error}
                  </p>
                )}
              </div>

              <div className="flex gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={onCancel}
                  className="flex-1"
                  disabled={loading}
                  data-testid="cancel-phone-button"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="flex-1 bg-accent hover:bg-accent/90"
                  disabled={loading || phoneNumber.length < 10}
                  data-testid="send-otp-button"
                >
                  {loading ? 'Sending...' : 'Send OTP'}
                </Button>
              </div>
            </form>
          </>
        ) : (
          <>
            <div className="text-center mb-6">
              <div className="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
                <MessageSquare className="h-6 w-6 text-green-600" />
              </div>
              <h2 className="text-xl font-heading font-bold tracking-tightest mb-2">
                Enter Verification Code
              </h2>
              <p className="text-sm text-muted-foreground">
                We&apos;ve sent a 6-digit code to <strong>{phoneNumber}</strong>
              </p>
            </div>

            <form onSubmit={handleOtpSubmit} className="space-y-4">
              <div>
                <Input
                  type="text"
                  placeholder="Enter 6-digit OTP"
                  value={otp}
                  onChange={handleOtpChange}
                  className="text-center text-2xl font-mono tracking-[0.5em]"
                  maxLength={6}
                  autoFocus
                  data-testid="otp-input"
                />
                {error && (
                  <p className="text-sm text-red-600 mt-1 text-center" data-testid="otp-error">
                    {error}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                <span>Code expires in {expiresInMinutes} minutes</span>
              </div>

              <div className="flex gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={onCancel}
                  className="flex-1"
                  disabled={loading}
                  data-testid="cancel-otp-button"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="flex-1 bg-accent hover:bg-accent/90"
                  disabled={loading || otp.length !== 6}
                  data-testid="verify-otp-button"
                >
                  {loading ? 'Verifying...' : 'Verify & Place Order'}
                </Button>
              </div>

              <button
                type="button"
                onClick={() => setStep('phone')}
                className="w-full text-sm text-muted-foreground hover:text-foreground"
                data-testid="change-phone-button"
              >
                Use different phone number
              </button>
            </form>
          </>
        )}
      </Card>
    </div>
  );
};
