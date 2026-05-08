import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { UserPlus, Plus, Trash2, Copy, Check, Link2, Building2, Shield, Clock, Mail, Send } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card } from '../../components/ui/card';
import { Checkbox } from '../../components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

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

const AVAILABLE_PERMISSIONS = Object.keys(PERMISSION_LABELS);

export const StaffInvites = () => {
  const [invites, setInvites] = useState([]);
  const [showrooms, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [showLinkDialog, setShowLinkDialog] = useState(false);
  const [showEmailDialog, setShowEmailDialog] = useState(false);
  const [selectedInviteForEmail, setSelectedInviteForEmail] = useState(null);
  const [emailData, setEmailData] = useState({ recipient_email: '', recipient_name: '' });
  const [sendingEmail, setSendingEmail] = useState(false);
  const [generatedLink, setGeneratedLink] = useState('');
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);
  
  const [formData, setFormData] = useState({
    role: 'staff',
    showroom_id: '',
    permissions: [],
    note: '',
    expires_days: 7
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [invitesRes, showroomsRes] = await Promise.all([
        api.getStaffInvites(),
        api.getStores()
      ]);
      setInvites(invitesRes.data);
      setStores(showroomsRes.data);
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error('Super Admin access required');
      } else {
        toast.error('Failed to load invites');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDialog = () => {
    setFormData({
      role: 'staff',
      showroom_id: '',
      permissions: ['epos'], // Default permission
      note: '',
      expires_days: 7
    });
    setShowDialog(true);
  };

  const handlePermissionToggle = (permission) => {
    setFormData(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter(p => p !== permission)
        : [...prev.permissions, permission]
    }));
  };

  const handleSelectAllPermissions = () => {
    if (formData.permissions.length === AVAILABLE_PERMISSIONS.length) {
      setFormData(prev => ({ ...prev, permissions: [] }));
    } else {
      setFormData(prev => ({ ...prev, permissions: [...AVAILABLE_PERMISSIONS] }));
    }
  };

  const handleCreateInvite = async (e) => {
    e.preventDefault();
    
    if (formData.permissions.length === 0) {
      toast.error('Please select at least one permission');
      return;
    }

    setSaving(true);
    try {
      const result = await api.createStaffInvite({
        role: formData.role,
        showroom_id: formData.showroom_id || null,
        permissions: formData.permissions,
        note: formData.note || null,
        expires_days: formData.expires_days
      });
      
      // Generate the invite link
      const baseUrl = window.location.origin;
      const inviteLink = `${baseUrl}/staff-register/${result.data.code}`;
      
      setGeneratedLink(inviteLink);
      setShowDialog(false);
      setShowLinkDialog(true);
      fetchData();
      
      toast.success('Invite created successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create invite');
    } finally {
      setSaving(false);
    }
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(generatedLink);
      setCopied(true);
      toast.success('Link copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast.error('Failed to copy link');
    }
  };

  const handleDeleteInvite = async (id) => {
    if (!window.confirm('Are you sure you want to delete this invite?')) return;
    
    try {
      await api.deleteStaffInvite(id);
      toast.success('Invite deleted');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete invite');
    }
  };

  const handleOpenEmailDialog = (invite) => {
    setSelectedInviteForEmail(invite);
    setEmailData({
      recipient_email: invite.email_sent_to || '',
      recipient_name: ''
    });
    setShowEmailDialog(true);
  };

  const handleSendEmail = async (e) => {
    e.preventDefault();
    if (!emailData.recipient_email) {
      toast.error('Please enter recipient email');
      return;
    }
    
    setSendingEmail(true);
    try {
      await api.sendStaffInviteEmail({
        invite_id: selectedInviteForEmail.id,
        recipient_email: emailData.recipient_email,
        recipient_name: emailData.recipient_name || null
      });
      toast.success(`Invite email sent to ${emailData.recipient_email}`);
      setShowEmailDialog(false);
      setEmailData({ recipient_email: '', recipient_name: '' });
      fetchData(); // Refresh to show email_sent_to info
    } catch (error) {
      if (error.response?.data?.detail) {
        toast.error(error.response.data.detail);
      } else {
        toast.error('Failed to send invite email');
      }
    } finally {
      setSendingEmail(false);
    }
  };

  const getRoleBadge = (role) => {
    const badges = {
      admin: <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">Admin</span>,
      manager: <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">Manager</span>,
      staff: <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">Staff</span>
    };
    return badges[role] || <span className="px-2 py-1 text-xs rounded-full bg-gray-100">{role}</span>;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  };

  const isExpired = (expiresAt) => {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading invites...</div>;
  }

  return (
    <div className="space-y-6" data-testid="staff-invites-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Staff Invites</h1>
          <p className="text-muted-foreground">Create invite links for staff and admin users</p>
        </div>
        <Button onClick={handleOpenDialog} data-testid="create-invite-btn">
          <Plus className="h-4 w-4 mr-2" />
          Create Invite Link
        </Button>
      </div>

      {/* Invites Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold">Role</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Store</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Email Sent To</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Permissions</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Status</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Created</th>
                <th className="px-4 py-3 text-left text-sm font-semibold">Expires</th>
                <th className="px-4 py-3 text-center text-sm font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {invites.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                    <UserPlus className="h-12 w-12 mx-auto mb-3 opacity-30" />
                    <p>No invite links created yet</p>
                    <p className="text-sm">Create an invite link to onboard staff members</p>
                  </td>
                </tr>
              ) : (
                invites.map((invite) => (
                  <tr key={invite.id} className={invite.used ? 'bg-gray-50' : ''}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-muted-foreground" />
                        {getRoleBadge(invite.role)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {invite.showroom_name ? (
                        <div className="flex items-center gap-2 text-sm">
                          <Building2 className="h-4 w-4 text-muted-foreground" />
                          <span>{invite.showroom_name}</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm italic">All Stores</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {invite.email_sent_to ? (
                        <div className="flex items-center gap-2 text-sm">
                          <Mail className="h-4 w-4 text-green-600" />
                          <div>
                            <p className="font-medium text-green-700">{invite.email_sent_to}</p>
                            {invite.email_sent_at && (
                              <p className="text-xs text-muted-foreground">
                                Sent {formatDate(invite.email_sent_at)}
                              </p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm italic flex items-center gap-1">
                          <Mail className="h-4 w-4 opacity-30" />
                          Not sent
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {invite.permissions?.slice(0, 3).map(p => (
                          <span key={p} className="px-2 py-0.5 text-xs bg-gray-100 rounded">
                            {PERMISSION_LABELS[p] || p}
                          </span>
                        ))}
                        {invite.permissions?.length > 3 && (
                          <span className="px-2 py-0.5 text-xs bg-gray-100 rounded">
                            +{invite.permissions.length - 3} more
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {invite.used ? (
                        <div>
                          <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
                            Used
                          </span>
                          <p className="text-xs text-muted-foreground mt-1">by {invite.used_by}</p>
                        </div>
                      ) : isExpired(invite.expires_at) ? (
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800">
                          Expired
                        </span>
                      ) : (
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-amber-100 text-amber-800">
                          Pending
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {formatDate(invite.created_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {formatDate(invite.expires_at)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex justify-center gap-1">
                        {!invite.used && !isExpired(invite.expires_at) && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenEmailDialog(invite)}
                              title={invite.email_sent_to ? `Resend to ${invite.email_sent_to}` : "Send invite via email"}
                              className={invite.email_sent_to ? "text-green-600 hover:text-green-700 hover:bg-green-50" : "text-blue-600 hover:text-blue-700 hover:bg-blue-50"}
                              data-testid={`email-invite-${invite.id}`}
                            >
                              <Send className="h-4 w-4 mr-1" />
                              <span className="text-xs">{invite.email_sent_to ? 'Resend' : 'Send'}</span>
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                const link = `${window.location.origin}/staff-register/${invite.code}`;
                                navigator.clipboard.writeText(link);
                                toast.success('Link copied!');
                              }}
                              title="Copy invite link"
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-500 hover:text-red-600 hover:bg-red-50"
                          onClick={() => handleDeleteInvite(invite.id)}
                          title="Delete invite"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Create Invite Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="h-5 w-5" />
              Create Staff Invite Link
            </DialogTitle>
            <DialogDescription>
              Generate an invite link to send to a new staff or admin member.
            </DialogDescription>
          </DialogHeader>
          
          <form onSubmit={handleCreateInvite} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-1 block">Role <span className="text-red-500">*</span></label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full h-10 px-3 border rounded-md"
                  data-testid="invite-role-select"
                >
                  <option value="staff">Staff</option>
                  <option value="manager">Manager</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              
              <div>
                <label className="text-sm font-medium mb-1 block">Store</label>
                <select
                  value={formData.showroom_id}
                  onChange={(e) => setFormData({ ...formData, showroom_id: e.target.value })}
                  className="w-full h-10 px-3 border rounded-md"
                  data-testid="invite-showroom-select"
                >
                  <option value="">All Stores</option>
                  {showrooms.map(showroom => (
                    <option key={showroom.id} value={showroom.id}>{showroom.name}</option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground mt-1">Assign to a specific showroom location</p>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-1 block">Link Expires In</label>
                <select
                  value={formData.expires_days}
                  onChange={(e) => setFormData({ ...formData, expires_days: parseInt(e.target.value) })}
                  className="w-full h-10 px-3 border rounded-md"
                >
                  <option value={1}>1 Day</option>
                  <option value={3}>3 Days</option>
                  <option value={7}>7 Days</option>
                  <option value={14}>14 Days</option>
                  <option value={30}>30 Days</option>
                </select>
              </div>
              
              <div>
                <label className="text-sm font-medium mb-1 block">Note (Optional)</label>
                <Input
                  value={formData.note}
                  onChange={(e) => setFormData({ ...formData, note: e.target.value })}
                  placeholder="e.g., New Tonbridge manager"
                />
              </div>
            </div>
            
            {/* Permissions Section */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium">Permissions <span className="text-red-500">*</span></label>
                <Button 
                  type="button" 
                  variant="outline" 
                  size="sm"
                  onClick={handleSelectAllPermissions}
                >
                  {formData.permissions.length === AVAILABLE_PERMISSIONS.length ? 'Deselect All' : 'Select All'}
                </Button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 p-4 border rounded-lg bg-muted/30">
                {AVAILABLE_PERMISSIONS.map(permission => (
                  <div key={permission} className="flex items-center space-x-2">
                    <Checkbox
                      id={`invite-${permission}`}
                      checked={formData.permissions.includes(permission)}
                      onCheckedChange={() => handlePermissionToggle(permission)}
                    />
                    <label 
                      htmlFor={`invite-${permission}`} 
                      className="text-sm cursor-pointer select-none"
                    >
                      {PERMISSION_LABELS[permission]}
                    </label>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Select the pages and features the invited user will have access to
              </p>
            </div>
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={saving} data-testid="generate-invite-btn">
                {saving ? 'Generating...' : 'Generate Invite Link'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Generated Link Dialog */}
      <Dialog open={showLinkDialog} onOpenChange={setShowLinkDialog}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-green-600">
              <Check className="h-5 w-5" />
              Invite Link Created!
            </DialogTitle>
            <DialogDescription>
              Share this link with the new team member. They&apos;ll be able to create their account with the role and permissions you specified.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="flex items-center gap-2">
              <Input
                value={generatedLink}
                readOnly
                className="font-mono text-sm"
              />
              <Button onClick={handleCopyLink} variant={copied ? "default" : "outline"}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
              <p className="font-medium flex items-center gap-2">
                <Mail className="h-4 w-4" />
                Send this link via email, WhatsApp, or any messenger
              </p>
              <p className="mt-1 text-blue-600">
                The recipient will create their own password when registering.
              </p>
            </div>
          </div>
          
          <DialogFooter>
            <Button onClick={() => setShowLinkDialog(false)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Send Email Dialog */}
      <Dialog open={showEmailDialog} onOpenChange={setShowEmailDialog}>
        <DialogContent className="max-w-md" data-testid="send-email-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-blue-700">
              <Send className="h-5 w-5" />
              {selectedInviteForEmail?.email_sent_to ? 'Resend Invite Email' : 'Send Invite Email'}
            </DialogTitle>
            <DialogDescription>
              {selectedInviteForEmail?.email_sent_to 
                ? 'Resend the invite link to the same or different email address.'
                : 'Send the invite link directly to the recipient\'s email address.'}
            </DialogDescription>
          </DialogHeader>
          
          {selectedInviteForEmail && (
            <form onSubmit={handleSendEmail} className="space-y-4">
              {/* Invite Details */}
              <div className="bg-gray-50 rounded-lg p-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Role:</span>
                  <span className="font-medium capitalize">{selectedInviteForEmail.role}</span>
                </div>
                {selectedInviteForEmail.showroom_name && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Store:</span>
                    <span className="font-medium">{selectedInviteForEmail.showroom_name}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Expires:</span>
                  <span className="font-medium">{formatDate(selectedInviteForEmail.expires_at)}</span>
                </div>
                {selectedInviteForEmail.email_sent_to && (
                  <div className="flex justify-between text-green-600 bg-green-50 -mx-3 px-3 py-2 rounded">
                    <span>Previously sent to:</span>
                    <span className="font-medium">{selectedInviteForEmail.email_sent_to}</span>
                  </div>
                )}
              </div>
              
              <div>
                <label className="text-sm font-medium mb-1 block">
                  Recipient Email <span className="text-red-500">*</span>
                </label>
                <Input
                  type="email"
                  value={emailData.recipient_email}
                  onChange={(e) => setEmailData({ ...emailData, recipient_email: e.target.value })}
                  placeholder="email@example.com"
                  required
                  data-testid="email-recipient-input"
                />
                {selectedInviteForEmail.email_sent_to && emailData.recipient_email !== selectedInviteForEmail.email_sent_to && emailData.recipient_email && (
                  <p className="text-xs text-amber-600 mt-1">
                    ⚠️ Sending to a different email than before
                  </p>
                )}
              </div>
              
              <div>
                <label className="text-sm font-medium mb-1 block">Recipient Name (optional)</label>
                <Input
                  type="text"
                  value={emailData.recipient_name}
                  onChange={(e) => setEmailData({ ...emailData, recipient_name: e.target.value })}
                  placeholder="John Smith"
                  data-testid="email-name-input"
                />
              </div>
              
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
                <strong>Note:</strong> Email delivery requires Resend to be configured. 
                In sandbox mode, emails can only be sent to verified addresses.
              </div>
              
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setShowEmailDialog(false)}>
                  Cancel
                </Button>
                <Button 
                  type="submit" 
                  disabled={sendingEmail}
                  className={selectedInviteForEmail.email_sent_to ? "bg-green-600 hover:bg-green-700" : "bg-blue-600 hover:bg-blue-700"}
                  data-testid="send-email-btn"
                >
                  {sendingEmail ? (
                    <>Sending...</>
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-2" />
                      {selectedInviteForEmail.email_sent_to ? 'Resend Email' : 'Send Email'}
                    </>
                  )}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default StaffInvites;
