import { useState } from 'react';
import Layout from './components/Layout';
import OverviewPage from './pages/OverviewPage';
import PipelinePage from './pages/PipelinePage';
import OpportunitiesPage from './pages/OpportunitiesPage';
import CompaniesPage from './pages/CompaniesPage';
import OutreachPage from './pages/OutreachPage';
import ApprovalsPage from './pages/ApprovalsPage';

const PAGES = {
  overview: OverviewPage,
  pipeline: PipelinePage,
  opportunities: OpportunitiesPage,
  companies: CompaniesPage,
  outreach: OutreachPage,
  approvals: ApprovalsPage,
};

export default function App() {
  const [currentPage, setCurrentPage] = useState('overview');
  const PageComponent = PAGES[currentPage] || OverviewPage;

  return (
    <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
      <PageComponent />
    </Layout>
  );
}
