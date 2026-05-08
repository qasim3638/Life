import React from 'react';
import { Lock, User } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';

/**
 * Shared Staff PIN Verification Dialog
 */
export const StaffPinDialog = ({
  open,
  onOpenChange,
  staffPin,
  onPinChange,
  verifiedStaff,
  verifyingPin,
  onVerify,
  title = 'Staff PIN Required',
  description = 'Enter your confidential PIN to save this document. Your name will be recorded as the sales person.'
}) => {
  const handlePinChange = (e) => {
    // Only allow digits, max 6 characters
    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
    onPinChange(value);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && staffPin.length >= 4) {
      onVerify();
    }
  };

  // Clear PIN when dialog opens or closes
  const handleOpenChange = (isOpen) => {
    if (!isOpen) {
      onPinChange(''); // Clear PIN when closing
    }
    onOpenChange(isOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-primary" />
            {title}
          </DialogTitle>
          <DialogDescription>
            {description}
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4 py-4">
          <div>
            <label className="text-sm font-medium">Enter PIN</label>
            <Input
              type="password"
              value={staffPin}
              onChange={handlePinChange}
              onKeyPress={handleKeyPress}
              placeholder="Enter 4-6 digit PIN"
              maxLength={6}
              className="text-center text-2xl tracking-widest"
              autoFocus
              autoComplete="off"
              data-testid="staff-pin-input"
            />
          </div>
          
          {verifiedStaff && (
            <div className="flex items-center gap-2 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-700">
              <User className="h-4 w-4" />
              Verified: {verifiedStaff.name || verifiedStaff.staff_name}
            </div>
          )}
        </div>
        
        <DialogFooter>
          <Button 
            variant="outline" 
            onClick={() => {
              onPinChange('');
              onOpenChange(false);
            }}
          >
            Cancel
          </Button>
          <Button 
            onClick={onVerify} 
            disabled={verifyingPin || staffPin.length < 4}
            data-testid="verify-pin-btn"
          >
            {verifyingPin ? 'Verifying...' : 'Verify & Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default StaffPinDialog;
