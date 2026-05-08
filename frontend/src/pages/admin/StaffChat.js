import React, { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';
import { 
  MessageCircle, Send, Users, Store, Megaphone, Hash, 
  ChevronLeft, X, Paperclip, FileText, Image, File, Download,
  Volume2, VolumeX
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { useAuth } from '../../contexts/AuthContext';
import { api } from '../../lib/api';

// File type icons
const getFileIcon = (fileType) => {
  const imageTypes = ['png', 'jpg', 'jpeg', 'gif'];
  const docTypes = ['pdf', 'doc', 'docx'];
  
  if (imageTypes.includes(fileType)) return <Image className="h-4 w-4" />;
  if (docTypes.includes(fileType)) return <FileText className="h-4 w-4" />;
  return <File className="h-4 w-4" />;
};

// Format file size
const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

// Notification sound (base64 encoded short beep)
const playNotificationSound = () => {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.value = 800;
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.3);
  } catch (e) {
    console.log('Could not play notification sound');
  }
};

export const StaffChat = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [channels, setChannels] = useState([]);
  const [activeChannel, setActiveChannel] = useState('general');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showSidebar, setShowSidebar] = useState(true);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [typingUsers, setTypingUsers] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const fileInputRef = useRef(null);
  const lastMessageCountRef = useRef(0);
  const typingTimeoutRef = useRef(null);

  // Fetch channels
  useEffect(() => {
    const fetchChannels = async () => {
      try {
        const res = await api.get('/chat/channels');
        setChannels(res.data);
      } catch (error) {
        console.error('Failed to fetch channels:', error);
      }
    };
    fetchChannels();
  }, []);

  // Fetch messages for active channel
  const fetchMessages = async (playSound = true) => {
    try {
      const res = await api.get(`/chat?channel=${activeChannel}&limit=50`);
      
      // Check for new messages and play sound
      if (playSound && soundEnabled && res.data.length > lastMessageCountRef.current) {
        const newMessages = res.data.slice(lastMessageCountRef.current);
        const hasNewFromOthers = newMessages.some(m => m.sender_id !== user?.id);
        if (hasNewFromOthers && lastMessageCountRef.current > 0) {
          playNotificationSound();
          // Show toast for new message
          const latestNew = newMessages.find(m => m.sender_id !== user?.id);
          if (latestNew) {
            toast.info(`${latestNew.sender_name}: ${latestNew.content.substring(0, 50)}...`, {
              duration: 3000,
            });
          }
        }
      }
      lastMessageCountRef.current = res.data.length;
      
      setMessages(res.data);
      
      // Mark as read
      if (res.data.length > 0) {
        const unreadIds = res.data
          .filter(m => !m.read_by?.includes(user?.id))
          .map(m => m.id);
        if (unreadIds.length > 0) {
          await api.post('/chat/read', unreadIds);
        }
      }
      
      // Fetch typing indicators
      fetchTypingUsers();
    } catch (error) {
      console.error('Failed to fetch messages:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch typing users
  const fetchTypingUsers = async () => {
    try {
      const res = await api.get(`/chat/typing?channel=${activeChannel}`);
      setTypingUsers(res.data.filter(t => t.user_id !== user?.id));
    } catch (error) {
      // Typing endpoint may not exist yet, ignore
    }
  };

  // Send typing indicator
  const sendTypingIndicator = useCallback(async () => {
    try {
      await api.post('/chat/typing', { channel: activeChannel });
    } catch (error) {
      // Ignore typing errors
    }
  }, [activeChannel]);

  // Handle typing
  const handleTyping = () => {
    if (!isTyping) {
      setIsTyping(true);
      sendTypingIndicator();
    }
    
    // Clear existing timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    
    // Set new timeout to stop typing indicator
    typingTimeoutRef.current = setTimeout(() => {
      setIsTyping(false);
    }, 2000);
  };

  // Fetch unread count
  const fetchUnreadCount = async () => {
    try {
      const res = await api.get('/chat/unread');
      setUnreadCount(res.data.unread);
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
    }
  };

  useEffect(() => {
    // Reset message count when changing channels
    lastMessageCountRef.current = 0;
    fetchMessages(false); // Don't play sound on initial load
    fetchUnreadCount();
    
    // Poll for new messages every 3 seconds
    pollIntervalRef.current = setInterval(() => {
      fetchMessages(true);
      fetchUnreadCount();
    }, 3000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChannel]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle file selection
  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Check file size (10MB max)
      if (file.size > 10 * 1024 * 1024) {
        toast.error('File too large. Maximum size is 10MB');
        return;
      }
      setSelectedFile(file);
    }
  };

  // Remove selected file
  const removeSelectedFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Send message (with or without file)
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() && !selectedFile) return;

    setSending(true);
    try {
      let res;
      
      if (selectedFile) {
        // Send with attachment
        setUploading(true);
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('content', newMessage.trim());
        formData.append('channel', activeChannel);
        
        res = await api.post('/chat/with-attachment', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        setUploading(false);
      } else {
        // Send text only
        res = await api.post('/chat', {
          content: newMessage.trim(),
          channel: activeChannel
        });
      }
      
      setMessages([...messages, res.data]);
      setNewMessage('');
    } catch (error) {
      toast.error('Failed to send message');
      setUploading(false);
    } finally {
      setSending(false);
    }
  };

  // Download attachment
  const handleDownloadAttachment = async (attachment) => {
    try {
      const res = await api.get(`/chat/attachment/${attachment.id}`);
      
      // Decode base64 and create download
      const byteCharacters = atob(res.data.data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: res.data.mime_type });
      
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = res.data.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      toast.success(`Downloaded ${res.data.filename}`);
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  // Get channel icon
  const getChannelIcon = (channel) => {
    if (channel.icon === 'users') return <Users className="h-4 w-4" />;
    if (channel.icon === 'megaphone') return <Megaphone className="h-4 w-4" />;
    if (channel.icon === 'store') return <Store className="h-4 w-4" />;
    return <Hash className="h-4 w-4" />;
  };

  // Format timestamp
  const formatTime = (isoString) => {
    const date = new Date(isoString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    
    if (isToday) {
      return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) + 
           ' ' + date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  };

  // Get initials for avatar
  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  // Get color for avatar based on name
  const getAvatarColor = (name) => {
    const colors = [
      'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500',
      'bg-pink-500', 'bg-teal-500', 'bg-indigo-500', 'bg-red-500'
    ];
    const index = name ? name.charCodeAt(0) % colors.length : 0;
    return colors[index];
  };

  const activeChannelInfo = channels.find(c => c.id === activeChannel);

  return (
    <div className="h-[calc(100vh-120px)] flex" data-testid="staff-chat">
      {/* Channel Sidebar */}
      <div className={`${showSidebar ? 'w-64' : 'w-0'} transition-all duration-300 overflow-hidden border-r bg-gray-50`}>
        <div className="p-4">
          <h2 className="font-semibold text-lg flex items-center gap-2 mb-4">
            <MessageCircle className="h-5 w-5" />
            Staff Chat
          </h2>
          
          {/* Channels */}
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
              Channels
            </p>
            {channels.map(channel => (
              <button
                key={channel.id}
                onClick={() => setActiveChannel(channel.id)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeChannel === channel.id 
                    ? 'bg-primary text-primary-foreground' 
                    : 'hover:bg-gray-200 text-gray-700'
                }`}
              >
                {getChannelIcon(channel)}
                <span className="truncate">{channel.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat Header */}
        <div className="h-14 border-b flex items-center justify-between px-4 bg-white">
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setShowSidebar(!showSidebar)}
              className="p-1 hover:bg-gray-100 rounded lg:hidden"
            >
              {showSidebar ? <X className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
            </button>
            <div className="flex items-center gap-2">
              {activeChannelInfo && getChannelIcon(activeChannelInfo)}
              <div>
                <h3 className="font-semibold">{activeChannelInfo?.name || 'General'}</h3>
                <p className="text-xs text-muted-foreground">{activeChannelInfo?.description}</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Sound toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSoundEnabled(!soundEnabled)}
              title={soundEnabled ? 'Mute notifications' : 'Enable notifications'}
              className="h-8 w-8"
            >
              {soundEnabled ? (
                <Volume2 className="h-4 w-4 text-green-600" />
              ) : (
                <VolumeX className="h-4 w-4 text-gray-400" />
              )}
            </Button>
            {unreadCount > 0 && (
              <span className="bg-red-500 text-white text-xs px-2 py-1 rounded-full">
                {unreadCount} unread
              </span>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <MessageCircle className="h-12 w-12 mb-2 opacity-50" />
              <p>No messages yet</p>
              <p className="text-sm">Be the first to say hello!</p>
            </div>
          ) : (
            messages.map((message, index) => {
              const isOwnMessage = message.sender_id === user?.id;
              const showAvatar = index === 0 || messages[index - 1]?.sender_id !== message.sender_id;
              
              return (
                <div
                  key={message.id}
                  className={`flex gap-3 ${isOwnMessage ? 'flex-row-reverse' : ''}`}
                >
                  {/* Avatar */}
                  <div className={`w-8 ${showAvatar ? '' : 'invisible'}`}>
                    <div className={`w-8 h-8 rounded-full ${getAvatarColor(message.sender_name)} flex items-center justify-center text-white text-xs font-medium`}>
                      {getInitials(message.sender_name)}
                    </div>
                  </div>
                  
                  {/* Message Content */}
                  <div className={`max-w-[70%] ${isOwnMessage ? 'items-end' : 'items-start'}`}>
                    {showAvatar && (
                      <div className={`flex items-center gap-2 mb-1 ${isOwnMessage ? 'flex-row-reverse' : ''}`}>
                        <span className="text-sm font-medium">{message.sender_name}</span>
                        {message.sender_store && (
                          <span className="text-xs text-muted-foreground bg-gray-200 px-1.5 py-0.5 rounded">
                            {message.sender_store}
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {formatTime(message.created_at)}
                        </span>
                      </div>
                    )}
                    <div className={`px-4 py-2 rounded-2xl ${
                      isOwnMessage 
                        ? 'bg-primary text-primary-foreground rounded-tr-sm' 
                        : 'bg-white border rounded-tl-sm'
                    }`}>
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                      
                      {/* Attachments */}
                      {message.attachments && message.attachments.length > 0 && (
                        <div className="mt-2 space-y-2">
                          {message.attachments.map((attachment) => (
                            <button
                              key={attachment.id}
                              onClick={() => handleDownloadAttachment(attachment)}
                              className={`flex items-center gap-2 p-2 rounded-lg transition-colors w-full text-left ${
                                isOwnMessage 
                                  ? 'bg-primary-foreground/10 hover:bg-primary-foreground/20 text-primary-foreground' 
                                  : 'bg-gray-100 hover:bg-gray-200'
                              }`}
                            >
                              {getFileIcon(attachment.file_type)}
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{attachment.filename}</p>
                                <p className={`text-xs ${isOwnMessage ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                                  {formatFileSize(attachment.file_size)}
                                </p>
                              </div>
                              <Download className="h-4 w-4 flex-shrink-0" />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
          <div ref={messagesEndRef} />
          
          {/* Typing Indicator */}
          {typingUsers.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
              </div>
              <span>
                {typingUsers.map(u => u.user_name).join(', ')} {typingUsers.length === 1 ? 'is' : 'are'} typing...
              </span>
            </div>
          )}
        </div>

        {/* Selected File Preview */}
        {selectedFile && (
          <div className="px-4 py-2 border-t bg-blue-50">
            <div className="flex items-center gap-2">
              {getFileIcon(selectedFile.name.split('.').pop())}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{selectedFile.name}</p>
                <p className="text-xs text-muted-foreground">{formatFileSize(selectedFile.size)}</p>
              </div>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={removeSelectedFile}
                className="h-6 w-6 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}

        {/* Message Input */}
        <div className="p-4 border-t bg-white">
          <form onSubmit={handleSendMessage} className="flex gap-2">
            {/* File attachment button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              className="hidden"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.gif,.txt,.csv"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
              disabled={sending || uploading}
              title="Attach file"
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            
            <Input
              value={newMessage}
              onChange={(e) => {
                setNewMessage(e.target.value);
                handleTyping();
              }}
              placeholder={selectedFile ? `Add a message for ${selectedFile.name}...` : `Message #${activeChannelInfo?.name || 'general'}...`}
              className="flex-1"
              disabled={sending || uploading}
              data-testid="chat-input"
            />
            <Button 
              type="submit" 
              disabled={sending || uploading || (!newMessage.trim() && !selectedFile)}
              data-testid="send-message-btn"
            >
              {uploading ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default StaffChat;
