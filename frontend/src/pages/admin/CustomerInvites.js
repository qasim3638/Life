import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { UserPlus, Link2, Copy, Check, Trash2, Clock, CheckCircle, XCircle, Send, Mail } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../components/ui/dialog';

const FRONTEND_URL = window.location.origin;

export const CustomerInvites = () => {
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [open, setOpen] = useState(false);
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [formData, setFormData] = useState({
    note: '',
    expires_in_days: 30
  });
  const [emailFormData, setEmailFormData] = useState({
    recipient_email: '',
    recipient_name: '',
    note: '',
    expires_in_days: 30
  });

  useEffect(() => {
    fetchInvites();
  }, []);

  const fetchInvites = async () => {
    try {
      const response = await api.getInvites();
      setInvites(response.data);
    } catch (error) {
      toast.error('Failed to load invites');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    
    try {
      const response = await api.createInvite({
        note: formData.note || null,
        expires_in_days: parseInt(formData.expires_in_days) || 30
      });
      
      toast.success('Invite link created!');
      setOpen(false);
      setFormData({ note: '', expires_in_days: 30 });
      fetchInvites();
      
      // Auto-copy the new invite link
      const link = `${FRONTEND_URL}/register?invite=${response.data.code}`;
      navigator.clipboard.writeText(link);
      toast.success('Link copied to clipboard!');
      
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create invite');
    } finally {
      setCreating(false);
    }
  };

  const copyLink = (code) => {
    const link = `${FRONTEND_URL}/register?invite=${code}`;
    navigator.clipboard.writeText(link);
    setCopiedId(code);
    toast.success('Link copied to clipboard!');
    setTimeout(() => setCopiedId(null), 2000);
  };

  const shareViaWhatsApp = (code, note) => {
    const link = `${FRONTEND_URL}/register?invite=${code}`;
    const message = `You're invited to join Tile Station! ${note ? `\n\n${note}\n\n` : '\n\n'}Click here to create your account:\n${link}`;
    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
  };

  const deleteInvite = async (id) => {
    if (!window.confirm('Are you sure you want to delete this invite?')) return;
    
    try {
      await api.deleteInvite(id);
      toast.success('Invite deleted');
      fetchInvites();
    } catch (error) {
      toast.error('Failed to delete invite');
    }
  };

  const handleSendEmail = async (e) => {
    e.preventDefault();
    
    if (!emailFormData.recipient_email) {
      toast.error('Please enter an email address');
      return;
    }
    
    setSendingEmail(true);
    
    try {
      const response = await api.sendInviteEmail({
        recipient_email: emailFormData.recipient_email,
        recipient_name: emailFormData.recipient_name || null,
        note: emailFormData.note || null,
        expires_in_days: parseInt(emailFormData.expires_in_days) || 30
      });
      
      if (response.data.status === 'success') {
        toast.success(`Invite sent to ${emailFormData.recipient_email}!`);
      } else {
        toast.warning(response.data.message);
      }
      
      setEmailDialogOpen(false);
      setEmailFormData({ recipient_email: '', recipient_name: '', note: '', expires_in_days: 30 });
      fetchInvites();
      
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to send invite email');
    } finally {
      setSendingEmail(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  const isExpired = (expiresAt) => {
    if (!expiresAt) return false;
    return new Date() > new Date(expiresAt);
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  const activeInvites = invites.filter(i => !i.used && !isExpired(i.expires_at));
  const usedInvites = invites.filter(i => i.used);

  return (
    <div className="space-y-6" data-testid="customer-invites-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Customer Invites</h1>
          <p className="text-muted-foreground">Generate and share registration links with potential customers</p>
        </div>
        
        <div className="flex gap-2">
          {/* Send via Email Dialog */}
          <Dialog open={emailDialogOpen} onOpenChange={setEmailDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="border-blue-200 text-blue-700 hover:bg-blue-50" data-testid="send-email-invite-btn">
                <Mail className="h-4 w-4 mr-2" />
                Send via Email
              </Button>
            </DialogTrigger>
            <DialogContent data-testid="send-email-dialog">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Mail className="h-5 w-5 text-blue-600" />
                  Send Invite via Email
                </DialogTitle>
              </DialogHeader>
              
              <form onSubmit={handleSendEmail} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email Address *</Label>
                  <Input
                    id="email"
                    type="email"
                    data-testid="invite-email-input"
                    value={emailFormData.recipient_email}
                    onChange={(e) => setEmailFormData({ ...emailFormData, recipient_email: e.target.value })}
                    placeholder="customer@example.com"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="name">Customer Name (optional)</Label>
                  <Input
                    id="name"
                    data-testid="invite-name-input"
                    value={emailFormData.recipient_name}
                    onChange={(e) => setEmailFormData({ ...emailFormData, recipient_name: e.target.value })}
                    placeholder="John Smith"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="emailNote">Personal Note (optional)</Label>
                  <Input
                    id="emailNote"
                    data-testid="invite-email-note-input"
                    value={emailFormData.note}
                    onChange={(e) => setEmailFormData({ ...emailFormData, note: e.target.value })}
                    placeholder="Welcome to Tile Station!"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="emailExpires">Expires in (days)</Label>
                  <Input
                    id="emailExpires"
                    data-testid="invite-email-expires-input"
                    type="number"
                    min="1"
                    max="365"
                    value={emailFormData.expires_in_days}
                    onChange={(e) => setEmailFormData({ ...emailFormData, expires_in_days: e.target.value })}
                  />
                </div>

                <Button 
                  type="submit" 
                  className="w-full bg-blue-600 hover:bg-blue-700"
                  disabled={sendingEmail}
                  data-testid="submit-email-invite-btn"
                >
                  {sendingEmail ? (
                    <>Sending...</>
                  ) : (
                    <><Mail className="h-4 w-4 mr-2" /> Send Invite Email</>
                  )}
                </Button>
              </form>
            </DialogContent>
          </Dialog>

          {/* Create Link Dialog */}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-accent hover:bg-accent/90" data-testid="create-invite-btn">
                <UserPlus className="h-4 w-4 mr-2" />
                Create Invite Link
              </Button>
            </DialogTrigger>
            <DialogContent data-testid="create-invite-dialog">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Link2 className="h-5 w-5" />
                  Create Invite Link
                </DialogTitle>
              </DialogHeader>
              
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="note">Name (optional)</Label>
                  <Input
                    id="note"
                    data-testid="invite-note-input"
                    value={formData.note}
                    onChange={(e) => setFormData({ ...formData, note: e.target.value })}
                    placeholder="Customer name"
                  />
                  <p className="text-xs text-muted-foreground">
                    Add a name to remember who this invite is for
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="expires">Expires in (days)</Label>
                  <Input
                    id="expires"
                    data-testid="invite-expires-input"
                    type="number"
                    min="1"
                    max="365"
                    value={formData.expires_in_days}
                    onChange={(e) => setFormData({ ...formData, expires_in_days: e.target.value })}
                  />
                </div>

                <Button 
                  type="submit" 
                  className="w-full bg-accent hover:bg-accent/90"
                  disabled={creating}
                  data-testid="submit-invite-btn"
                >
                  {creating ? 'Creating...' : 'Create & Copy Link'}
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 text-center">
          <p className="text-3xl font-bold text-accent">{activeInvites.length}</p>
          <p className="text-sm text-muted-foreground">Active Invites</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-3xl font-bold text-green-600">{usedInvites.length}</p>
          <p className="text-sm text-muted-foreground">Customers Joined</p>
        </Card>
      </div>

      {/* Active Invites */}
      <Card className="p-6">
        <h2 className="text-xl font-heading font-bold tracking-tightest mb-4">Active Invite Links</h2>
        
        {activeInvites.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Link2 className="h-12 w-12 mx-auto mb-3 opacity-20" />
            <p>No active invites</p>
            <p className="text-sm mt-1">Create an invite link to share with potential customers</p>
          </div>
        ) : (
          <div className="space-y-3">
            {activeInvites.map(invite => (
              <div 
                key={invite.id} 
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-secondary rounded-lg"
                data-testid={`invite-${invite.id}`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <code className="bg-accent/10 text-accent px-2 py-1 rounded font-mono text-sm">
                      {invite.code}
                    </code>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      Expires {formatDate(invite.expires_at)}
                    </span>
                  </div>
                  {invite.note && (
                    <p className="text-sm text-muted-foreground">{invite.note}</p>
                  )}
                </div>
                
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyLink(invite.code)}
                    data-testid={`copy-invite-${invite.id}`}
                  >
                    {copiedId === invite.code ? (
                      <><Check className="h-4 w-4 mr-1 text-green-600" /> Copied</>
                    ) : (
                      <><Copy className="h-4 w-4 mr-1" /> Copy Link</>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => shareViaWhatsApp(invite.code, invite.note)}
                    className="bg-green-50 border-green-200 text-green-700 hover:bg-green-100"
                    data-testid={`whatsapp-invite-${invite.id}`}
                  >
                    <Send className="h-4 w-4 mr-1" /> WhatsApp
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => deleteInvite(invite.id)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    data-testid={`delete-invite-${invite.id}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Used Invites */}
      {usedInvites.length > 0 && (
        <Card className="p-6">
          <h2 className="text-xl font-heading font-bold tracking-tightest mb-4 flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            Customers Who Joined
          </h2>
          <div className="space-y-3">
            {usedInvites.map(invite => (
              <div 
                key={invite.id} 
                className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg"
                data-testid={`used-invite-${invite.id}`}
              >
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <code className="bg-green-100 text-green-700 px-2 py-1 rounded font-mono text-sm">
                      {invite.code}
                    </code>
                    <span className="text-sm font-medium text-green-700">
                      → {invite.used_by}
                    </span>
                  </div>
                  {invite.note && (
                    <p className="text-sm text-muted-foreground">{invite.note}</p>
                  )}
                  <p className="text-xs text-green-600 mt-1">
                    Joined {formatDate(invite.used_at)}
                  </p>
                </div>
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Help Section */}
      <Card className="p-6 bg-blue-50/50 border-blue-200">
        <h3 className="font-heading font-bold text-lg mb-3">How Invite Links Work</h3>
        <div className="grid md:grid-cols-3 gap-4 text-sm">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold">1</div>
            <div>
              <p className="font-medium">Create Link</p>
              <p className="text-muted-foreground">Generate a unique invite link</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold">2</div>
            <div>
              <p className="font-medium">Share</p>
              <p className="text-muted-foreground">Send via WhatsApp, SMS, or email</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold">3</div>
            <div>
              <p className="font-medium">Customer Registers</p>
              <p className="text-muted-foreground">They click & create their account</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};
