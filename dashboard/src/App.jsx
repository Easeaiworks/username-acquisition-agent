import { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './lib/auth';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import OverviewPage from './pages/OverviewPage';
import PipelinePage from './pages/PipelinePage';
import OpportunitiesPage from './pages/OpportunitiesPage';
import CompaniesPage from './pages/CompaniesPage';
import OutreachPage from './pages/OutreachPage';
import ApprovalsPage from './pages/ApprovalsPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import AdminIntegrationsPage from './pages/AdminIntegrationsPage';
import AdminUploadsPage from './pages/AdminUploadsPage';
import AdminTemplatesPage from './pages/AdminTemplatesPage';
import AdminUsersPage from './pages/AdminUsersPage';
import EmailContactsPage from './pages/EmailContactsPage';
import EmailCampaignsPage from './pages/EmailCampaignsPage';
import EmailSequencesPage from './pages/EmailSequencesPage';
import EmailSendersPage from './pages/EmailSendersPage';
import AutomationsPage from './pages/AutomationsPage';
import WebhooksPage from './pages/WebhooksPage';
import { getIntegrations, getAdminUsers } from './lib/api';

const PAGES = {
  overview: OverviewPage,
  pipeline: PipelinePage,
  opportunities: OpportunitiesPage,
  companies: CompaniesPage,
  outreach: OutreachPage,
  approvals: ApprovalsPage,
  reports: ReportsPage,
  settings: SettingsPage,
  'admin-integrations': AdminIntegrationsPage,
  'admin-uploads': AdminUploadsPage,
  'admin-templates': AdminTemplatesPage,
  'admin-users': AdminUsersPage,
  'email-contacts': EmailContactsPage,
  'email-campaigns': EmailCampaignsPage,
  'email-sequences': EmailSequencesPage,
  'email-senders': EmailSendersPage,
  'admin-automations': AutomationsPage,
  'admin-webhooks': WebhooksPage,
};

function Dashboard() {
  const [currentPage, setCurrentPage] = useState('overview');
  const { setUserRole } = useAuth();
  const PageComponent = PAGES[currentPage] || OverviewPage;

  useEffect(() => {
    detectRole();
  }, []);

  async function detectRole() {
    try {
      // Try admin endpoint first — accessible by admin and super_admin
      await getIntegrations();
      // If we get here, user is at least admin
      try {
        // Try super_admin-only endpoint
        await getAdminUsers();
        setUserRole('super_admin');
      } catch {
        // admin users endpoint failed — user is admin but not super_admin
        setUserRole('admin');
      }
    } catch {
      // integrations endpoint failed — user is viewer
      setUserRole('viewer');
    }
  }

  return (
    <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
      <PageComponent />
    </Layout>
  );
}

function AuthGate() {
  const { isAuthenticated, setApiKey, setUserRole } = useAuth();

  function handleLoginSuccess(data) {
    // data = { api_key, user_id, email, name, role }
    if (data.role) {
      setUserRole(data.role);
    }
  }

  if (!isAuthenticated) {
    return (
      <LoginPage
        onLogin={setApiKey}
        onLoginSuccess={handleLoginSuccess}
      />
    );
  }

  return <Dashboard />;
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
