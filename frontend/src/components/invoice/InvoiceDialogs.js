import React from 'react';
import { Lock } from 'lucide-react';
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

export const InvoiceDialogs = ({
  // Store PIN Dialog
  showStorePinDialog,
  setShowStorePinDialog,
  showroomPin,
  setStorePin,
  handleStorePinVerify,
  // Staff PIN Dialog
  showPinDialog,
  setShowPinDialog,
  staffPin,
  setStaffPin,
  verifyingPin,
  handlePinVerify,
  verifiedStaff,
  // Unsaved Changes Dialog
  showUnsavedDialog,
  setShowUnsavedDialog,
  confirmDiscardChanges,
  cancelDiscard,
  invoiceData,
  totals,
  // Discount Auth Dialog
  showDiscountAuthDialog,
  setShowDiscountAuthDialog,
  discountAuthPin,
  setDiscountAuthPin,
  pendingDiscountLineIndex,
  pendingDiscountValue,
  verifyingDiscountAuth,
  handleDiscountAuthorization,
  setPendingDiscountLineIndex,
  setPendingDiscountValue
}) => {
  return (
    <>
      {/* Store PIN Dialog */}
      <Dialog open={showStorePinDialog} onOpenChange={setShowStorePinDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" />
              Change Store
            </DialogTitle>
            <DialogDescription>
              This showroom is locked for today. Enter your staff PIN to change it.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              type="password"
              placeholder="Enter staff PIN"
              value={showroomPin}
              onChange={(e) => setStorePin(e.target.value)}
              maxLength={6}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowStorePinDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleStorePinVerify}>
              Verify & Change
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Staff PIN Verification Dialog */}
      <Dialog open={showPinDialog} onOpenChange={setShowPinDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" />
              Staff Verification Required
            </DialogTitle>
            <DialogDescription>
              Enter your staff PIN to save this invoice. This ensures accountability for all transactions.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {verifiedStaff ? (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                <p className="text-green-700 font-medium">✓ Verified as {verifiedStaff.staff_name}</p>
                <p className="text-sm text-green-600 mt-1">Click &ldquo;Save Invoice&rdquo; to complete</p>
              </div>
            ) : (
              <div>
                <label className="text-sm font-medium">Staff PIN</label>
                <Input
                  type="password"
                  placeholder="Enter your PIN"
                  value={staffPin}
                  onChange={(e) => setStaffPin(e.target.value)}
                  className="mt-2"
                  maxLength={6}
                  data-testid="staff-pin-input"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowPinDialog(false);
              setStaffPin('');
            }}>
              Cancel
            </Button>
            {verifiedStaff ? (
              <Button onClick={handlePinVerify} className="bg-green-600 hover:bg-green-700">
                Save Invoice
              </Button>
            ) : (
              <Button onClick={handlePinVerify} disabled={verifyingPin || !staffPin}>
                {verifyingPin ? 'Verifying...' : 'Verify PIN'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Unsaved Changes Dialog */}
      <Dialog open={showUnsavedDialog} onOpenChange={setShowUnsavedDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-amber-600">Unsaved Changes</DialogTitle>
            <DialogDescription>
              You have unsaved changes on this invoice. What would you like to do?
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <p className="text-sm text-amber-800 font-medium mb-2">Current Invoice Summary:</p>
              <ul className="text-sm text-amber-700 space-y-1">
                {invoiceData.invoiceNo && <li>• Invoice: {invoiceData.invoiceNo}</li>}
                {invoiceData.lineItems.filter(i => i.product).length > 0 && (
                  <li>• Items: {invoiceData.lineItems.filter(i => i.product).length} product(s)</li>
                )}
                {totals.grossTotal > 0 && <li>• Total: £{totals.grossTotal.toFixed(2)}</li>}
              </ul>
            </div>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={cancelDiscard}>
              Keep Editing
            </Button>
            <Button variant="destructive" onClick={confirmDiscardChanges}>
              Discard Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Discount Authorization Dialog */}
      <Dialog open={showDiscountAuthDialog} onOpenChange={(open) => {
        if (!open) {
          setShowDiscountAuthDialog(false);
          setDiscountAuthPin('');
          setPendingDiscountLineIndex(null);
          setPendingDiscountValue(null);
        }
      }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600">
              <Lock className="h-5 w-5" />
              Authorization Required
            </DialogTitle>
            <DialogDescription>
              The discount you&apos;re trying to apply exceeds the maximum allowed.
              A manager or admin must authorize this discount.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
              <div className="text-sm text-amber-800">
                <p className="font-medium">Discount Details:</p>
                {pendingDiscountLineIndex !== null && invoiceData.lineItems[pendingDiscountLineIndex] && (
                  <>
                    <p>• Product: {invoiceData.lineItems[pendingDiscountLineIndex]?.product}</p>
                    <p>• Original Price: £{parseFloat(invoiceData.lineItems[pendingDiscountLineIndex]?.price || 0).toFixed(2)}</p>
                    <p>• Requested Price: £{parseFloat(pendingDiscountValue || 0).toFixed(2)}</p>
                    <p>• Max Allowed: {invoiceData.lineItems[pendingDiscountLineIndex]?.max_discount}% off</p>
                  </>
                )}
              </div>
            </div>
            <label className="text-sm font-medium">Manager/Admin PIN</label>
            <Input
              type="password"
              placeholder="Enter authorization PIN"
              value={discountAuthPin}
              onChange={(e) => setDiscountAuthPin(e.target.value)}
              className="mt-2"
              data-testid="discount-auth-pin-input"
              maxLength={6}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowDiscountAuthDialog(false);
              setDiscountAuthPin('');
              setPendingDiscountLineIndex(null);
              setPendingDiscountValue(null);
            }}>
              Cancel
            </Button>
            <Button 
              onClick={handleDiscountAuthorization}
              disabled={verifyingDiscountAuth || !discountAuthPin}
              className="bg-amber-600 hover:bg-amber-700"
            >
              {verifyingDiscountAuth ? 'Verifying...' : 'Authorize Discount'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
