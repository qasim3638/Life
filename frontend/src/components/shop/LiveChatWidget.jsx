/**
 * Live Chat Widget - Customer support chat for website visitors
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MessageCircle, X, Send, Minimize2, Maximize2, User, Bot, Headphones, Loader2, Clock, Mail } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { cn } from '../../lib/utils';
import { useLocation } from 'react-router-dom';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const LiveChatWidget = () => {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [settings, setSettings] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [visitorName, setVisitorName] = useState('');
  const [visitorEmail, setVisitorEmail] = useState('');
  const [showNameInput, setShowNameInput] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [waitingForAgent, setWaitingForAgent] = useState(false);
  const [showContactForm, setShowContactForm] = useState(false);
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactMessage, setContactMessage] = useState('');
  const [contactSubmitted, setContactSubmitted] = useState(false);
  const [agentResponded, setAgentResponded] = useState(false);
  
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const waitTimerRef = useRef(null);
  const agentRespondedRef = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, showContactForm]);

  // Fetch chat settings
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch(`${API_URL}/api/live-chat/settings/public`);
        if (response.ok) {
          const data = await response.json();
          setSettings(data);
        }
      } catch (error) {
        setSettings({
          enabled: true,
          welcome_message: "Hi! How can we help you today?",
          connecting_message: "Please wait while we connect you to our customer service team member.",
          theme_color: "#1a1a1a",
          position: "bottom-right",
          online_hours_start: "08:00",
          online_hours_end: "18:00",
          no_response_timeout: 2
        });
      }
    };
    fetchSettings();
  }, []);

  // Start or resume chat session
  const startSession = useCallback(async () => {
    if (sessionId) return;
    
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/live-chat/session/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        const data = await response.json();
        setSessionId(data.session_id);
        setMessages(data.messages || []);
        connectWebSocket(data.session_id);
      }
    } catch (error) {
      console.error('[Chat] Session start error:', error);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  // Connect WebSocket
  const connectWebSocket = (sid) => {
    const wsUrl = `${API_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/api/live-chat/ws/visitor/${sid}`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'message') {
            setMessages(prev => [...prev, data.message]);
            if (!isOpen) setUnreadCount(prev => prev + 1);
            
            // Agent or admin responded - clear wait timer
            if (data.message.sender === 'admin' || data.message.sender === 'agent') {
              setAgentResponded(true);
              agentRespondedRef.current = true;
              setWaitingForAgent(false);
              setShowContactForm(false);
              if (waitTimerRef.current) {
                clearTimeout(waitTimerRef.current);
                waitTimerRef.current = null;
              }
            }
          } else if (data.type === 'admin_typing') {
            setIsTyping(true);
            setTimeout(() => setIsTyping(false), 3000);
          }
        } catch (e) {
          console.debug('[Chat] parse error:', e);
        }
      };
      
      wsRef.current.onclose = () => {
        reconnectTimeoutRef.current = setTimeout(() => {
          if (sessionId) connectWebSocket(sessionId);
        }, 5000);
      };
    } catch (error) {
      console.debug('[Chat] WebSocket error:', error);
    }
  };

  // Cleanup
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (waitTimerRef.current) clearTimeout(waitTimerRef.current);
    };
  }, []);

  // Send message
  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim() || isLoading) return;

    const msgText = inputMessage.trim();
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/live-chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: msgText,
          visitor_name: visitorName || undefined,
          visitor_email: visitorEmail || undefined
        })
      });

      if (response.ok) {
        const data = await response.json();
        
        // Check if this is the first visitor message
        const visitorMsgCount = messages.filter(m => m.sender === 'visitor').length;
        const isFirstMessage = visitorMsgCount === 0 && !agentRespondedRef.current;
        
        // Add visitor message
        const newMessages = [{
          id: data.message_id,
          sender: 'visitor',
          message: msgText,
          timestamp: new Date().toISOString()
        }];

        // Add "connecting" message immediately for first message
        if (isFirstMessage) {
          const connectingMsg = settings?.connecting_message || 'Please wait while we connect you to our customer service team member.';
          newMessages.push({
            id: `connecting-${Date.now()}`,
            sender: 'system',
            message: connectingMsg,
            timestamp: new Date().toISOString()
          });
          setWaitingForAgent(true);

          // Start timeout for contact form
          const timeout = (settings?.no_response_timeout || 2) * 60 * 1000;
          waitTimerRef.current = setTimeout(() => {
            if (!agentRespondedRef.current) {
              setShowContactForm(true);
              setWaitingForAgent(false);
            }
          }, timeout);
        }

        setMessages(prev => [...prev, ...newMessages]);

        // Show AI response after a delay (so connecting message is seen first)
        if (data.ai_response) {
          setTimeout(() => {
            setMessages(prev => [...prev, data.ai_response]);
          }, isFirstMessage ? 1500 : 0);
        }
      }
    } catch (error) {
      console.error('[Chat] Send error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Submit contact form
  const submitContactForm = async (e) => {
    e.preventDefault();
    if (!contactEmail.trim()) return;

    try {
      await fetch(`${API_URL}/api/live-chat/offline-message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          name: contactName,
          email: contactEmail,
          message: contactMessage || 'Left contact details for callback'
        })
      });
      setContactSubmitted(true);

      // Add system message
      setMessages(prev => [...prev, {
        id: `form-${Date.now()}`,
        sender: 'system',
        message: `Thanks ${contactName || 'there'}! We'll get back to you at ${contactEmail}. You can continue chatting here if you'd like.`,
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('[Chat] Contact form error:', error);
    }
  };

  const handleOpenChat = () => {
    setIsOpen(true);
    setIsMinimized(false);
    setUnreadCount(0);
    if (!sessionId) startSession();
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getSenderIcon = (sender) => {
    switch (sender) {
      case 'visitor': return <User className="w-4 h-4" />;
      case 'ai': return <Bot className="w-4 h-4" />;
      case 'admin': return <Headphones className="w-4 h-4" />;
      case 'system': return <Clock className="w-4 h-4" />;
      default: return <MessageCircle className="w-4 h-4" />;
    }
  };

  if (settings && !settings.enabled) return null;

  return (
    <>
      {/* Chat Widget Button */}
      {!isOpen && (
        <button
          onClick={handleOpenChat}
          className={cn(
            "fixed z-50 p-4 rounded-full shadow-lg transition-all duration-300 hover:scale-110",
            "bg-[#1a1a1a] text-white hover:bg-[#333]",
            settings?.position === 'bottom-left' ? 'left-6 bottom-20 md:bottom-6' : 'right-6 bottom-20 md:bottom-6'
          )}
          style={{ backgroundColor: settings?.theme_color }}
          data-testid="chat-widget-button"
        >
          <MessageCircle className="w-6 h-6" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
              {unreadCount}
            </span>
          )}
        </button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div
          className={cn(
            "fixed z-50 transition-all duration-300",
            settings?.position === 'bottom-left' ? 'left-6 bottom-20 md:bottom-6' : 'right-6 bottom-20 md:bottom-6',
            isMinimized ? 'w-72 h-14' : 'w-96 h-[520px]'
          )}
          data-testid="chat-window"
        >
          <div className="bg-white rounded-2xl shadow-2xl flex flex-col h-full overflow-hidden border border-gray-200">
            {/* Header */}
            <div 
              className="flex items-center justify-between p-4 text-white"
              style={{ backgroundColor: settings?.theme_color || '#1a1a1a' }}
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                  <MessageCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold">Tile Station</h3>
                  <p className="text-xs text-white/70">
                    {isTyping ? 'Typing...' : waitingForAgent ? 'Connecting...' : 'We typically reply instantly'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => setIsMinimized(!isMinimized)} className="p-2 hover:bg-white/20 rounded-full transition">
                  {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
                </button>
                <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-white/20 rounded-full transition">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {!isMinimized && (
              <>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                  {messages.map((msg, idx) => (
                    <div key={msg.id || idx}>
                      {msg.sender === 'system' ? (
                        <div className="flex justify-center">
                          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-2 max-w-[85%] text-center">
                            <p className="text-sm text-amber-800">{msg.message}</p>
                            <p className="text-xs text-amber-500 mt-1">{formatTime(msg.timestamp)}</p>
                          </div>
                        </div>
                      ) : (
                        <div className={cn("flex gap-2", msg.sender === 'visitor' ? 'justify-end' : 'justify-start')}>
                          {msg.sender !== 'visitor' && (
                            <div className={cn(
                              "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                              msg.sender === 'ai' ? 'bg-purple-100 text-purple-600' : 
                              msg.sender === 'admin' ? 'bg-green-100 text-green-600' : 
                              'bg-gray-100 text-gray-600'
                            )}>
                              {getSenderIcon(msg.sender)}
                            </div>
                          )}
                          <div className={cn(
                            "max-w-[75%] rounded-2xl px-4 py-2",
                            msg.sender === 'visitor' 
                              ? 'bg-[#1a1a1a] text-white rounded-br-md' 
                              : 'bg-white shadow-sm rounded-bl-md'
                          )}
                          style={msg.sender === 'visitor' ? { backgroundColor: settings?.theme_color } : {}}>
                            <p className="text-sm">{msg.message}</p>
                            <p className={cn("text-xs mt-1", msg.sender === 'visitor' ? 'text-white/60' : 'text-gray-400')}>
                              {formatTime(msg.timestamp)}
                            </p>
                          </div>
                          {msg.sender === 'visitor' && (
                            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
                              <User className="w-4 h-4 text-gray-600" />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {/* Waiting indicator */}
                  {waitingForAgent && (
                    <div className="flex justify-center">
                      <div className="flex items-center gap-2 text-gray-400 text-sm">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Connecting you to a team member...
                      </div>
                    </div>
                  )}

                  {isTyping && (
                    <div className="flex gap-2">
                      <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                        <Headphones className="w-4 h-4 text-green-600" />
                      </div>
                      <div className="bg-white shadow-sm rounded-2xl rounded-bl-md px-4 py-3">
                        <div className="flex gap-1">
                          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {isLoading && messages.length === 0 && (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                    </div>
                  )}

                  {/* Contact Form (shows after timeout) */}
                  {showContactForm && !contactSubmitted && (
                    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                      <div className="flex items-center gap-2 mb-3">
                        <Clock className="w-4 h-4 text-amber-500" />
                        <p className="text-sm font-medium text-gray-700">Our team is currently busy</p>
                      </div>
                      <p className="text-xs text-gray-500 mb-1">
                        Opening hours: {settings?.online_hours_start || '08:00'} - {settings?.online_hours_end || '18:00'} (Mon-Fri)
                      </p>
                      <p className="text-xs text-gray-500 mb-3">Leave your details and we'll get back to you:</p>
                      <form onSubmit={submitContactForm} className="space-y-2">
                        <Input
                          value={contactName}
                          onChange={(e) => setContactName(e.target.value)}
                          placeholder="Your name"
                          className="text-sm"
                          data-testid="chat-contact-name"
                        />
                        <Input
                          value={contactEmail}
                          onChange={(e) => setContactEmail(e.target.value)}
                          placeholder="Your email *"
                          type="email"
                          required
                          className="text-sm"
                          data-testid="chat-contact-email"
                        />
                        <Input
                          value={contactMessage}
                          onChange={(e) => setContactMessage(e.target.value)}
                          placeholder="Message (optional)"
                          className="text-sm"
                          data-testid="chat-contact-message"
                        />
                        <Button type="submit" size="sm" className="w-full" data-testid="chat-contact-submit">
                          <Mail className="w-4 h-4 mr-1" /> Send Details
                        </Button>
                      </form>
                    </div>
                  )}
                  
                  <div ref={messagesEndRef} />
                </div>

                {/* Name Input */}
                {showNameInput && (
                  <div className="p-4 bg-gray-100 border-t">
                    <p className="text-sm text-gray-600 mb-2">What should we call you?</p>
                    <div className="flex gap-2">
                      <Input value={visitorName} onChange={(e) => setVisitorName(e.target.value)} placeholder="Your name (optional)" className="flex-1" />
                      <Button onClick={() => setShowNameInput(false)} size="sm">Continue</Button>
                    </div>
                  </div>
                )}

                {/* Message Input */}
                <form onSubmit={sendMessage} className="p-4 border-t bg-white">
                  <div className="flex gap-2">
                    <Input
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      placeholder="Type your message..."
                      className="flex-1"
                      disabled={isLoading}
                      data-testid="chat-message-input"
                    />
                    <Button 
                      type="submit" 
                      disabled={!inputMessage.trim() || isLoading}
                      style={{ backgroundColor: settings?.theme_color }}
                      data-testid="chat-send-button"
                    >
                      {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </Button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default LiveChatWidget;
