import React from 'react';
import HubPage from '../../components/HubPage';
import {
  Radio, MessageCircle, ClipboardList, Mail, Send,
  Megaphone, Bell, Phone, FolderOpen, BookOpen,
} from 'lucide-react';

export default function CommunicationHub() {
  const cards = [
    {
      title: 'Document Storage',
      description: 'Manage files, folders & permissions',
      icon: FolderOpen,
      link: '/admin/documents',
      color: 'bg-cyan-600'
    },
    {
      title: 'Staff Chat',
      description: 'Internal team communication',
      icon: MessageCircle,
      link: '/admin/chat',
      color: 'bg-blue-600'
    },
    {
      title: 'Tasks & Notes',
      description: 'Manage tasks and leave notes',
      icon: ClipboardList,
      link: '/admin/tasks',
      color: 'bg-green-600'
    },
    {
      title: 'Staff Training Booklet',
      description: 'Download the operations manual · Super-admin can edit notes',
      icon: BookOpen,
      link: '/admin/training-booklet',
      color: 'bg-amber-600'
    },
    {
      title: 'Inbox',
      description: 'View received messages',
      icon: Mail,
      link: '/admin/inbox',
      color: 'bg-purple-600'
    },
    {
      title: 'Send Email',
      description: 'Compose and send emails',
      icon: Send,
      link: '/admin/email',
      color: 'bg-orange-600'
    },
    {
      title: 'Marketing',
      description: 'Marketing campaigns and promotions',
      icon: Megaphone,
      link: '/admin/marketing',
      color: 'bg-pink-600'
    },
    {
      title: 'Notifications',
      description: 'Manage system notifications',
      icon: Bell,
      link: '/admin/notifications',
      color: 'bg-red-600'
    },
    {
      title: 'WhatsApp',
      description: 'WhatsApp business integration',
      icon: Phone,
      link: '/admin/whatsapp',
      color: 'bg-emerald-600'
    },
  ];

  return (
    <HubPage
      title="Communication"
      subtitle="Internal communication and marketing"
      icon={Radio}
      cards={cards}
    />
  );
}
