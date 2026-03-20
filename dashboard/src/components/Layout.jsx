import { useState } from 'react';
import { LayoutDashboard, Building2, Target, Mail, CheckSquare, BarChart3, Settings, Menu, X } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'pipeline', label: 'Pipeline', icon: BarChart3 },
  { id: 'opportunities', label: 'Opportunities', icon: Target },
  { id: 'companies', label: 'Companies', icon: Building2 },
  { id: 'outreach', label: 'Outreach', icon: Mail },
  { id: 'approvals', label: 'Approvals', icon: CheckSquare },
];

export default function Layout({ currentPage, onNavigate, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 text-white transform transition-transform duration-200 ease-in-out
        lg:relative lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-700">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Sean Lead Agent</h1>
            <p className="text-xs text-gray-400">Username Acquisition System</p>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="lg:hidden text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        <nav className="mt-4 px-3">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => { onNavigate(id); setSidebarOpen(false); }}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-1
                ${currentPage === id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'}
              `}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>

        <div className="absolute bottom-4 left-3 right-3">
          <div className="px-3 py-3 bg-gray-800 rounded-lg">
            <p className="text-xs text-gray-400">Daily Pipeline</p>
            <p className="text-sm text-green-400 font-medium">Active — 6:00 AM</p>
          </div>
        </div>
      </aside>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 flex items-center justify-between px-6 bg-white border-b border-gray-200">
          <button onClick={() => setSidebarOpen(true)} className="lg:hidden text-gray-600">
            <Menu size={24} />
          </button>
          <div className="flex items-center gap-4">
            <div className="hidden sm:block">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                System Online
              </span>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
