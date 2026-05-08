import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../components/ui/tabs';
import { 
  Plus, 
  Search, 
  Download, 
  Upload, 
  Trash2, 
  MoreVertical,
  RefreshCw,
  Users,
  Building2,
  Phone,
  Mail,
  MapPin,
  Calendar,
  User,
  FileSpreadsheet,
  Store
} from 'lucide-react';
import { Badge } from '../../components/ui/badge';

// Editable Cell Component
const EditableCell = ({ value, field, rowId, onSave, type = 'text' }) => {
  const [isEditing, setIsEditing] = useState(false);
  // Use value directly as initial state, component re-renders when value changes
  const [editValue, setEditValue] = useState(value || '');
  const inputRef = useRef(null);

  // Sync local state when value prop changes (using key pattern alternative)
  const latestValue = value || '';
  if (!isEditing && editValue !== latestValue) {
    setEditValue(latestValue);
  }

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = () => {
    if (editValue !== value) {
      onSave(rowId, field, editValue);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      setEditValue(value || '');
      setIsEditing(false);
    }
  };

  if (type === 'status') {
    return (
      <Select
        value={value || 'active'}
        onValueChange={(val) => onSave(rowId, field, val)}
      >
        <SelectTrigger className="h-8 text-xs border-0 bg-transparent hover:bg-muted/50 w-[100px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="active">
            <Badge variant="default" className="bg-green-500">Active</Badge>
          </SelectItem>
          <SelectItem value="inactive">
            <Badge variant="secondary">Inactive</Badge>
          </SelectItem>
          <SelectItem value="stopped_trading">
            <Badge variant="destructive">Stopped</Badge>
          </SelectItem>
        </SelectContent>
      </Select>
    );
  }

  if (isEditing) {
    return (
      <Input
        ref={inputRef}
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className="h-8 text-xs min-w-[100px]"
      />
    );
  }

  return (
    <div
      onClick={() => setIsEditing(true)}
      className="px-2 py-1 min-h-[32px] cursor-text hover:bg-muted/50 rounded text-sm flex items-center"
    >
      {value || <span className="text-muted-foreground italic">Click to edit</span>}
    </div>
  );
};

export const TradeList = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStore, setSelectedStore] = useState('');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [newAccount, setNewAccount] = useState({
    name: '',
    company_name: '',
    address: '',
    contact_no: '',
    email: '',
    extra_info: '',
    input_by: ''
  });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const storesRes = await api.getStores();
      setStores(storesRes.data);
      
      // Set default store if not selected
      if (!selectedStore && storesRes.data.length > 0) {
        setSelectedStore(storesRes.data[0].id);
      }
      
      // Fetch accounts for selected store
      if (selectedStore) {
        const accountsRes = await api.get(`/trade-list/by-showroom/${selectedStore}`);
        setAccounts(accountsRes.data);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load trade accounts');
    } finally {
      setLoading(false);
    }
  }, [selectedStore]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch accounts when store changes
  useEffect(() => {
    const fetchAccounts = async () => {
      if (selectedStore) {
        try {
          const accountsRes = await api.get(`/trade-list/by-showroom/${selectedStore}`);
          setAccounts(accountsRes.data);
        } catch (error) {
          console.error('Error fetching accounts:', error);
        }
      }
    };
    fetchAccounts();
  }, [selectedStore]);

  const handleCellSave = async (rowId, field, value) => {
    // Optimistic update
    setAccounts(prev => prev.map(account => 
      account.id === rowId ? { ...account, [field]: value } : account
    ));

    try {
      await api.patch('/trade-list/bulk', { updates: [{ id: rowId, field, value }] });
    } catch (error) {
      console.error('Error saving cell:', error);
      toast.error('Failed to save change');
      fetchData();
    }
  };

  const handleAddAccount = async () => {
    if (!newAccount.name) {
      toast.error('Name is required');
      return;
    }

    try {
      const response = await api.post('/trade-list', {
        ...newAccount,
        showroom_id: selectedStore,
        input_by: user?.name || user?.email || ''
      });
      setAccounts(prev => [...prev, response.data]);
      setShowAddDialog(false);
      setNewAccount({
        name: '',
        company_name: '',
        address: '',
        contact_no: '',
        email: '',
        extra_info: '',
        input_by: ''
      });
      toast.success('Trade account added');
    } catch (error) {
      console.error('Error adding account:', error);
      toast.error('Failed to add trade account');
    }
  };

  const handleDeleteAccount = async (id) => {
    if (!window.confirm('Are you sure you want to delete this trade account?')) return;

    try {
      await api.delete(`/trade-list/${id}`);
      setAccounts(prev => prev.filter(a => a.id !== id));
      toast.success('Trade account deleted');
    } catch (error) {
      console.error('Error deleting account:', error);
      toast.error('Failed to delete trade account');
    }
  };

  const handleExportCsv = () => {
    const headers = ['Date Registered', 'Name', 'Company Name', 'Address', 'Contact No', 'Email', 'Extra Info', 'Input By', 'Status'];
    const rows = accounts.map(a => [
      a.date_registered || '',
      a.name || '',
      a.company_name || '',
      a.address || '',
      a.contact_no || '',
      a.email || '',
      a.extra_info || '',
      a.input_by || '',
      a.status || 'active'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${(cell || '').replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    const storeName = stores.find(s => s.id === selectedStore)?.name || 'store';
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trade_list_${storeName}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success('CSV exported successfully');
  };

  const handleFileImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const text = e.target?.result;
        const lines = text.split('\n').filter(line => line.trim());
        if (lines.length < 2) {
          toast.error('CSV file is empty or has no data rows');
          return;
        }

        const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
        const entries = [];
        
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].match(/(".*?"|[^,]+)/g) || [];
          const row = {};
          headers.forEach((header, idx) => {
            row[header] = (values[idx] || '').replace(/"/g, '').trim();
          });
          if (row['NAME'] || row['Name'] || row['name']) {
            entries.push(row);
          }
        }

        const response = await api.post(`/trade-list/import?showroom_id=${selectedStore}`, entries);
        toast.success(`Imported ${response.data.imported} trade accounts`);
        setShowImportDialog(false);
        fetchData();
      } catch (error) {
        console.error('Error importing CSV:', error);
        toast.error('Failed to import CSV');
      }
    };
    reader.readAsText(file);
  };

  // Filter accounts
  const filteredAccounts = accounts.filter(account => {
    const matchesSearch = !searchTerm || 
      account.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      account.company_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      account.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      account.contact_no?.includes(searchTerm);
    
    return matchesSearch;
  });

  const currentStoreName = stores.find(s => s.id === selectedStore)?.name || 'Select Store';

  if (loading && stores.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="trade-list-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Users className="h-6 w-6" />
            Builders Trade List
          </h1>
          <p className="text-muted-foreground">Manage trade accounts for each showroom</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchData} data-testid="refresh-btn">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportCsv} data-testid="export-btn">
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowImportDialog(true)} data-testid="import-btn">
            <Upload className="h-4 w-4 mr-2" />
            Import CSV
          </Button>
          <Button onClick={() => setShowAddDialog(true)} data-testid="add-account-btn">
            <Plus className="h-4 w-4 mr-2" />
            Add Account
          </Button>
        </div>
      </div>

      {/* Store Tabs */}
      <Tabs value={selectedStore} onValueChange={setSelectedStore} className="w-full">
        <TabsList className="grid w-full" style={{ gridTemplateColumns: `repeat(${stores.length}, 1fr)` }}>
          {stores.map(store => (
            <TabsTrigger key={store.id} value={store.id} className="flex items-center gap-2">
              <Store className="h-4 w-4" />
              {store.name}
              <Badge variant="secondary" className="ml-1">
                {accounts.filter(a => a.showroom_id === store.id).length || filteredAccounts.length}
              </Badge>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Search */}
      <div className="flex items-center gap-4 p-4 bg-card rounded-lg border">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by name, company, email, or phone..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
              data-testid="search-input"
            />
          </div>
        </div>
        <div className="text-sm text-muted-foreground">
          {filteredAccounts.length} trade accounts
        </div>
      </div>

      {/* Table */}
      <div className="border rounded-lg overflow-hidden bg-card">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="font-semibold min-w-[100px]">
                  <div className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    Date
                  </div>
                </TableHead>
                <TableHead className="font-semibold min-w-[150px]">
                  <div className="flex items-center gap-1">
                    <User className="h-3 w-3" />
                    Name
                  </div>
                </TableHead>
                <TableHead className="font-semibold min-w-[180px]">
                  <div className="flex items-center gap-1">
                    <Building2 className="h-3 w-3" />
                    Company
                  </div>
                </TableHead>
                <TableHead className="font-semibold min-w-[200px]">
                  <div className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" />
                    Address
                  </div>
                </TableHead>
                <TableHead className="font-semibold min-w-[130px]">
                  <div className="flex items-center gap-1">
                    <Phone className="h-3 w-3" />
                    Contact No
                  </div>
                </TableHead>
                <TableHead className="font-semibold min-w-[180px]">
                  <div className="flex items-center gap-1">
                    <Mail className="h-3 w-3" />
                    Email
                  </div>
                </TableHead>
                <TableHead className="font-semibold min-w-[150px]">Extra Info</TableHead>
                <TableHead className="font-semibold min-w-[100px]">Input By</TableHead>
                <TableHead className="font-semibold min-w-[100px]">Status</TableHead>
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAccounts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="text-center py-8 text-muted-foreground">
                    <FileSpreadsheet className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>No trade accounts for {currentStoreName}</p>
                    <p className="text-sm">Add accounts manually or import from CSV</p>
                  </TableCell>
                </TableRow>
              ) : (
                filteredAccounts.map((account) => (
                  <TableRow key={account.id} className="hover:bg-muted/30">
                    <TableCell>
                      <EditableCell
                        value={account.date_registered}
                        field="date_registered"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      <EditableCell
                        value={account.name}
                        field="name"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={account.company_name}
                        field="company_name"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={account.address}
                        field="address"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={account.contact_no}
                        field="contact_no"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={account.email}
                        field="email"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={account.extra_info}
                        field="extra_info"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={account.input_by}
                        field="input_by"
                        rowId={account.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={account.status}
                        field="status"
                        rowId={account.id}
                        onSave={handleCellSave}
                        type="status"
                      />
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => handleDeleteAccount(account.id)}
                            className="text-destructive"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Add Account Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add New Trade Account</DialogTitle>
            <DialogDescription>
              Add a new builder trade account to {currentStoreName}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Name *</label>
                <Input
                  value={newAccount.name}
                  onChange={(e) => setNewAccount(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Contact name"
                  data-testid="new-name"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Company Name</label>
                <Input
                  value={newAccount.company_name}
                  onChange={(e) => setNewAccount(prev => ({ ...prev, company_name: e.target.value }))}
                  placeholder="Company name"
                  data-testid="new-company"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Address</label>
              <Input
                value={newAccount.address}
                onChange={(e) => setNewAccount(prev => ({ ...prev, address: e.target.value }))}
                placeholder="Full address"
                data-testid="new-address"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Contact No</label>
                <Input
                  value={newAccount.contact_no}
                  onChange={(e) => setNewAccount(prev => ({ ...prev, contact_no: e.target.value }))}
                  placeholder="Phone number"
                  data-testid="new-contact"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Email</label>
                <Input
                  value={newAccount.email}
                  onChange={(e) => setNewAccount(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="Email address"
                  type="email"
                  data-testid="new-email"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Extra Info</label>
              <Input
                value={newAccount.extra_info}
                onChange={(e) => setNewAccount(prev => ({ ...prev, extra_info: e.target.value }))}
                placeholder="Additional notes"
                data-testid="new-extra-info"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddAccount} data-testid="save-new-account">
              <Plus className="h-4 w-4 mr-2" />
              Add Account
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import CSV Dialog */}
      <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import Trade Accounts</DialogTitle>
            <DialogDescription>
              Upload a CSV file with trade account data for {currentStoreName}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <div className="border-2 border-dashed rounded-lg p-8 text-center">
              <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground mb-4">
                Click to select a CSV file or drag and drop
              </p>
              <input
                type="file"
                accept=".csv"
                onChange={handleFileImport}
                className="hidden"
                id="csv-upload-trade"
                data-testid="csv-file-input"
              />
              <label htmlFor="csv-upload-trade">
                <Button variant="outline" asChild>
                  <span>Select CSV File</span>
                </Button>
              </label>
            </div>
            <div className="mt-4 text-xs text-muted-foreground">
              <p className="font-medium mb-1">Expected columns:</p>
              <p>NAME, COMPANY NAME, ADDRESS, CONTACT NO, EMAIL, ETXRA INFO</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowImportDialog(false)}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TradeList;
