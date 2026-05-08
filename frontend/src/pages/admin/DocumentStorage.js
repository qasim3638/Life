import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../../components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '../../components/ui/dropdown-menu';
import {
  Folder,
  FolderPlus,
  Upload,
  Search,
  FileText,
  Image,
  Film,
  Music,
  Archive,
  File,
  Download,
  Trash2,
  MoreVertical,
  Eye,
  Lock,
  Unlock,
  ChevronRight,
  Home,
  Grid,
  List,
  Clock,
  User,
  HardDrive,
  RefreshCw,
  X,
  Check,
  Edit,
  History,
  FolderOpen,
  ArrowLeft,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// File type icons
const getFileIcon = (fileType, extension) => {
  switch (fileType) {
    case 'image':
      return <Image className="h-8 w-8 text-green-500" />;
    case 'video':
      return <Film className="h-8 w-8 text-purple-500" />;
    case 'audio':
      return <Music className="h-8 w-8 text-pink-500" />;
    case 'archive':
      return <Archive className="h-8 w-8 text-orange-500" />;
    case 'document':
      if (['.pdf'].includes(extension)) return <FileText className="h-8 w-8 text-red-500" />;
      if (['.doc', '.docx'].includes(extension)) return <FileText className="h-8 w-8 text-blue-500" />;
      if (['.xls', '.xlsx'].includes(extension)) return <FileText className="h-8 w-8 text-green-600" />;
      return <FileText className="h-8 w-8 text-blue-500" />;
    default:
      return <File className="h-8 w-8 text-gray-500" />;
  }
};

// Format file size
const formatSize = (bytes) => {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// Format date
const formatDate = (dateString) => {
  if (!dateString) return '';
  return new Date(dateString).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export default function DocumentStorage() {
  const { user, token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [folders, setFolders] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [currentFolder, setCurrentFolder] = useState(null);
  const [breadcrumb, setBreadcrumb] = useState([]);
  const [viewMode, setViewMode] = useState('grid'); // grid or list
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState(null);
  
  // Dialogs
  const [createFolderDialog, setCreateFolderDialog] = useState(false);
  const [uploadDialog, setUploadDialog] = useState(false);
  const [passwordDialog, setPasswordDialog] = useState(false);
  const [previewDialog, setPreviewDialog] = useState(false);
  const [detailDialog, setDetailDialog] = useState(false);
  const [editFolderDialog, setEditFolderDialog] = useState(false);
  
  // Form states
  const [newFolder, setNewFolder] = useState({ name: '', description: '', password: '', is_public: true });
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [folderPassword, setFolderPassword] = useState('');
  const [uploadFiles, setUploadFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState({});
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  
  const fileInputRef = useRef(null);
  const isSuperAdmin = user?.role === 'super_admin';

  // Fetch folders and documents
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Build query params - only include parent_id/folder_id if we're in a subfolder
      const folderParams = currentFolder ? `?parent_id=${currentFolder}` : '';
      const docParams = currentFolder ? `?folder_id=${currentFolder}` : '';
      
      const [foldersRes, docsRes] = await Promise.all([
        api.get(`/documents/folders${folderParams}`),
        api.get(`/documents/list${docParams}`)
      ]);
      
      setFolders(foldersRes.data || []);
      setDocuments(docsRes.data?.documents || []);
      
      // Update breadcrumb
      if (currentFolder) {
        const folderRes = await api.get(`/documents/folders/${currentFolder}`);
        setBreadcrumb(folderRes.data?.path || []);
      } else {
        setBreadcrumb([]);
      }
    } catch (error) {
      console.error('Error fetching documents:', error);
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [currentFolder]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/documents/stats/overview');
      setStats(res.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  }, []);

  useEffect(() => {
    fetchData();
    fetchStats();
  }, [fetchData, fetchStats]);

  // Create folder
  const handleCreateFolder = async () => {
    if (!newFolder.name.trim()) {
      toast.error('Folder name is required');
      return;
    }
    
    try {
      await api.post('/documents/folders', {
        name: newFolder.name.trim(),
        description: newFolder.description,
        parent_id: currentFolder,
        password: newFolder.password || null,
        is_public: newFolder.is_public
      });
      
      toast.success('Folder created successfully');
      setCreateFolderDialog(false);
      setNewFolder({ name: '', description: '', password: '', is_public: true });
      fetchData();
      fetchStats();
    } catch (error) {
      console.error('Error creating folder:', error);
      toast.error(error.response?.data?.detail || 'Failed to create folder');
    }
  };

  // Open folder (with password check)
  const handleOpenFolder = async (folder) => {
    if (folder.is_protected) {
      setSelectedFolder(folder);
      setPasswordDialog(true);
    } else {
      setCurrentFolder(folder.id);
    }
  };

  // Verify folder password
  const handleVerifyPassword = async () => {
    try {
      await api.post(`/documents/folders/${selectedFolder.id}/verify-password`, {
        password: folderPassword
      });
      
      setCurrentFolder(selectedFolder.id);
      setPasswordDialog(false);
      setFolderPassword('');
      setSelectedFolder(null);
    } catch (error) {
      toast.error('Invalid password');
    }
  };

  // Upload files
  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    setUploadFiles(files);
    setUploadDialog(true);
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    
    const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
    
    for (const file of uploadFiles) {
      try {
        if (file.size <= CHUNK_SIZE) {
          // Small file - direct upload
          const formData = new FormData();
          formData.append('file', file);
          if (currentFolder) formData.append('folder_id', currentFolder);
          
          setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));
          
          await api.post('/documents/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (progressEvent) => {
              const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
              setUploadProgress(prev => ({ ...prev, [file.name]: progress }));
            }
          });
          
          setUploadProgress(prev => ({ ...prev, [file.name]: 100 }));
        } else {
          // Large file - chunked upload
          const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
          const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
          
          for (let i = 0; i < totalChunks; i++) {
            const start = i * CHUNK_SIZE;
            const end = Math.min(start + CHUNK_SIZE, file.size);
            const chunk = file.slice(start, end);
            
            const formData = new FormData();
            formData.append('chunk', chunk);
            formData.append('upload_id', uploadId);
            formData.append('chunk_index', i);
            formData.append('total_chunks', totalChunks);
            formData.append('filename', file.name);
            if (currentFolder) formData.append('folder_id', currentFolder);
            
            await api.post('/documents/upload-chunk', formData, {
              headers: { 'Content-Type': 'multipart/form-data' }
            });
            
            const progress = Math.round(((i + 1) / totalChunks) * 100);
            setUploadProgress(prev => ({ ...prev, [file.name]: progress }));
          }
        }
        
        toast.success(`${file.name} uploaded successfully`);
      } catch (error) {
        console.error(`Error uploading ${file.name}:`, error);
        toast.error(`Failed to upload ${file.name}: ${error.response?.data?.detail || error.message}`);
      }
    }
    
    setUploadDialog(false);
    setUploadFiles([]);
    setUploadProgress({});
    fetchData();
    fetchStats();
  };

  // Download document
  const handleDownload = async (doc) => {
    try {
      window.open(`${API_URL}/api/documents/${doc.id}/download`, '_blank');
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  // Preview document
  const handlePreview = async (doc) => {
    if (doc.file_type === 'image') {
      setPreviewUrl(`${API_URL}/api/documents/${doc.id}/download`);
      setSelectedDocument(doc);
      setPreviewDialog(true);
    } else if (doc.extension === '.pdf') {
      window.open(`${API_URL}/api/documents/${doc.id}/download`, '_blank');
    } else {
      toast.info('Preview not available for this file type');
    }
  };

  // Delete document
  const handleDeleteDocument = async (doc) => {
    if (!window.confirm(`Are you sure you want to delete "${doc.name}"?`)) return;
    
    try {
      await api.delete(`/documents/${doc.id}`);
      toast.success('Document deleted');
      fetchData();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete document');
    }
  };

  // Delete folder
  const handleDeleteFolder = async (folder) => {
    if (!window.confirm(`Are you sure you want to delete folder "${folder.name}" and all its contents?`)) return;
    
    try {
      await api.delete(`/documents/folders/${folder.id}`);
      toast.success('Folder deleted');
      fetchData();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete folder');
    }
  };

  // Search documents
  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      fetchData();
      return;
    }
    
    try {
      const res = await api.get(`/documents/search?q=${encodeURIComponent(searchQuery)}`);
      setDocuments(res.data?.documents || []);
      setFolders([]);
      setBreadcrumb([{ id: 'search', name: `Search: "${searchQuery}"` }]);
    } catch (error) {
      toast.error('Search failed');
    }
  };

  // Navigate back
  const handleBack = () => {
    if (breadcrumb.length > 0) {
      const parentId = breadcrumb.length > 1 ? breadcrumb[breadcrumb.length - 2].id : null;
      setCurrentFolder(parentId);
    }
  };

  // Navigate to folder from breadcrumb
  const handleBreadcrumbClick = (folderId) => {
    setCurrentFolder(folderId);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Document Storage</h1>
          <p className="text-slate-400">Manage your files and folders</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => { setViewMode(viewMode === 'grid' ? 'list' : 'grid'); }}>
            {viewMode === 'grid' ? <List className="h-4 w-4" /> : <Grid className="h-4 w-4" />}
          </Button>
          <Button variant="outline" size="sm" onClick={() => { fetchData(); fetchStats(); }}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-slate-800 border-slate-700">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <FileText className="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats.total_documents}</p>
                  <p className="text-xs text-slate-400">Total Files</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-slate-800 border-slate-700">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                  <Folder className="h-5 w-5 text-purple-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats.total_folders}</p>
                  <p className="text-xs text-slate-400">Folders</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-slate-800 border-slate-700">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <HardDrive className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">{stats.total_storage_mb} MB</p>
                  <p className="text-xs text-slate-400">Storage Used</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-slate-800 border-slate-700">
            <CardContent className="p-4">
              <div className="flex flex-wrap gap-2">
                {stats.by_type && Object.entries(stats.by_type).map(([type, data]) => (
                  <Badge key={type} variant="secondary" className="text-xs">
                    {type}: {data.count}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
        <div className="flex items-center gap-2">
          {currentFolder && (
            <Button variant="ghost" size="sm" onClick={handleBack}>
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
          )}
          
          {/* Breadcrumb */}
          <div className="flex items-center text-sm text-slate-400">
            <button 
              onClick={() => setCurrentFolder(null)}
              className="hover:text-white flex items-center"
            >
              <Home className="h-4 w-4" />
            </button>
            {breadcrumb.map((item, index) => (
              <React.Fragment key={item.id}>
                <ChevronRight className="h-4 w-4 mx-1" />
                <button
                  onClick={() => handleBreadcrumbClick(index === breadcrumb.length - 1 ? item.id : breadcrumb[index].id)}
                  className={`hover:text-white ${index === breadcrumb.length - 1 ? 'text-white font-medium' : ''}`}
                >
                  {item.name}
                </button>
              </React.Fragment>
            ))}
          </div>
        </div>
        
        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="pl-10 bg-slate-800 border-slate-700"
            />
          </div>
          <Button variant="outline" onClick={() => setCreateFolderDialog(true)}>
            <FolderPlus className="h-4 w-4 mr-2" />
            New Folder
          </Button>
          <Button onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-4 w-4 mr-2" />
            Upload
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : (
        <div className={viewMode === 'grid' ? 'grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4' : 'space-y-2'}>
          {/* Folders */}
          {folders.map((folder) => (
            <div
              key={folder.id}
              className={`group ${
                viewMode === 'grid'
                  ? 'bg-slate-800 border border-slate-700 rounded-lg p-4 hover:border-slate-600 cursor-pointer transition-all'
                  : 'bg-slate-800 border border-slate-700 rounded-lg p-3 hover:border-slate-600 cursor-pointer flex items-center justify-between'
              }`}
              onClick={() => handleOpenFolder(folder)}
              data-testid={`folder-${folder.id}`}
            >
              {viewMode === 'grid' ? (
                <>
                  <div className="flex items-center justify-center mb-3">
                    <div className="relative">
                      {folder.is_protected ? (
                        <FolderOpen className="h-12 w-12 text-yellow-500" />
                      ) : (
                        <Folder className="h-12 w-12 text-blue-500" />
                      )}
                      {folder.is_protected && (
                        <Lock className="h-4 w-4 text-yellow-500 absolute -bottom-1 -right-1" />
                      )}
                    </div>
                  </div>
                  <p className="text-white text-sm font-medium truncate text-center">{folder.name}</p>
                  <p className="text-xs text-slate-400 text-center mt-1">{folder.file_count || 0} files</p>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      {folder.is_protected ? (
                        <FolderOpen className="h-8 w-8 text-yellow-500" />
                      ) : (
                        <Folder className="h-8 w-8 text-blue-500" />
                      )}
                      {folder.is_protected && (
                        <Lock className="h-3 w-3 text-yellow-500 absolute -bottom-0.5 -right-0.5" />
                      )}
                    </div>
                    <div>
                      <p className="text-white font-medium">{folder.name}</p>
                      <p className="text-xs text-slate-400">{folder.file_count || 0} files • {formatSize(folder.total_size || 0)}</p>
                    </div>
                  </div>
                  {isSuperAdmin && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem onClick={(e) => { e.stopPropagation(); setSelectedFolder(folder); setEditFolderDialog(true); }}>
                          <Edit className="h-4 w-4 mr-2" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-red-500" onClick={(e) => { e.stopPropagation(); handleDeleteFolder(folder); }}>
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </>
              )}
            </div>
          ))}

          {/* Documents */}
          {documents.map((doc) => (
            <div
              key={doc.id}
              className={`group ${
                viewMode === 'grid'
                  ? 'bg-slate-800 border border-slate-700 rounded-lg p-4 hover:border-slate-600 cursor-pointer transition-all'
                  : 'bg-slate-800 border border-slate-700 rounded-lg p-3 hover:border-slate-600 flex items-center justify-between'
              }`}
              data-testid={`document-${doc.id}`}
            >
              {viewMode === 'grid' ? (
                <>
                  <div className="flex items-center justify-center mb-3">
                    {getFileIcon(doc.file_type, doc.extension)}
                  </div>
                  <p className="text-white text-sm font-medium truncate text-center" title={doc.name}>
                    {doc.name}
                  </p>
                  <p className="text-xs text-slate-400 text-center mt-1">{formatSize(doc.file_size)}</p>
                  <div className="flex items-center justify-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="sm" onClick={() => handlePreview(doc)}>
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDownload(doc)}>
                      <Download className="h-4 w-4" />
                    </Button>
                    {(isSuperAdmin || doc.uploaded_by === user?.email) && (
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteDocument(doc)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {getFileIcon(doc.file_type, doc.extension)}
                    <div className="min-w-0">
                      <p className="text-white font-medium truncate" title={doc.name}>{doc.name}</p>
                      <div className="flex items-center gap-3 text-xs text-slate-400">
                        <span>{formatSize(doc.file_size)}</span>
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {doc.uploaded_by_name || doc.uploaded_by}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(doc.created_at)}
                        </span>
                        {doc.version > 1 && (
                          <Badge variant="outline" className="text-xs">
                            v{doc.version}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" onClick={() => handlePreview(doc)}>
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDownload(doc)}>
                      <Download className="h-4 w-4" />
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem onClick={() => { setSelectedDocument(doc); setDetailDialog(true); }}>
                          <FileText className="h-4 w-4 mr-2" />
                          Details
                        </DropdownMenuItem>
                        {doc.version > 1 && (
                          <DropdownMenuItem onClick={() => { setSelectedDocument(doc); setDetailDialog(true); }}>
                            <History className="h-4 w-4 mr-2" />
                            Version History
                          </DropdownMenuItem>
                        )}
                        {(isSuperAdmin || doc.uploaded_by === user?.email) && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-red-500" onClick={() => handleDeleteDocument(doc)}>
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </>
              )}
            </div>
          ))}

          {/* Empty state */}
          {folders.length === 0 && documents.length === 0 && !loading && (
            <div className="col-span-full flex flex-col items-center justify-center py-16 text-slate-400">
              <FolderOpen className="h-16 w-16 mb-4 opacity-50" />
              <p className="text-lg">No files or folders</p>
              <p className="text-sm">Upload files or create a folder to get started</p>
            </div>
          )}
        </div>
      )}

      {/* Create Folder Dialog */}
      <Dialog open={createFolderDialog} onOpenChange={setCreateFolderDialog}>
        <DialogContent className="bg-slate-800 border-slate-700">
          <DialogHeader>
            <DialogTitle className="text-white">Create New Folder</DialogTitle>
            <DialogDescription className="text-slate-400">
              Create a folder to organize your documents
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-slate-400">Folder Name *</label>
              <Input
                value={newFolder.name}
                onChange={(e) => setNewFolder({ ...newFolder, name: e.target.value })}
                placeholder="Enter folder name"
                className="mt-1 bg-slate-900 border-slate-700"
                data-testid="folder-name-input"
              />
            </div>
            <div>
              <label className="text-sm text-slate-400">Description</label>
              <Input
                value={newFolder.description}
                onChange={(e) => setNewFolder({ ...newFolder, description: e.target.value })}
                placeholder="Optional description"
                className="mt-1 bg-slate-900 border-slate-700"
              />
            </div>
            {isSuperAdmin && (
              <div>
                <label className="text-sm text-slate-400">Password Protection (Optional)</label>
                <Input
                  type="password"
                  value={newFolder.password}
                  onChange={(e) => setNewFolder({ ...newFolder, password: e.target.value })}
                  placeholder="Leave empty for no password"
                  className="mt-1 bg-slate-900 border-slate-700"
                  data-testid="folder-password-input"
                />
                <p className="text-xs text-slate-500 mt-1">Only Super Admin can set folder passwords</p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateFolderDialog(false)}>Cancel</Button>
            <Button onClick={handleCreateFolder} data-testid="create-folder-btn">Create Folder</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Password Dialog */}
      <Dialog open={passwordDialog} onOpenChange={setPasswordDialog}>
        <DialogContent className="bg-slate-800 border-slate-700">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <Lock className="h-5 w-5 text-yellow-500" />
              Protected Folder
            </DialogTitle>
            <DialogDescription className="text-slate-400">
              Enter the password to access "{selectedFolder?.name}"
            </DialogDescription>
          </DialogHeader>
          <div>
            <Input
              type="password"
              value={folderPassword}
              onChange={(e) => setFolderPassword(e.target.value)}
              placeholder="Enter password"
              className="bg-slate-900 border-slate-700"
              onKeyDown={(e) => e.key === 'Enter' && handleVerifyPassword()}
              data-testid="folder-password-verify-input"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setPasswordDialog(false); setFolderPassword(''); }}>Cancel</Button>
            <Button onClick={handleVerifyPassword} data-testid="verify-password-btn">
              <Unlock className="h-4 w-4 mr-2" />
              Unlock
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upload Dialog */}
      <Dialog open={uploadDialog} onOpenChange={setUploadDialog}>
        <DialogContent className="bg-slate-800 border-slate-700 max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-white">Upload Files</DialogTitle>
            <DialogDescription className="text-slate-400">
              Upload files up to 100MB each
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {uploadFiles.map((file, index) => (
              <div key={index} className="flex items-center gap-3 bg-slate-900 p-3 rounded-lg">
                {getFileIcon(null, `.${file.name.split('.').pop()}`)}
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm truncate">{file.name}</p>
                  <p className="text-xs text-slate-400">{formatSize(file.size)}</p>
                  {uploadProgress[file.name] !== undefined && (
                    <div className="mt-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-blue-500 transition-all"
                        style={{ width: `${uploadProgress[file.name]}%` }}
                      />
                    </div>
                  )}
                </div>
                {uploadProgress[file.name] === 100 && (
                  <Check className="h-5 w-5 text-green-500" />
                )}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setUploadDialog(false); setUploadFiles([]); }}>Cancel</Button>
            <Button onClick={handleUpload} data-testid="confirm-upload-btn">
              <Upload className="h-4 w-4 mr-2" />
              Upload {uploadFiles.length} file{uploadFiles.length !== 1 ? 's' : ''}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog open={previewDialog} onOpenChange={setPreviewDialog}>
        <DialogContent className="bg-slate-800 border-slate-700 max-w-4xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle className="text-white">{selectedDocument?.name}</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-center p-4">
            {selectedDocument?.file_type === 'image' && previewUrl && (
              <img 
                src={previewUrl} 
                alt={selectedDocument?.name}
                className="max-w-full max-h-[70vh] object-contain rounded-lg"
              />
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewDialog(false)}>Close</Button>
            <Button onClick={() => handleDownload(selectedDocument)}>
              <Download className="h-4 w-4 mr-2" />
              Download
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail Dialog */}
      <Dialog open={detailDialog} onOpenChange={setDetailDialog}>
        <DialogContent className="bg-slate-800 border-slate-700">
          <DialogHeader>
            <DialogTitle className="text-white">File Details</DialogTitle>
          </DialogHeader>
          {selectedDocument && (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                {getFileIcon(selectedDocument.file_type, selectedDocument.extension)}
                <div>
                  <p className="text-white font-medium">{selectedDocument.name}</p>
                  <p className="text-sm text-slate-400">{selectedDocument.mime_type}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-400">Size</p>
                  <p className="text-white">{formatSize(selectedDocument.file_size)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Version</p>
                  <p className="text-white">v{selectedDocument.version}</p>
                </div>
                <div>
                  <p className="text-slate-400">Uploaded By</p>
                  <p className="text-white">{selectedDocument.uploaded_by_name || selectedDocument.uploaded_by}</p>
                </div>
                <div>
                  <p className="text-slate-400">Uploaded At</p>
                  <p className="text-white">{formatDate(selectedDocument.created_at)}</p>
                </div>
                <div>
                  <p className="text-slate-400">Downloads</p>
                  <p className="text-white">{selectedDocument.download_count || 0}</p>
                </div>
                <div>
                  <p className="text-slate-400">Type</p>
                  <p className="text-white capitalize">{selectedDocument.file_type}</p>
                </div>
              </div>
              {selectedDocument.tags && selectedDocument.tags.length > 0 && (
                <div>
                  <p className="text-slate-400 text-sm mb-2">Tags</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedDocument.tags.map((tag, i) => (
                      <Badge key={i} variant="secondary">{tag}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
