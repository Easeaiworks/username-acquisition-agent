import { useState } from 'react';
import { LayoutDashboard, Building2, Target, Mail, CheckSquare, BarChart3, FileText, Settings, Menu, X, LogOut, Key, Upload, Users, Shield, Send, GitBranch, Server, Zap, Globe } from 'lucide-react';
import { useAuth } from '../lib/auth';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'pipeline', label: 'Pipeline', icon: BarChart3 },
  { id: 'opportunities', label: 'Opportunities', icon: Target },
  { id: 'companies', label: 'Companies', icon: Building2 },
  { id: 'outreach', label: 'Outreach', icon: Mail },
  { id: 'approvals', label: 'Approvals', icon: CheckSquare },
  { id: 'reports', label: 'Reports', icon: FileText },
  { id: 'settings', label: 'Settings', icon: Settings },
];

const EMAIL_NAV_ITEMS = [
  { id: 'email-contacts', label: 'Contacts', icon: Users },
  { id: 'email-campaigns', label: 'Campaigns', icon: Send },
  { id: 'email-sequences', label: 'Sequences', icon: GitBranch },
];

const ADMIN_NAV_ITEMS = [
  { id: 'admin-integrations', label: 'Integrations', icon: Key },
  { id: 'admin-uploads', label: 'File Manager', icon: Upload },
  { id: 'admin-templates', label: 'Templates', icon: Mail },
  { id: 'email-senders', label: 'Email Senders', icon: Server },
  { id: 'admin-automations', label: 'Automations', icon: Zap },
  { id: 'admin-webhooks', label: 'Webhooks', icon: Globe },
  { id: 'admin-users', label: 'Users', icon: Users },
];

export default function Layout({ currentPage, onNavigate, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { logout, userRole } = useAuth();

  const showAdmin = userRole === 'super_admin' || userRole === 'admin';

  return (
    <div className="flex h-screen" style={{ background: '#eef1f8' }}>
      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 sidebar-glass text-white transform transition-transform duration-200 ease-in-out
        lg:relative lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex items-center justify-between h-16 px-6" style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.15)' }}>
          <div>
            <h1 className="text-lg font-semibold tracking-tight" style={{ color: '#e2e8f4' }}>Sean Lead Agent</h1>
            <p className="text-xs" style={{ color: '#8b9fd4' }}>Username Acquisition System</p>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden" style={{ color: '#8b9fd4' }}>
            <X size={20} />
          </button>
        </div>

        <nav className="mt-4 px-3 flex-1 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 10rem)' }}>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { onNavigate(id); setSidebarOpen(false); }}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium mb-1 nav-item
                ${currentPage === id ? 'nav-item-active text-white' : ''}
              `}
              style={currentPage !== id ? { color: '#a4b3d4' } : {}}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}

          {/* Email Section — visible to all authenticated users */}
          <div className="mx-0 my-3 border-t" style={{ borderColor: 'rgba(91, 126, 194, 0.15)' }} />
          <p className="px-3 text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: '#5b7ec2' }}>
            <Mail size={12} className="inline mr-1.5 -mt-0.5" />
            Email
          </p>
          {EMAIL_NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { onNavigate(id); setSidebarOpen(false); }}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium mb-1 nav-item
                ${currentPage === id ? 'nav-item-active text-white' : ''}
              `}
              style={currentPage !== id ? { color: '#a4b3d4' } : {}}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}

          {showAdmin && (
            <>
              <div className="mx-0 my-3 border-t" style={{ borderColor: 'rgba(91, 126, 194, 0.15)' }} />
              <p className="px-3 text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: '#5b7ec2' }}>
                <Shield size={12} className="inline mr-1.5 -mt-0.5" />
                Admin
              </p>
              {ADMIN_NAV_ITEMS.filter(item => {
                if (item.id === 'admin-users') return userRole === 'super_admin';
                if (item.id === 'admin-automations' || item.id === 'admin-webhooks') return userRole === 'super_admin' || userRole === 'admin';
                return true;
              }).map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => { onNavigate(id); setSidebarOpen(false); }}
                  className={`
                    w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium mb-1 nav-item
                    ${currentPage === id ? 'nav-item-active text-white' : ''}
                  `}
                  style={currentPage !== id ? { color: '#a4b3d4' } : {}}
                >
                  <Icon size={18} />
                  {label}
                </button>
              ))}
            </>
          )}
        </nav>

        <div className="absolute bottom-4 left-3 right-3 space-y-2">
          <div className="px-3 py-3 rounded-lg pipeline-status">
            <p className="text-xs" style={{ color: '#8b9fd4' }}>Daily Pipeline</p>
            <p className="text-sm font-medium" style={{ color: '#34d399' }}>Active — 6:00 AM</p>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors hover:bg-white/5"
            style={{ color: '#8b9fd4' }}
          >
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" style={{ background: 'rgba(15, 26, 46, 0.6)' }} onClick={() => setSidebarOpen(false)} />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 flex items-center justify-between px-6 header-glass">
          <button onClick={() => setSidebarOpen(true)} className="lg:hidden" style={{ color: '#2b3f6b' }}>
            <Menu size={24} />
          </button>
          <div className="flex items-center gap-4">
            <div className="hidden sm:block">
              <span className="status-online inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold text-white">
                System Online
              </span>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6 page-enter">
          {children}
        </main>
      </div>
    </div>
  );
}
