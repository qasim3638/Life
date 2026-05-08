import React from 'react';
import HubPage from '../../components/HubPage';
import { 
  Settings, Building2, Shield, KeyRound, Link2, 
  Trash2, Cog, Database, Lock, Percent, ShieldCheck
} from 'lucide-react';

export default function SettingsHub() {
  const cards = [
    {
      title: 'Pricing Settings',
      description: 'Configure markup % and update prices',
      icon: Percent,
      link: '/admin/pricing-settings',
      color: 'bg-amber-600'
    },
    {
      title: 'Stores',
      description: 'Manage store locations',
      icon: Building2,
      link: '/admin/showrooms',
      color: 'bg-blue-600'
    },
    {
      title: 'User Management',
      description: 'Manage admin users and roles',
      icon: Shield,
      link: '/admin/users',
      color: 'bg-green-600'
    },
    {
      title: 'Permissions',
      description: 'Control which pages and actions each role can access',
      icon: ShieldCheck,
      link: '/admin/permissions',
      color: 'bg-emerald-600'
    },
    {
      title: 'Storefront Features',
      description: 'Show/hide Compare, Refer-a-friend & Welcome Popup on the live website',
      icon: Cog,
      link: '/admin/storefront-features',
      color: 'bg-amber-600'
    },
    {
      title: 'Staff PINs',
      description: 'Manage staff PIN codes',
      icon: KeyRound,
      link: '/admin/staff-pins',
      color: 'bg-purple-600'
    },
    {
      title: 'Staff Invites',
      description: 'Invite new staff members',
      icon: Link2,
      link: '/admin/staff-invites',
      color: 'bg-orange-600'
    },
    {
      title: 'Trash',
      description: 'Restore deleted items',
      icon: Trash2,
      link: '/admin/trash',
      color: 'bg-red-600'
    },
    {
      title: 'General Settings',
      description: 'System configuration',
      icon: Cog,
      link: '/admin/settings',
      color: 'bg-slate-600'
    },
    {
      title: 'Backup',
      description: 'Database backup and restore',
      icon: Database,
      link: '/admin/backup',
      color: 'bg-cyan-600'
    },
    {
      title: 'Security',
      description: 'Device authorization and security settings',
      icon: Lock,
      link: '/admin/settings?tab=security',
      color: 'bg-pink-600'
    },
  ];

  return (
    <HubPage 
      title="Admin Settings" 
      subtitle="System configuration and user management"
      icon={Settings}
      cards={cards} 
    />
  );
}
