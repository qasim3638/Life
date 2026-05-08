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
  Plus, 
  Search, 
  Download, 
  Upload, 
  Trash2, 
  MoreVertical,
  Check,
  X,
  Save,
  FileSpreadsheet,
  Filter,
  RefreshCw
} from 'lucide-react';

// Editable Cell Component
const EditableCell = ({ value, field, rowId, onSave, type = 'text', options = [] }) => {
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

  if (type === 'boolean') {
    return (
      <button
        onClick={() => onSave(rowId, field, value === 'Yes' ? 'No' : 'Yes')}
        className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
          value === 'Yes' 
            ? 'bg-green-100 text-green-700 hover:bg-green-200' 
            : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
        }`}
        data-testid={`cell-${field}-${rowId}`}
      >
        {value || 'No'}
      </button>
    );
  }

  if (type === 'select' && options.length > 0) {
    return (
      <Select
        value={value || ''}
        onValueChange={(val) => onSave(rowId, field, val)}
      >
        <SelectTrigger className="h-8 text-xs border-0 bg-transparent hover:bg-muted/50" data-testid={`cell-${field}-${rowId}`}>
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent>
          {options.map(opt => (
            <SelectItem key={opt} value={opt}>{opt}</SelectItem>
          ))}
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
        data-testid={`cell-edit-${field}-${rowId}`}
      />
    );
  }

  return (
    <div
      onClick={() => setIsEditing(true)}
      className="px-2 py-1 min-h-[32px] cursor-text hover:bg-muted/50 rounded text-sm flex items-center"
      data-testid={`cell-${field}-${rowId}`}
    >
      {value || <span className="text-muted-foreground italic">Click to edit</span>}
    </div>
  );
};

export const TilesInfo = () => {
  const { user } = useAuth();
  const [entries, setEntries] = useState([]);
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [supplierFilter, setSupplierFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [suppliers, setSuppliers] = useState([]);
  const [categories, setCategories] = useState([]);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [pendingChanges, setPendingChanges] = useState([]);
  const [newEntry, setNewEntry] = useState({
    original_name: '',
    our_name: '',
    online_name: '',
    price_on_ticket: '',
    finish: '',
    supplier: '',
    category: '',
    notes: ''
  });

  const finishOptions = ['Polished', 'Matt', 'High Polished', 'Satin', 'Textured', 'Natural'];

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [entriesRes, storesRes] = await Promise.all([
        api.get('/tiles-info'),
        api.getStores()
      ]);
      setEntries(entriesRes.data);
      setStores(storesRes.data);

      // Get unique suppliers and categories
      const uniqueSuppliers = [...new Set(entriesRes.data.map(e => e.supplier).filter(Boolean))];
      const uniqueCategories = [...new Set(entriesRes.data.map(e => e.category).filter(Boolean))];
      setSuppliers(uniqueSuppliers);
      setCategories(uniqueCategories);
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load tiles info');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCellSave = async (rowId, field, value) => {
    // Optimistic update
    setEntries(prev => prev.map(entry => {
      if (entry.id === rowId) {
        if (field.startsWith('display_')) {
          const showroomId = field.replace('display_', '');
          return {
            ...entry,
            display_locations: {
              ...entry.display_locations,
              [showroomId]: value === 'Yes'
            }
          };
        }
        return { ...entry, [field]: value };
      }
      return entry;
    }));

    // Queue the change
    setPendingChanges(prev => {
      const existing = prev.findIndex(p => p.id === rowId && p.field === field);
      if (existing >= 0) {
        const updated = [...prev];
        updated[existing] = { id: rowId, field, value };
        return updated;
      }
      return [...prev, { id: rowId, field, value }];
    });

    // Auto-save after a short delay (debounced)
    try {
      await api.patch('/tiles-info/bulk', { updates: [{ id: rowId, field, value }] });
    } catch (error) {
      console.error('Error saving cell:', error);
      toast.error('Failed to save change');
      fetchData(); // Revert on error
    }
  };

  const handleAddEntry = async () => {
    if (!newEntry.original_name || !newEntry.our_name) {
      toast.error('Original Name and Our Name are required');
      return;
    }

    try {
      const response = await api.post('/tiles-info', newEntry);
      setEntries(prev => [...prev, response.data]);
      setShowAddDialog(false);
      setNewEntry({
        original_name: '',
        our_name: '',
        online_name: '',
        price_on_ticket: '',
        finish: '',
        supplier: '',
        category: '',
        notes: ''
      });
      toast.success('Entry added successfully');
    } catch (error) {
      console.error('Error adding entry:', error);
      toast.error('Failed to add entry');
    }
  };

  const handleDeleteEntry = async (id) => {
    if (!window.confirm('Are you sure you want to delete this entry?')) return;

    try {
      await api.delete(`/tiles-info/${id}`);
      setEntries(prev => prev.filter(e => e.id !== id));
      toast.success('Entry deleted');
    } catch (error) {
      console.error('Error deleting entry:', error);
      toast.error('Failed to delete entry');
    }
  };

  const handleExportCsv = () => {
    // Build CSV headers
    const baseHeaders = ['Original Name', 'Our Name', 'Online Name', 'Price on Ticket', 'Finish', 'Supplier', 'Category'];
    const storeHeaders = stores.map(s => `On Display in ${s.name}?`);
    const headers = [...baseHeaders, ...storeHeaders];

    // Build CSV rows
    const rows = entries.map(entry => {
      const baseData = [
        entry.original_name || '',
        entry.our_name || '',
        entry.online_name || '',
        entry.price_on_ticket || '',
        entry.finish || '',
        entry.supplier || '',
        entry.category || ''
      ];
      const storeData = stores.map(s => 
        entry.display_locations?.[s.id] ? 'Yes' : ''
      );
      return [...baseData, ...storeData];
    });

    // Create CSV content
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${(cell || '').replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tiles_info_${new Date().toISOString().split('T')[0]}.csv`;
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

        // Parse headers
        const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
        
        // Parse rows
        const entries = [];
        for (let i = 1; i < lines.length; i++) {
          const values = lines[i].match(/(".*?"|[^,]+)/g) || [];
          const row = {};
          headers.forEach((header, idx) => {
            row[header] = (values[idx] || '').replace(/"/g, '').trim();
          });
          if (row['Original Name'] || row['Our Name']) {
            entries.push(row);
          }
        }

        // Import to backend
        const response = await api.post('/tiles-info/import-csv', entries);
        toast.success(`Imported ${response.data.imported} entries`);
        setShowImportDialog(false);
        fetchData();
      } catch (error) {
        console.error('Error importing CSV:', error);
        toast.error('Failed to import CSV');
      }
    };
    reader.readAsText(file);
  };

  // Filter entries
  const filteredEntries = entries.filter(entry => {
    const matchesSearch = !searchTerm || 
      entry.original_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.our_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      entry.online_name?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesSupplier = !supplierFilter || supplierFilter === 'all' || entry.supplier === supplierFilter;
    const matchesCategory = !categoryFilter || categoryFilter === 'all' || entry.category === categoryFilter;

    return matchesSearch && matchesSupplier && matchesCategory;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="tiles-info-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Tiles Info</h1>
          <p className="text-muted-foreground">Manage tile product information like a spreadsheet</p>
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
          <Button onClick={() => setShowAddDialog(true)} data-testid="add-entry-btn">
            <Plus className="h-4 w-4 mr-2" />
            Add Entry
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 p-4 bg-card rounded-lg border">
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search tiles..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
              data-testid="search-input"
            />
          </div>
        </div>
        
        <Select value={supplierFilter} onValueChange={setSupplierFilter}>
          <SelectTrigger className="w-[180px]" data-testid="supplier-filter">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="All Suppliers" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Suppliers</SelectItem>
            {suppliers.map(s => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[180px]" data-testid="category-filter">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {categories.map(c => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="text-sm text-muted-foreground">
          {filteredEntries.length} of {entries.length} entries
        </div>
      </div>

      {/* Spreadsheet Table */}
      <div className="border rounded-lg overflow-hidden bg-card">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="font-semibold min-w-[180px] sticky left-0 bg-muted/50 z-10">Original Name</TableHead>
                <TableHead className="font-semibold min-w-[180px]">Our Name</TableHead>
                <TableHead className="font-semibold min-w-[140px]">Online Name</TableHead>
                <TableHead className="font-semibold min-w-[120px]">Price on Ticket</TableHead>
                <TableHead className="font-semibold min-w-[100px]">Finish</TableHead>
                {stores.map(store => (
                  <TableHead key={store.id} className="font-semibold min-w-[120px] text-center">
                    On Display in<br/>{store.name}?
                  </TableHead>
                ))}
                <TableHead className="font-semibold min-w-[120px]">Supplier</TableHead>
                <TableHead className="font-semibold min-w-[120px]">Category</TableHead>
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEntries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9 + stores.length} className="text-center py-8 text-muted-foreground">
                    <FileSpreadsheet className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>No tiles info entries yet</p>
                    <p className="text-sm">Add entries manually or import from CSV</p>
                  </TableCell>
                </TableRow>
              ) : (
                filteredEntries.map((entry) => (
                  <TableRow key={entry.id} className="hover:bg-muted/30" data-testid={`row-${entry.id}`}>
                    <TableCell className="sticky left-0 bg-card z-10 border-r">
                      <EditableCell
                        value={entry.original_name}
                        field="original_name"
                        rowId={entry.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={entry.our_name}
                        field="our_name"
                        rowId={entry.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={entry.online_name}
                        field="online_name"
                        rowId={entry.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={entry.price_on_ticket}
                        field="price_on_ticket"
                        rowId={entry.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={entry.finish}
                        field="finish"
                        rowId={entry.id}
                        onSave={handleCellSave}
                        type="select"
                        options={finishOptions}
                      />
                    </TableCell>
                    {stores.map(store => (
                      <TableCell key={store.id} className="text-center">
                        <EditableCell
                          value={entry.display_locations?.[store.id] ? 'Yes' : 'No'}
                          field={`display_${store.id}`}
                          rowId={entry.id}
                          onSave={handleCellSave}
                          type="boolean"
                        />
                      </TableCell>
                    ))}
                    <TableCell>
                      <EditableCell
                        value={entry.supplier}
                        field="supplier"
                        rowId={entry.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <EditableCell
                        value={entry.category}
                        field="category"
                        rowId={entry.id}
                        onSave={handleCellSave}
                      />
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8" data-testid={`row-menu-${entry.id}`}>
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => handleDeleteEntry(entry.id)}
                            className="text-destructive"
                            data-testid={`delete-${entry.id}`}
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

      {/* Add Entry Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add New Tile Entry</DialogTitle>
            <DialogDescription>
              Add a new tile product to the information sheet
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Original Name *</label>
                <Input
                  value={newEntry.original_name}
                  onChange={(e) => setNewEntry(prev => ({ ...prev, original_name: e.target.value }))}
                  placeholder="Supplier's name"
                  data-testid="new-original-name"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Our Name *</label>
                <Input
                  value={newEntry.our_name}
                  onChange={(e) => setNewEntry(prev => ({ ...prev, our_name: e.target.value }))}
                  placeholder="Your display name"
                  data-testid="new-our-name"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Online Name</label>
                <Input
                  value={newEntry.online_name}
                  onChange={(e) => setNewEntry(prev => ({ ...prev, online_name: e.target.value }))}
                  placeholder="Same"
                  data-testid="new-online-name"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Price on Ticket</label>
                <Input
                  value={newEntry.price_on_ticket}
                  onChange={(e) => setNewEntry(prev => ({ ...prev, price_on_ticket: e.target.value }))}
                  placeholder="e.g., 39.99/29.99"
                  data-testid="new-price"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">Finish</label>
                <Select
                  value={newEntry.finish}
                  onValueChange={(val) => setNewEntry(prev => ({ ...prev, finish: val }))}
                >
                  <SelectTrigger data-testid="new-finish">
                    <SelectValue placeholder="Select finish" />
                  </SelectTrigger>
                  <SelectContent>
                    {finishOptions.map(opt => (
                      <SelectItem key={opt} value={opt}>{opt}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm font-medium">Supplier</label>
                <Input
                  value={newEntry.supplier}
                  onChange={(e) => setNewEntry(prev => ({ ...prev, supplier: e.target.value }))}
                  placeholder="Supplier name"
                  data-testid="new-supplier"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium">Category</label>
              <Input
                value={newEntry.category}
                onChange={(e) => setNewEntry(prev => ({ ...prev, category: e.target.value }))}
                placeholder="e.g., Le Porce, Dallas White"
                data-testid="new-category"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddEntry} data-testid="save-new-entry">
              <Plus className="h-4 w-4 mr-2" />
              Add Entry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import CSV Dialog */}
      <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Import from CSV</DialogTitle>
            <DialogDescription>
              Upload a CSV file with tile information. The CSV should have headers matching the columns.
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
                id="csv-upload"
                data-testid="csv-file-input"
              />
              <label htmlFor="csv-upload">
                <Button variant="outline" asChild>
                  <span>Select CSV File</span>
                </Button>
              </label>
            </div>
            <div className="mt-4 text-xs text-muted-foreground">
              <p className="font-medium mb-1">Expected columns:</p>
              <p>Original Name, Our Name, Online Name, Price on Ticket, Finish, Supplier, Category, On Display in [Store Name]?</p>
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

export default TilesInfo;
