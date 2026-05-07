import { useState } from 'react';
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

const PAGES = {
  overview: OverviewPage,
  pipeline: PipelinePage,
  opportunities: OpportunitiesPage,
  companies: CompaniesPage,
  outreach: OutreachPage,
  approvals: ApprovalsPage,
  reports: ReportsPage,
  settings: SettingsPage,
};

function Dashboard() {
  const [currentPage, setCurrentPage] = useState('overview');
  const PageComponent = PAGES[currentPage] || OverviewPage;

  return (
    <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
      <PageComponent />
    </Layout>
  );
}

function AuthGate() {
  const { isAuthenticated, setApiKey } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage onLogin={setApiKey} />;
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
